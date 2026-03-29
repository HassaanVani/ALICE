import React, { useState, useEffect, useRef, useCallback } from 'react';
import CameraPanel from './components/CameraPanel.jsx';
import BlockOverlay from './components/BlockOverlay.jsx';
import ArmOverlay from './components/ArmOverlay.jsx';
import ActivationPanel from './components/ActivationPanel.jsx';
import BrainViewport from './components/BrainViewport.jsx';
import SimulatedArm from './components/SimulatedArm/SimulatedArm.jsx';
import SystemState from './components/SystemState.jsx';
import ModeControls from './components/ModeControls.jsx';
import SortDashboard from './components/SortDashboard.jsx';
import TetrisDashboard from './components/TetrisDashboard.jsx';
import RecordingControls from './components/RecordingControls.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';
import PersonalityPanel from './components/PersonalityPanel.jsx';
import ObjectMemoryPanel from './components/ObjectMemoryPanel.jsx';
import DeskPresetSelector from './components/DeskPresetSelector.jsx';
import PerformanceTimeline from './components/PerformanceTimeline.jsx';
import { ToastProvider, useToast } from './components/Toast.jsx';
import Audience from './pages/Audience.jsx';
import { AliceSocketProvider } from './hooks/AliceSocketProvider.jsx';
import { useAliceState } from './hooks/useAliceState.js';
import { useTensorStream } from './hooks/useTensorStream.js';
import { useCameraStream } from './hooks/useCameraStream.js';

function getRoute() {
  return window.location.hash.replace('#', '') || '/';
}

const MODE_IDS = ['idle', 'auto_sort', 'auto_tetris', 'puppeteer', 'demo', 'performance', 'calibrate'];

const SHORTCUTS = [
  { key: '1-7', description: 'Switch mode (Idle, Sort, Tetris, Puppet, Demo, Perform, Cal)' },
  { key: 'R', description: 'Toggle recording' },
  { key: 'Esc', description: 'Switch to Idle' },
  { key: '?', description: 'Toggle this help overlay' },
];

function ShortcutsOverlay({ onClose }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 9000,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--bg-panel-solid)',
          border: '1px solid var(--glass-border)',
          borderRadius: 10, padding: '20px 28px',
          fontFamily: 'var(--font-mono)', minWidth: 320,
          boxShadow: 'var(--glass-shadow)',
        }}
      >
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 14 }}>
          Keyboard Shortcuts
        </div>
        {SHORTCUTS.map((s) => (
          <div key={s.key} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
            <span style={{
              fontSize: 11, color: 'var(--text-primary)',
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid var(--border-color)',
              borderRadius: 4, padding: '2px 8px', fontWeight: 600,
            }}>{s.key}</span>
            <span style={{ fontSize: 10, color: 'var(--text-secondary)', marginLeft: 16 }}>{s.description}</span>
          </div>
        ))}
        <div style={{ fontSize: 9, color: 'var(--text-dim)', marginTop: 12, textAlign: 'center' }}>
          Press <strong>?</strong> or <strong>Esc</strong> to close
        </div>
      </div>
    </div>
  );
}

