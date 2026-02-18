import React, { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = `ws://${window.location.hostname || 'localhost'}:8767`;

const VOTE_OPTIONS = [
  { id: 'sort_color', label: 'Sort by Color', icon: 'palette', color: '#3b82f6' },
  { id: 'sort_size', label: 'Sort by Size', icon: 'resize', color: '#a855f7' },
  { id: 'stack_tower', label: 'Stack Tower', icon: 'layers', color: '#22c55e' },
  { id: 'tetris_pack', label: 'Tetris Pack', icon: 'grid', color: '#eab308' },
  { id: 'chaos', label: 'Chaos Mode', icon: 'zap', color: '#ef4444' },
];

const styles = {
  page: {
    minHeight: '100vh',
    background: '#09090b',
    color: '#e4e4e7',
    fontFamily: "'SF Mono', 'Fira Code', monospace",
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    padding: '24px 16px',
    overflow: 'auto',
  },
  header: {
    textAlign: 'center',
    marginBottom: 32,
  },
  title: {
    fontSize: 20,
    fontWeight: 700,
    color: '#3b82f6',
    letterSpacing: '0.15em',
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 12,
    color: '#52525b',
  },
  connectionBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '4px 12px',
    borderRadius: 20,
    fontSize: 10,
    marginTop: 8,
    border: '1px solid #27272a',
  },
  votesContainer: {
    width: '100%',
    maxWidth: 400,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    marginBottom: 32,
  },
  voteButton: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px 20px',
    border: '1px solid #27272a',
    borderRadius: 8,
    background: '#111113',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    WebkitTapHighlightColor: 'transparent',
  },
  voteLabel: {
    fontSize: 14,
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  voteCount: {
    fontSize: 20,
    fontWeight: 700,
  },
  tiltSection: {
    width: '100%',
    maxWidth: 400,
    textAlign: 'center',
    padding: '20px 0',
    borderTop: '1px solid #27272a',
  },
  tiltLabel: {
    fontSize: 11,
    color: '#52525b',
    textTransform: 'uppercase',
    letterSpacing: '0.1em',
    marginBottom: 16,
  },
  tiltDisplay: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 32,
  },
  tiltAxis: {
    textAlign: 'center',
  },
  tiltValue: {
    fontSize: 24,
    fontWeight: 700,
    color: '#3b82f6',
    fontVariantNumeric: 'tabular-nums',
  },
  tiltAxisLabel: {
    fontSize: 10,
    color: '#52525b',
    marginTop: 4,
    textTransform: 'uppercase',
  },
  joystick: {
    width: 150,
    height: 150,
    borderRadius: '50%',
    border: '2px solid #27272a',
    background: '#111113',
    position: 'relative',
    margin: '16px auto',
    touchAction: 'none',
  },
  joystickDot: {
    width: 20,
    height: 20,
    borderRadius: '50%',
    background: '#3b82f6',
    boxShadow: '0 0 12px rgba(59,130,246,0.5)',
    position: 'absolute',
    transform: 'translate(-50%, -50%)',
    transition: 'all 0.1s ease',
  },
  backLink: {
    marginTop: 32,
    fontSize: 11,
    color: '#52525b',
    textDecoration: 'none',
    cursor: 'pointer',
  },
};

