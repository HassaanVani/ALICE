import React, { useState, useEffect, useCallback } from 'react';
import BrainViewport from './components/BrainViewport.jsx';
import SpatialMapViewport from './components/SpatialMapViewport.jsx';
import SimulatedArm from './components/SimulatedArm/SimulatedArm.jsx';
import CameraPanel from './components/CameraPanel.jsx';
import PuppeteerView from './components/PuppeteerView.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';
import { ToastProvider } from './components/Toast.jsx';
import { AliceSocketProvider } from './hooks/AliceSocketProvider.jsx';
import { useAliceState } from './hooks/useAliceState.js';
import { useTensorStream } from './hooks/useTensorStream.js';
import { useCameraStream } from './hooks/useCameraStream.js';


/* ═══════════════════════════════════════════════════════════
   HERO — The ALICE glassmorphic text + zoom-through-A
   ═══════════════════════════════════════════════════════════ */

function Hero({ onEnter }) {
  const [exiting, setExiting] = useState(false);

  const handleClick = () => {
    setExiting(true);
    setTimeout(onEnter, 1200);
  };

  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Enter' || e.key === ' ') handleClick();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div className={`hero ${exiting ? 'exiting' : ''}`} onClick={handleClick}>
      <div className="hero-title">ALICE</div>
      <div className="hero-subtitle">
        The first thing on your desk that knows what's on your desk.
      </div>
      <div className="hero-cta">
        <span>Click anywhere to enter</span>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════
   SIDEBAR PANELS
   ═══════════════════════════════════════════════════════════ */

const EMOTIONS = ['content', 'curious', 'annoyed', 'focused', 'reluctant', 'satisfied', 'startled', 'playful'];

function PersonalityPanel({ state }) {
  const emotion = state.personality_emotion || 'content';
  const mood = Math.round((state.personality_mood || 0.5) * 100);

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">Personality</div>
        <div className="panel-accent">{emotion}</div>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {EMOTIONS.map((e) => (
          <div key={e} className={`emotion-chip ${emotion === e ? 'active' : ''}`}>
            {e}
          </div>
        ))}
      </div>
      <div style={{ marginTop: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>MOOD</span>
          <span style={{ fontSize: 10, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{mood}%</span>
        </div>
        <div className="mood-track">
          <div className="mood-fill" style={{ width: `${mood}%` }} />
        </div>
      </div>
      {state.personality_is_in_flow && (
        <div style={{ marginTop: 10, fontSize: 10, color: 'var(--cyan)', fontWeight: 600, letterSpacing: '0.08em' }}>
          IN FLOW STATE
        </div>
      )}
    </div>
  );
}


function ObjectsPanel({ state }) {
  const objects = state.object_memory || [];

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">Object Memory</div>
        <div className="panel-accent">{objects.length}</div>
      </div>
      {objects.length === 0 ? (
        <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>No objects tracked yet</div>
      ) : (
        objects.slice(0, 8).map((obj, i) => (
          <div key={obj.object_id || i} className="obj-row">
            <div>
              <span className="obj-name">{obj.label || obj.object_id}</span>
              {obj.session_count <= 1 && <span className="badge badge-new" style={{ marginLeft: 6 }}>New</span>}
              {obj.has_moved && <span className="badge badge-moved" style={{ marginLeft: 6 }}>Moved</span>}
            </div>
            <span className="obj-detail">
              {obj.confidence ? `${Math.round(obj.confidence * 100)}%` : ''}
            </span>
          </div>
        ))
      )}
    </div>
  );
}


function LivingPanel({ state }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">Living Behaviors</div>
      </div>
      <div className="living-grid">
        <div className="living-card">
          <div className="living-num">{(state.curiosity_total || 0).toFixed(1)}</div>
          <div className="living-label">Curiosity</div>
        </div>
        <div className="living-card">
          <div className="living-num">{state.active_habits || 0}</div>
          <div className="living-label">Habits</div>
        </div>
        <div className="living-card">
          <div className="living-num" style={{ fontSize: 13 }}>{state.gaze_target || '—'}</div>
          <div className="living-label">Watching</div>
        </div>
        <div className="living-card">
          <div className="living-num" style={{ fontSize: 13 }}>{state.current_posture || '—'}</div>
          <div className="living-label">Posture</div>
        </div>
      </div>
      {state.curiosity_most_curious && (
        <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-secondary)' }}>
          Most curious about: <span style={{ color: 'var(--cyan)' }}>{state.curiosity_most_curious}</span>
        </div>
      )}
    </div>
  );
}


function ModifiersPanel({ state }) {
  const mods = [
    { key: 'spd', label: 'Speed', val: state.llm_mod_spd || 1.0 },
    { key: 'pos', label: 'Posture', val: state.llm_mod_pos || 1.0 },
  ];
  const source = state.llm_mod_source || 'default';

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">LLM Modifiers</div>
        <div className="panel-accent">{source === 'llm' ? 'Active' : 'Default'}</div>
      </div>
      {mods.map((m) => (
        <div key={m.key} className="mod-row">
          <span className="mod-key">{m.label}</span>
          <div className="mod-track">
            <div className="mod-bar" style={{ width: `${Math.min(100, (m.val / 2) * 100)}%` }} />
          </div>
          <span className="mod-val">{m.val.toFixed(1)}</span>
        </div>
      ))}
    </div>
  );
}