function Dashboard() {
  const { state, connected, sendCommand, updateState } = useAliceState();
  const { activations } = useTensorStream();
  const { frameRef, cameraConnected } = useCameraStream();
  const { addToast } = useToast();
  const [showShortcuts, setShowShortcuts] = useState(false);
  const prevConnectedRef = useRef(connected);
  const prevModeRef = useRef(state.mode);
  const prevRecordingRef = useRef(state.recording);

  const armAngles = state.arm_position || [90, 90, 90, 90, 90];
  const gripperOpen = !(state.gripper_position > 0.5);
  const mood = state.personality_mood ?? 0.5;
  const isPerformance = state.mode === 'performance';
  const demoAct = state.demo_act || 0;

  // Toast on mode switch
  useEffect(() => {
    if (prevModeRef.current !== undefined && state.mode !== prevModeRef.current) {
      addToast(`Mode: ${state.mode || 'idle'}`, 'info');
    }
    prevModeRef.current = state.mode;
  }, [state.mode, addToast]);

  // Toast on recording toggle
  useEffect(() => {
    if (prevRecordingRef.current !== undefined && state.recording !== prevRecordingRef.current) {
      addToast(state.recording ? 'Recording started' : 'Recording stopped', state.recording ? 'error' : 'success');
    }
    prevRecordingRef.current = state.recording;
  }, [state.recording, addToast]);

  // Toast on WS reconnect
  useEffect(() => {
    if (prevConnectedRef.current === false && connected === true) {
      addToast('Reconnected to ALICE', 'success');
    }
    prevConnectedRef.current = connected;
  }, [connected, addToast]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      const tag = document.activeElement?.tagName;
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;

      if (e.key === '?') { e.preventDefault(); setShowShortcuts((v) => !v); return; }

      if (e.key === 'Escape') {
        if (showShortcuts) { setShowShortcuts(false); }
        else { updateState({ mode: 'idle' }); sendCommand('switch_mode', { mode: 'idle' }); }
        return;
      }

      if (e.key === 'r' || e.key === 'R') {
        sendCommand(state.recording ? 'stop_recording' : 'start_recording');
        return;
      }

      const num = parseInt(e.key, 10);
      if (num >= 1 && num <= MODE_IDS.length) {
        const modeId = MODE_IDS[num - 1];
        updateState({ mode: modeId });
        sendCommand('switch_mode', { mode: modeId });
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showShortcuts, sendCommand, updateState, state.recording]);

  const handleSnapshot = useCallback(() => {
    sendCommand('snapshot');
    addToast('Snapshot captured', 'success');
  }, [sendCommand, addToast]);

  const handlePresetSelect = useCallback((preset) => {
    sendCommand('vote_preset', { preset });
    addToast(`Voted: ${preset}`, 'info');
  }, [sendCommand, addToast]);

  return (
    <div className="dashboard">
      {showShortcuts && <ShortcutsOverlay onClose={() => setShowShortcuts(false)} />}

      {/* Connection warning banner */}
      {!connected && (
        <div style={{
          gridColumn: '1 / -1',
          background: 'rgba(127, 29, 29, 0.6)', backdropFilter: 'blur(10px)',
          color: '#fca5a5', padding: '6px 16px', fontSize: 11,
          fontFamily: 'var(--font-mono)', textAlign: 'center',
          borderRadius: 6, border: '1px solid rgba(153, 27, 27, 0.5)',
        }}>
          Disconnected from ALICE — data may be stale. Reconnecting...
        </div>
      )}

      {/* Header */}
      <div className="dashboard-header">
        <h1>A.L.I.C.E.</h1>
        <div className="header-controls">
          {/* Mood bar in header */}
          <div className="mood-bar">
            <div className="mood-bar-fill" style={{ width: `${mood * 100}%` }} />
          </div>
          <select
            className="mode-select"
            value={state.mode || 'idle'}
            onChange={(e) => {
              const mode = e.target.value;
              updateState({ mode });
              sendCommand('switch_mode', { mode });
            }}
          >
            <option value="idle">Idle</option>
            <option value="auto_sort">Auto Sort</option>
            <option value="auto_tetris">Auto Tetris</option>
            <option value="puppeteer">Puppeteer</option>
            <option value="demo">Demo</option>
            <option value="performance">Performance</option>
            <option value="calibrate">Calibrate</option>
          </select>
          <div className={`status-dot ${connected ? '' : 'disconnected'}`} />
        </div>
      </div>

      {/* Performance Timeline */}
      <PerformanceTimeline currentAct={demoAct} visible={isPerformance && demoAct > 0} />

      {/* Camera + Overlays */}
      <ErrorBoundary>
        <div className="panel panel-camera">
          <div className="panel-header">
            <h2>Camera Feed</h2>
            <div className="indicator" style={{ background: cameraConnected ? 'var(--success)' : 'var(--danger)' }} />
          </div>
          <div className="panel-body" style={{ padding: 0, position: 'relative' }}>
            <CameraPanel frameRef={frameRef} />
            <BlockOverlay blocks={state.blocks || []} />
            <ArmOverlay angles={armAngles} gripperOpen={gripperOpen} />
          </div>
        </div>
      </ErrorBoundary>

      {/* Brain Viewport */}
      <ErrorBoundary>
        <div className="panel panel-brain">
          <div className="panel-header">
            <h2>Glass Brain</h2>
            <div className="indicator" style={{ background: activations.length > 0 ? 'var(--success)' : 'var(--text-dim)' }} />
          </div>
          <div className="panel-body" style={{ padding: 0 }}>
            <BrainViewport activations={activations} />
          </div>
        </div>
      </ErrorBoundary>

      {/* CNN Activations */}
      <ErrorBoundary>
        <div className="panel panel-activations">
          <div className="panel-header">
            <h2>Neural Activations</h2>
            <span style={{ fontSize: 9, color: 'var(--text-dim)' }}>{activations.length} layers</span>
          </div>
          <div className="panel-body">
            <ActivationPanel activations={activations} />
          </div>
        </div>
      </ErrorBoundary>

      {/* Simulated Arm */}
      <ErrorBoundary>
        <div className="panel panel-arm">
          <div className="panel-header">
            <h2>Arm Model</h2>
            <span style={{ fontSize: 9, color: 'var(--text-dim)' }}>{armAngles.length} axes</span>
          </div>
          <div className="panel-body" style={{ padding: 0 }}>
            <SimulatedArm angles={armAngles} gripperOpen={gripperOpen} />
          </div>
        </div>
      </ErrorBoundary>

      {/* Sidebar */}
      <div className="panel-sidebar">
        {/* Personality */}
        <div className="panel">
          <div className="panel-header"><h2>Personality</h2></div>
          <div className="panel-body">
            <PersonalityPanel state={state} />
          </div>
        </div>

        {/* Object Memory */}
        <div className="panel" style={{ flex: 1 }}>
          <div className="panel-header">
            <h2>Object Memory</h2>
            <span style={{ fontSize: 9, color: 'var(--text-dim)' }}>
              {(state.object_memory || []).length} objects
            </span>
          </div>
          <div className="panel-body">
            <ObjectMemoryPanel objects={state.object_memory || []} />
          </div>
        </div>

        {/* Desk Presets (shown during performance/idle) */}
        <div className="panel">
          <div className="panel-header"><h2>Desk Presets</h2></div>
          <div className="panel-body">
            <DeskPresetSelector
              activePreset={state.active_preset}
              presetVotes={state.preset_votes}
              onSelectPreset={handlePresetSelect}
            />
          </div>
        </div>

        {/* System State */}
        <div className="panel">
          <div className="panel-header"><h2>System</h2></div>
          <div className="panel-body">
            <SystemState state={state} connected={connected} cameraConnected={cameraConnected} />
          </div>
        </div>

        {/* Context-sensitive: Sort or Tetris */}
        <SortDashboard state={state} />
        <TetrisDashboard state={state} />

        {/* Mode Controls */}
        <div className="panel" style={{ flex: 0 }}>
          <div className="panel-header"><h2>Mode Controls</h2></div>
          <div className="panel-body">
            <ModeControls currentMode={state.mode} sendCommand={sendCommand} updateState={updateState} />
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="dashboard-footer">
        <RecordingControls sendCommand={sendCommand} recording={state.recording || false} />
      </div>
    </div>
  );
}

export default function App() {
  const [route, setRoute] = useState(getRoute());

  useEffect(() => {
    const onHash = () => setRoute(getRoute());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  if (route === '/audience') {
    return <Audience />;
  }

  return (
    <AliceSocketProvider>
      <ToastProvider>
        <Dashboard />
      </ToastProvider>
    </AliceSocketProvider>
  );
}
