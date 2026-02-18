import React, { useState } from 'react';

const styles = {
  container: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '8px 12px',
    background: '#111113',
    border: '1px solid #27272a',
    borderRadius: 6,
  },
  section: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  divider: {
    width: 1,
    height: 20,
    background: '#27272a',
    margin: '0 8px',
  },
  label: {
    fontSize: 10,
    color: '#52525b',
    fontFamily: 'var(--font-mono)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginRight: 8,
  },
  recDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: '#ef4444',
    boxShadow: '0 0 8px #ef4444',
    animation: 'pulse 1s ease-in-out infinite',
  },
  recLabel: {
    fontSize: 11,
    color: '#ef4444',
    fontFamily: 'var(--font-mono)',
    fontWeight: 600,
  },
  timeLabel: {
    fontSize: 11,
    color: '#a1a1aa',
    fontFamily: 'var(--font-mono)',
  },
};

export default function RecordingControls({ sendCommand, recording }) {
  const [replayFile, setReplayFile] = useState('');

  const handleRecord = () => {
    if (recording) {
      sendCommand('stop_recording');
    } else {
      sendCommand('start_recording');
    }
  };

  const handleReplay = () => {
    sendCommand('replay', { file: replayFile || 'latest' });
  };

  const handleReplayStop = () => {
    sendCommand('stop_replay');
  };

  const handleSnapshot = () => {
    sendCommand('snapshot');
  };

  return (
    <div style={styles.container}>
      {/* Recording section */}
      <div style={styles.section}>
        <span style={styles.label}>Rec</span>
        <button
          className={`btn ${recording ? 'btn-danger' : 'btn-success'}`}
          onClick={handleRecord}
          style={{ padding: '4px 12px', fontSize: 10 }}
        >
          {recording ? 'STOP' : 'REC'}
        </button>
        {recording && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={styles.recDot} />
            <span style={styles.recLabel}>RECORDING</span>
          </div>
        )}
      </div>

      <div style={styles.divider} />

      {/* Replay section */}
      <div style={styles.section}>
        <span style={styles.label}>Replay</span>
        <input
          type="text"
          placeholder="latest"
          value={replayFile}
          onChange={(e) => setReplayFile(e.target.value)}
          style={{
            width: 100,
            padding: '4px 8px',
            background: '#18181b',
            border: '1px solid #27272a',
            borderRadius: 3,
            color: '#e4e4e7',
            fontSize: 10,
            fontFamily: 'var(--font-mono)',
            outline: 'none',
          }}
        />
        <button
          className="btn"
          onClick={handleReplay}
          style={{ padding: '4px 10px', fontSize: 10 }}
        >
          PLAY
        </button>
        <button
          className="btn"
          onClick={handleReplayStop}
          style={{ padding: '4px 10px', fontSize: 10 }}
        >
          STOP
        </button>
      </div>

      <div style={styles.divider} />

      {/* Snapshot */}
      <div style={styles.section}>
        <button
          className="btn btn-accent"
          onClick={handleSnapshot}
          style={{ padding: '4px 12px', fontSize: 10 }}
        >
          SNAPSHOT
        </button>
      </div>
    </div>
  );
}
