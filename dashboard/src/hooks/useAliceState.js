import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = `ws://${window.location.hostname || 'localhost'}:8765`;

const DEFAULT_STATE = {
  mode: 'IDLE',
  blocks: [],
  joints: [0, 0, 0, 0, 0, 0],
  gripperOpen: true,
  sortProgress: 0,
  tetrisProgress: 0,
  cameraHealth: 'unknown',
  recording: false,
  fps: 0,
  uptime: 0,
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
        console.log('[useAliceState] Connected to', WS_URL);
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

          if (msg.type === 'state_sync') {
            setState((prev) => ({
              ...prev,
              mode: msg.mode ?? prev.mode,
              blocks: msg.blocks ?? prev.blocks,
              joints: msg.joints ?? prev.joints,
              gripperOpen: msg.gripper_open ?? prev.gripperOpen,
              sortProgress: msg.sort_progress ?? prev.sortProgress,
              tetrisProgress: msg.tetris_progress ?? prev.tetrisProgress,
              cameraHealth: msg.camera_health ?? prev.cameraHealth,
              recording: msg.recording ?? prev.recording,
              fps: msg.fps ?? prev.fps,
              uptime: msg.uptime ?? prev.uptime,
            }));
          } else if (msg.type === 'heartbeat') {
            setState((prev) => ({
              ...prev,
              lastHeartbeat: Date.now(),
              uptime: msg.uptime ?? prev.uptime,
            }));
          }
        } catch (err) {
          // Ignore parse errors for non-JSON messages
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        console.log('[useAliceState] Disconnected, reconnecting in 2s...');
        reconnectTimer.current = setTimeout(connect, 2000);
      };

      ws.onerror = (err) => {
        console.warn('[useAliceState] WebSocket error:', err);
        ws.close();
      };
    } catch (err) {
      console.warn('[useAliceState] Connection failed:', err);
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

  const sendCommand = useCallback((command, payload = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: command, ...payload }));
    } else {
      console.warn('[useAliceState] Cannot send, not connected');
    }
  }, []);

  return { state, connected, sendCommand };
}
