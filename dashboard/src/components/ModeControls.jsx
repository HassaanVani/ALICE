import React from 'react';

const MODES = [
  { id: 'idle', label: 'Idle', color: '#52525b', description: 'Standby mode' },
  { id: 'chimp', label: 'Sort', color: '#3b82f6', description: 'ChimpSort challenge' },
  { id: 'tetris', label: 'Tetris', color: '#a855f7', description: 'Tetris packing' },
  { id: 'puppeteer', label: 'Puppet', color: '#22c55e', description: 'Arm teleoperation' },
  { id: 'calibrate', label: 'Calibrate', color: '#eab308', description: 'Arm calibration' },
];

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  button: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 12px',
    border: '1px solid #27272a',
    borderRadius: 4,
    background: '#111113',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    fontFamily: 'var(--font-mono)',
  },
  modeLabel: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  modeDesc: {
    fontSize: 9,
    color: '#52525b',
  },
  activeDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
  },
};

export default function ModeControls({ currentMode, sendCommand }) {
  const handleSwitch = (modeId) => {
    sendCommand('switch_mode', { mode: modeId });
  };

  return (
    <div style={styles.container}>
      {MODES.map((mode) => {
        const isActive = currentMode === mode.id;
        return (
          <button
            key={mode.id}
            onClick={() => handleSwitch(mode.id)}
            style={{
              ...styles.button,
              borderColor: isActive ? mode.color : '#27272a',
              background: isActive ? `${mode.color}15` : '#111113',
            }}
            onMouseEnter={(e) => {
              if (!isActive) e.currentTarget.style.borderColor = mode.color + '80';
            }}
            onMouseLeave={(e) => {
              if (!isActive) e.currentTarget.style.borderColor = '#27272a';
            }}
          >
            <div>
              <div style={{ ...styles.modeLabel, color: isActive ? mode.color : '#a1a1aa' }}>
                {mode.label}
              </div>
              <div style={styles.modeDesc}>{mode.description}</div>
            </div>
            <div
              style={{
                ...styles.activeDot,
                background: isActive ? mode.color : 'transparent',
                border: `1px solid ${isActive ? mode.color : '#3f3f46'}`,
                boxShadow: isActive ? `0 0 8px ${mode.color}` : 'none',
              }}
            />
          </button>
        );
      })}
    </div>
  );
}