function SystemPanel({ state, connected }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">System</div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <SysRow label="Connection" value={connected ? 'Online' : 'Offline'} color={connected ? 'var(--green)' : 'var(--red)'} />
        <SysRow label="Arm" value={state.arm_state || 'unknown'} />
        <SysRow label="Presence" value={state.presence_detected ? `${state.presence_count} face${state.presence_count !== 1 ? 's' : ''}` : 'None'} />
        {state.tetris_score > 0 && <SysRow label="Tetris" value={`${state.tetris_score} pts`} />}
      </div>
    </div>
  );
}

function SysRow({ label, value, color }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{label}</span>
      <span style={{ fontSize: 11, fontWeight: 500, color: color || 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{value}</span>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════
   PERFORMANCE TIMELINE
   ═══════════════════════════════════════════════════════════ */

const ACTS = [
  "She's Already Here",
  "She Knows This Desk",
  "She Helps",
  "She Has Opinions",
  "Engagement",
  "Identity",
];

function Timeline({ currentAct }) {
  return (
    <div className="panel" style={{ padding: '12px 20px' }}>
      <div className="timeline">
        {ACTS.map((name, i) => (
          <div key={i} className="tl-act">
            {i < ACTS.length - 1 && <div className="tl-line" />}
            <div className={`tl-dot ${i + 1 === currentAct ? 'active' : i + 1 < currentAct ? 'done' : ''}`} />
            <div className="tl-name">{name}</div>
          </div>
        ))}
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════
   DASHBOARD — Main layout
   ═══════════════════════════════════════════════════════════ */

function Dashboard({ entering }) {
  const { state, connected } = useAliceState();
  const { activations } = useTensorStream();
  const { frameRef, cameraConnected } = useCameraStream();
  const [centerView, setCenterView] = useState('spatial');

  const mode = state.mode || 'idle';
  const isPerformance = mode === 'performance';
  const isPuppeteer = mode === 'puppeteer';

  return (
    <div className={`dashboard ${entering ? 'entering' : ''}`}>
      {/* Header */}
      <header className="dash-header">
        <div className="dash-logo">
          <span>A</span>LICE
        </div>
        <div className="dash-status">
          <div className="status-pill">
            <div className={`status-dot ${connected ? '' : 'off'}`} />
            {connected ? 'Connected' : 'Offline'}
          </div>
          <div className="mode-chip">{mode}</div>
        </div>
      </header>

      {isPuppeteer ? (
        /* Puppeteer mode — hand tracking takes over left + center */
        <div className="dash-col" style={{ gridColumn: '1 / 3' }}>
          <div className="panel panel-fill" style={{ padding: 0 }}>
            <ErrorBoundary>
              <PuppeteerView />
            </ErrorBoundary>
          </div>
        </div>
      ) : (
        <>
          {/* Left column — Camera + Arm */}
          <div className="dash-col">
            <div className="panel panel-fill" style={{ padding: 0 }}>
              <ErrorBoundary>
                <div className="camera-wrap">
                  <CameraPanel frameRef={frameRef} />
                </div>
              </ErrorBoundary>
            </div>
            <div className="panel panel-half" style={{ padding: 0 }}>
              <ErrorBoundary>
                <div className="viewport">
                  <SimulatedArm
                    angles={state.arm_position || [0, 0, 0, 0, 0]}
                    gripperOpen={state.gripper_position < 0.5}
                  />
                  <div className="viewport-tag">Arm Model</div>
                </div>
              </ErrorBoundary>
            </div>
          </div>

          {/* Center column — 3D Surroundings Heatmap & Neural View */}
          <div className="dash-col">
            {isPerformance && <Timeline currentAct={state.demo_act || 0} />}
            <div className="panel panel-fill" style={{ padding: 0 }}>
              <ErrorBoundary>
                <div className="viewport">
                  {centerView === 'spatial' ? (
                    <SpatialMapViewport state={state} />
                  ) : (
                    <BrainViewport activations={activations} />
                  )}

                  {/* Viewport Mode Switcher */}
                  <div
                    style={{
                      position: 'absolute',
                      bottom: '10px',
                      left: '14px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      zIndex: 10,
                    }}
                  >
                    <button
                      onClick={() => setCenterView('spatial')}
                      style={{
                        padding: '4px 8px',
                        fontSize: '9px',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                        background: centerView === 'spatial' ? 'rgba(0, 240, 255, 0.25)' : 'rgba(8, 16, 28, 0.7)',
                        color: centerView === 'spatial' ? '#00f0ff' : 'var(--text-dim)',
                        border: '1px solid ' + (centerView === 'spatial' ? 'rgba(0, 240, 255, 0.5)' : 'rgba(255, 255, 255, 0.1)'),
                        borderRadius: '4px',
                        cursor: 'pointer',
                        backdropFilter: 'blur(8px)',
                      }}
                    >
                      3D Surroundings Heatmap
                    </button>
                    <button
                      onClick={() => setCenterView('brain')}
                      style={{
                        padding: '4px 8px',
                        fontSize: '9px',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                        background: centerView === 'brain' ? 'rgba(0, 240, 255, 0.25)' : 'rgba(8, 16, 28, 0.7)',
                        color: centerView === 'brain' ? '#00f0ff' : 'var(--text-dim)',
                        border: '1px solid ' + (centerView === 'brain' ? 'rgba(0, 240, 255, 0.5)' : 'rgba(255, 255, 255, 0.1)'),
                        borderRadius: '4px',
                        cursor: 'pointer',
                        backdropFilter: 'blur(8px)',
                      }}
                    >
                      Neural Activations
                    </button>
                  </div>
                </div>
              </ErrorBoundary>
            </div>
          </div>
        </>
      )}

      {/* Sidebar */}
      <div className="dash-col dash-sidebar">
        <ErrorBoundary><PersonalityPanel state={state} /></ErrorBoundary>
        <ErrorBoundary><LivingPanel state={state} /></ErrorBoundary>
        <ErrorBoundary><ObjectsPanel state={state} /></ErrorBoundary>
        <ErrorBoundary><ModifiersPanel state={state} /></ErrorBoundary>
        <ErrorBoundary><SystemPanel state={state} connected={connected} /></ErrorBoundary>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════
   APP — Hero → Dashboard transition
   ═══════════════════════════════════════════════════════════ */

export default function App() {
  const [view, setView] = useState('hero'); // 'hero' | 'entering' | 'dashboard'

  const handleEnter = useCallback(() => {
    setView('entering');
    setTimeout(() => setView('dashboard'), 100);
  }, []);

  return (
    <ToastProvider>
      <AliceSocketProvider>
        {view === 'hero' && <Hero onEnter={handleEnter} />}
        {view !== 'hero' && <Dashboard entering={view === 'entering'} />}
      </AliceSocketProvider>
    </ToastProvider>
  );
}
