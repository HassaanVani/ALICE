import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = `ws://${window.location.hostname || 'localhost'}:8765`;

const DEFAULT_STATE = {
  mode: 'idle',
  arm_position: [90, 90, 90, 90, 90],
  arm_state: 'idle',
  gripper_position: 0,
  cameras: { overhead: 'unknown', front: 'unknown' },
  sort_state: 'idle',
  sort_move_count: 0,
  tetris_score: 0,
  tetris_lines: 0,
  tetris_level: 1,
  tetris_game_over: false,
  tetris_board: [],
  puppeteer_state: 'idle',
  puppeteer_recording: false,
  calibration_points: 0,
  calibration_ready: false,
  detected_blocks: [],
  timestamp: 0,
  lastHeartbeat: null,
};

export function useAliceState() {
  const [state, setState] = useState(DEFAULT_STATE);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        if (reconnectTimer.current) {
          clearTimeout(reconnectTimer.current);
          reconnectTimer.current = null;
        }
      };

      ws.onmessage = (event) => {
        try {
          // Skip binary messages (handled by useTensorStream)
          if (typeof event.data !== 'string') return;

          const msg = JSON.parse(event.data);

          if (msg.type === 'state_sync' && msg.state) {
            setState((prev) => ({ ...prev, ...msg.state, lastHeartbeat: Date.now() }));
          } else if (msg.type === 'heartbeat') {
            setState((prev) => ({ ...prev, lastHeartbeat: Date.now() }));
          } else if (msg.type === 'mode_switched') {
            setState((prev) => ({ ...prev, mode: msg.mode }));
          } else if (msg.type === 'error') {
            console.error('[ALICE]', msg.detail || 'Unknown error');
          }
        } catch {
          // Ignore parse errors for non-JSON messages
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

  // Server expects { command: "...", ...params }
  const sendCommand = useCallback((command, payload = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command, ...payload }));
    }
  }, []);

  const updateState = useCallback((patch) => {
    setState((prev) => ({ ...prev, ...patch }));
  }, []);

  return { state, connected, sendCommand, updateState };
}
