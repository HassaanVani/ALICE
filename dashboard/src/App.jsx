import React, { useState, useEffect } from 'react';
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
import Audience from './pages/Audience.jsx';
import { AliceSocketProvider } from './hooks/AliceSocketProvider.jsx';
import { useAliceState } from './hooks/useAliceState.js';
import { useTensorStream } from './hooks/useTensorStream.js';
import { useCameraStream } from './hooks/useCameraStream.js';

function getRoute() {
  return window.location.hash.replace('#', '') || '/';
}

function Dashboard() {
  const { state, connected, sendCommand, updateState } = useAliceState();
  const { activations } = useTensorStream();
  const { frameRef, cameraConnected } = useCameraStream();

  const armAngles = state.arm_position || [90, 90, 90, 90, 90];
  const gripperOpen = !(state.gripper_position > 0.5);

  return (
    <div className="dashboard">
      {/* Connection warning banner */}
      {!connected && (
        <div style={{
          background: '#7f1d1d',
          color: '#fca5a5',
          padding: '6px 16px',
          fontSize: 11,
          fontFamily: 'var(--font-mono)',
          textAlign: 'center',
          borderBottom: '1px solid #991b1b',
        }}>
          Disconnected from ALICE — data may be stale. Reconnecting...
        </div>
      )}
      {/* Header */}
      <div className="dashboard-header">
        <h1>ALICE Dashboard</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <select
            value={state.mode || 'idle'}
            onChange={(e) => {
              const mode = e.target.value;
              updateState({ mode });
              sendCommand('switch_mode', { mode });
            }}
            style={{
              background: '#18181b',
              color: '#e4e4e7',
              border: '1px solid #3b82f6',
              borderRadius: 4,
              padding: '4px 8px',
              fontSize: 11,
              fontFamily: 'var(--font-mono)',
              textTransform: 'uppercase',
              cursor: 'pointer',
            }}
          >
            <option value="idle">Idle</option>
            <option value="auto_sort">Auto Sort</option>
            <option value="auto_tetris">Auto Tetris</option>
            <option value="puppeteer">Puppeteer</option>
            <option value="demo">Demo</option>
            <option value="calibrate">Calibrate</option>
          </select>
          <div className={`status-dot ${connected ? '' : 'disconnected'}`} />
        </div>
      </div>

      {/* Camera + Block Overlay */}
      <div className="panel panel-camera">
        <div className="panel-header">
          <h2>Camera Feed</h2>
          <div className="indicator" style={{ background: cameraConnected ? '#22c55e' : '#ef4444' }} />
        </div>
        <div className="panel-body" style={{ padding: 0, position: 'relative' }}>
          <CameraPanel frameRef={frameRef} />
          <BlockOverlay blocks={state.blocks || []} />
          <ArmOverlay angles={armAngles} gripperOpen={gripperOpen} />
        </div>
      </div>

      {/* Brain Viewport */}
      <div className="panel panel-brain">
        <div className="panel-header">
          <h2>Brain Viewport</h2>
          <div className="indicator" style={{ background: activations.length > 0 ? '#22c55e' : '#52525b' }} />
        </div>
        <div className="panel-body" style={{ padding: 0 }}>
          <BrainViewport activations={activations} />
        </div>
      </div>

      {/* CNN Activations */}
      <div className="panel panel-activations">
        <div className="panel-header">
          <h2>CNN Activations</h2>
          <span style={{ fontSize: 10, color: '#52525b' }}>{activations.length} layers</span>
        </div>
        <div className="panel-body">
          <ActivationPanel activations={activations} />
        </div>
      </div>

      {/* Simulated Arm */}
      <div className="panel panel-arm">
        <div className="panel-header">
          <h2>Simulated Arm</h2>
          <span style={{ fontSize: 10, color: '#52525b' }}>
            {armAngles.length} axes
          </span>
        </div>
        <div className="panel-body" style={{ padding: 0 }}>
          <SimulatedArm angles={armAngles} gripperOpen={gripperOpen} />
        </div>
      </div>

      {/* Sidebar */}
      <div className="panel-sidebar">
        <div className="panel" style={{ flex: 1 }}>
          <div className="panel-header">
            <h2>System State</h2>
          </div>
          <div className="panel-body">
            <SystemState state={state} connected={connected} cameraConnected={cameraConnected} />
          </div>
        </div>
        <SortDashboard state={state} />
        <TetrisDashboard state={state} />
        <div className="panel" style={{ flex: 0 }}>
          <div className="panel-header">
            <h2>Mode Controls</h2>
          </div>
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
      <Dashboard />
    </AliceSocketProvider>
  );
}
