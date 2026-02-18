import React from 'react';

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    fontSize: 11,
    fontFamily: 'var(--font-mono)',
  },
  row: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '4px 0',
    borderBottom: '1px solid #1a1a1e',
  },
  label: {
    color: '#a1a1aa',
    fontSize: 10,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  value: {
    color: '#e4e4e7',
    fontSize: 11,
    fontWeight: 500,
  },
  progressContainer: {
    width: '100%',
    height: 4,
    background: '#18181b',
    borderRadius: 2,
    overflow: 'hidden',
    marginTop: 4,
  },
  sectionTitle: {
    fontSize: 9,
    color: '#52525b',
    textTransform: 'uppercase',
    letterSpacing: '0.1em',
    marginTop: 6,
    marginBottom: 2,
  },
};

function StatusDot({ status }) {
  const colorMap = {
    ok: '#22c55e',
    healthy: '#22c55e',
    connected: '#22c55e',
    warning: '#eab308',
    degraded: '#eab308',
    error: '#ef4444',
    disconnected: '#ef4444',
    unknown: '#52525b',
  };
  const color = colorMap[status?.toLowerCase()] || colorMap.unknown;

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: color,
          boxShadow: `0 0 6px ${color}`,
          display: 'inline-block',
        }}
      />
      <span style={{ color, fontSize: 10, textTransform: 'uppercase' }}>
        {status || 'unknown'}
      </span>
    </span>
  );
}

function ProgressBar({ value, max = 100, color = '#3b82f6' }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div style={styles.progressContainer}>
      <div
        style={{
          width: `${pct}%`,
          height: '100%',
          background: color,
          borderRadius: 2,
          transition: 'width 0.3s ease',
        }}
      />
    </div>
  );
}

function formatUptime(seconds) {
  if (!seconds) return '0s';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function SystemState({ state, connected, cameraConnected }) {
  return (
    <div style={styles.container}>
      {/* Connection */}
      <div style={styles.sectionTitle}>Connection</div>
      <div style={styles.row}>
        <span style={styles.label}>WebSocket</span>
        <StatusDot status={connected ? 'connected' : 'disconnected'} />
      </div>
      <div style={styles.row}>
        <span style={styles.label}>Camera</span>
        <StatusDot status={cameraConnected ? 'connected' : 'disconnected'} />
      </div>

      {/* System */}
      <div style={styles.sectionTitle}>System</div>
      <div style={styles.row}>
        <span style={styles.label}>Mode</span>
        <span style={{
          ...styles.value,
          color: state.mode === 'IDLE' ? '#52525b'
            : state.mode === 'SORT' ? '#3b82f6'
            : state.mode === 'TETRIS' ? '#a855f7'
            : state.mode === 'AUDIENCE' ? '#22c55e'
            : '#e4e4e7',
        }}>
          {state.mode || 'IDLE'}
        </span>
      </div>
      <div style={styles.row}>
        <span style={styles.label}>Camera Health</span>
        <StatusDot status={state.cameraHealth || 'unknown'} />
      </div>
      <div style={styles.row}>
        <span style={styles.label}>FPS</span>
        <span style={styles.value}>{state.fps || 0}</span>
      </div>
      <div style={styles.row}>
        <span style={styles.label}>Uptime</span>
        <span style={styles.value}>{formatUptime(state.uptime)}</span>
      </div>

      {/* Progress */}
      <div style={styles.sectionTitle}>Task Progress</div>
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
          <span style={styles.label}>Sort</span>
          <span style={{ ...styles.value, fontSize: 10 }}>{state.sortProgress || 0}%</span>
        </div>
        <ProgressBar value={state.sortProgress || 0} color="#3b82f6" />
      </div>
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
          <span style={styles.label}>Tetris</span>
          <span style={{ ...styles.value, fontSize: 10 }}>{state.tetrisProgress || 0}%</span>
        </div>
        <ProgressBar value={state.tetrisProgress || 0} color="#a855f7" />
      </div>

      {/* Recording */}
      <div style={styles.row}>
        <span style={styles.label}>Recording</span>
        <span style={{
          ...styles.value,
          color: state.recording ? '#ef4444' : '#52525b',
        }}>
          {state.recording ? 'REC' : 'OFF'}
          {state.recording && (
            <span style={{
              display: 'inline-block',
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: '#ef4444',
              marginLeft: 6,
              animation: 'pulse 1s ease-in-out infinite',
            }} />
          )}
        </span>
      </div>
    </div>
  );
}
