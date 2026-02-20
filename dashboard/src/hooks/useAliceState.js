import { useState, useEffect, useCallback } from 'react';
import { useAliceSocket } from './AliceSocketProvider.jsx';

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
  const { connected, send, addTextListener, removeTextListener } = useAliceSocket();
  const [state, setState] = useState(DEFAULT_STATE);

  useEffect(() => {
    const handler = (raw) => {
      try {
        const msg = JSON.parse(raw);

        if (msg.type === 'state_sync' && msg.state) {
          setState((prev) => ({ ...prev, ...msg.state, lastHeartbeat: Date.now() }));
        } else if (msg.type === 'heartbeat') {
          setState((prev) => ({ ...prev, lastHeartbeat: Date.now() }));
        } else if (msg.type === 'mode_switched') {
          setState((prev) => ({ ...prev, mode: msg.mode }));
        }
      } catch {
        // Ignore non-JSON text messages
      }
    };

    addTextListener(handler);
    return () => removeTextListener(handler);
  }, [addTextListener, removeTextListener]);

  const sendCommand = useCallback((command, payload = {}) => {
    send(JSON.stringify({ command, ...payload }));
  }, [send]);

  const updateState = useCallback((patch) => {
    setState((prev) => ({ ...prev, ...patch }));
  }, []);

  return { state, connected, sendCommand, updateState };
}
