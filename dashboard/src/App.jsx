import React, { useState, useEffect } from 'react';
import CameraPanel from './components/CameraPanel.jsx';
import BlockOverlay from './components/BlockOverlay.jsx';
import ActivationPanel from './components/ActivationPanel.jsx';
import BrainViewport from './components/BrainViewport.jsx';
import ArmStatus from './components/ArmStatus.jsx';
import SystemState from './components/SystemState.jsx';
import ModeControls from './components/ModeControls.jsx';
import RecordingControls from './components/RecordingControls.jsx';
import Audience from './pages/Audience.jsx';
import { useAliceState } from './hooks/useAliceState.js';
import { useTensorStream } from './hooks/useTensorStream.js';
import { useCameraStream } from './hooks/useCameraStream.js';

function getRoute() {
  return window.location.hash.replace('#', '') || '/';
}

function Dashboard() {
  const { state, connected, sendCommand } = useAliceState();
  const { activations } = useTensorStream();
  const { frameRef, cameraConnected } = useCameraStream();

  return (
    <div className="dashboard">
      {/* Header */}
      <div className="dashboard-header">
        <h1>ALICE Dashboard</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 11, color: '#a1a1aa', fontFamily: 'var(--font-mono)' }}>
            {state.mode || 'IDLE'}
          </span>
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

      {/* Arm Status */}
      <div className="panel panel-arm">
        <div className="panel-header">
          <h2>Arm Status</h2>
          <span style={{ fontSize: 10, color: '#52525b' }}>
            {(state.joints || []).length} joints
          </span>
        </div>
        <div className="panel-body" style={{ padding: 0 }}>
          <ArmStatus joints={state.joints || []} gripperOpen={state.gripperOpen ?? true} />
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
        <div className="panel" style={{ flex: 0 }}>
          <div className="panel-header">
            <h2>Mode Controls</h2>
          </div>
          <div className="panel-body">
            <ModeControls currentMode={state.mode} sendCommand={sendCommand} />
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

  return <Dashboard />;
}