export default function Audience() {
  const [connected, setConnected] = useState(false);
  const [votes, setVotes] = useState({});
  const [selectedVote, setSelectedVote] = useState(null);
  const [tilt, setTilt] = useState({ alpha: 0, beta: 0, gamma: 0 });
  const [tiltEnabled, setTiltEnabled] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  // WebSocket connection
  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        console.log('[Audience] Connected to', WS_URL);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'vote_update') {
            setVotes(msg.votes || {});
          } else if (msg.type === 'vote_ack') {
            // Vote acknowledged
          }
        } catch {
          // Ignore
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        reconnectTimer.current = setTimeout(connect, 2000);
      };

      ws.onerror = () => ws.close();
    } catch {
      reconnectTimer.current = setTimeout(connect, 2000);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  // Device orientation for tilt control
  const enableTilt = async () => {
    try {
      // Request permission on iOS 13+
      if (typeof DeviceOrientationEvent !== 'undefined' &&
          typeof DeviceOrientationEvent.requestPermission === 'function') {
        const permission = await DeviceOrientationEvent.requestPermission();
        if (permission !== 'granted') {
          console.warn('Device orientation permission denied');
          return;
        }
      }

      setTiltEnabled(true);
    } catch (err) {
      console.warn('Tilt not available:', err);
    }
  };

  useEffect(() => {
    if (!tiltEnabled) return;

    const handleOrientation = (event) => {
      const alpha = event.alpha || 0;
      const beta = event.beta || 0;
      const gamma = event.gamma || 0;

      setTilt({ alpha, beta, gamma });

      // Send tilt data to server
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'tilt',
          alpha: Math.round(alpha * 10) / 10,
          beta: Math.round(beta * 10) / 10,
          gamma: Math.round(gamma * 10) / 10,
        }));
      }
    };

    window.addEventListener('deviceorientation', handleOrientation);
    return () => window.removeEventListener('deviceorientation', handleOrientation);
  }, [tiltEnabled]);

  // Send vote
  const handleVote = (optionId) => {
    setSelectedVote(optionId);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'vote', option: optionId }));
    }
  };

  // Map tilt to joystick position
  const joystickX = 50 + Math.max(-50, Math.min(50, tilt.gamma)) / 50 * 45;
  const joystickY = 50 + Math.max(-50, Math.min(50, tilt.beta)) / 50 * 45;

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <div style={styles.title}>ALICE</div>
        <div style={styles.subtitle}>Audience Control Panel</div>
        <div style={{
          ...styles.connectionBadge,
          borderColor: connected ? '#22c55e30' : '#ef444430',
          color: connected ? '#22c55e' : '#ef4444',
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: connected ? '#22c55e' : '#ef4444',
          }} />
          {connected ? 'CONNECTED' : 'CONNECTING...'}
        </div>
      </div>

      {/* Vote Buttons */}
      <div style={styles.votesContainer}>
        {VOTE_OPTIONS.map((option) => {
          const isSelected = selectedVote === option.id;
          const count = votes[option.id] || 0;
          return (
            <button
              key={option.id}
              onClick={() => handleVote(option.id)}
              style={{
                ...styles.voteButton,
                borderColor: isSelected ? option.color : '#27272a',
                background: isSelected ? `${option.color}15` : '#111113',
                transform: isSelected ? 'scale(1.02)' : 'scale(1)',
              }}
            >
              <span style={{ ...styles.voteLabel, color: isSelected ? option.color : '#a1a1aa' }}>
                {option.label}
              </span>
              <span style={{ ...styles.voteCount, color: option.color }}>
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Tilt Control */}
      <div style={styles.tiltSection}>
        <div style={styles.tiltLabel}>Tilt Control</div>

        {!tiltEnabled ? (
          <button
            onClick={enableTilt}
            style={{
              padding: '12px 24px',
              border: '1px solid #3b82f6',
              borderRadius: 6,
              background: 'rgba(59,130,246,0.1)',
              color: '#3b82f6',
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              cursor: 'pointer',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}
          >
            Enable Tilt
          </button>
        ) : (
          <>
            {/* Virtual joystick */}
            <div style={styles.joystick}>
              {/* Crosshair */}
              <div style={{
                position: 'absolute', top: '50%', left: 0, right: 0,
                height: 1, background: '#27272a',
              }} />
              <div style={{
                position: 'absolute', left: '50%', top: 0, bottom: 0,
                width: 1, background: '#27272a',
              }} />
              {/* Dot */}
              <div style={{
                ...styles.joystickDot,
                left: `${joystickX}%`,
                top: `${joystickY}%`,
              }} />
            </div>

            {/* Tilt values */}
            <div style={styles.tiltDisplay}>
              <div style={styles.tiltAxis}>
                <div style={styles.tiltValue}>{tilt.beta.toFixed(1)}</div>
                <div style={styles.tiltAxisLabel}>Pitch</div>
              </div>
              <div style={styles.tiltAxis}>
                <div style={styles.tiltValue}>{tilt.gamma.toFixed(1)}</div>
                <div style={styles.tiltAxisLabel}>Roll</div>
              </div>
              <div style={styles.tiltAxis}>
                <div style={styles.tiltValue}>{tilt.alpha.toFixed(1)}</div>
                <div style={styles.tiltAxisLabel}>Yaw</div>
              </div>
            </div>
          </>
        )}
      </div>

      <a href="#/" style={styles.backLink}>
        Back to Dashboard
      </a>
    </div>
  );
}
