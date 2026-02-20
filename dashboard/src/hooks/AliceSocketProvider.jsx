import React, { createContext, useContext, useRef, useState, useEffect, useCallback } from 'react';
import { TENSOR_WS_URL } from '../ws-config.js';

const AliceSocketContext = createContext(null);

/**
 * Shared WebSocket provider — a single connection to the ALICE tensor server.
 * All hooks (state, tensors, camera) share this instead of opening duplicates.
 */
export function AliceSocketProvider({ children }) {
  const wsRef = useRef(null);
  const [connected, setConnected] = useState(false);
  const textListenersRef = useRef(new Set());
  const binaryListenersRef = useRef(new Set());
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(TENSOR_WS_URL);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        if (reconnectTimer.current) {
          clearTimeout(reconnectTimer.current);
          reconnectTimer.current = null;
        }
      };

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          for (const cb of binaryListenersRef.current) {
            try { cb(event.data); } catch { /* listener error */ }
          }
        } else if (typeof event.data === 'string') {
          for (const cb of textListenersRef.current) {
            try { cb(event.data); } catch { /* listener error */ }
          }
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

  const send = useCallback((data) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data));
    }
  }, []);

  const addTextListener = useCallback((cb) => { textListenersRef.current.add(cb); }, []);
  const removeTextListener = useCallback((cb) => { textListenersRef.current.delete(cb); }, []);
  const addBinaryListener = useCallback((cb) => { binaryListenersRef.current.add(cb); }, []);
  const removeBinaryListener = useCallback((cb) => { binaryListenersRef.current.delete(cb); }, []);

  return (
    <AliceSocketContext.Provider value={{
      connected,
      send,
      addTextListener,
      removeTextListener,
      addBinaryListener,
      removeBinaryListener,
    }}>
      {children}
    </AliceSocketContext.Provider>
  );
}

export function useAliceSocket() {
  const ctx = useContext(AliceSocketContext);
  if (!ctx) throw new Error('useAliceSocket must be used within <AliceSocketProvider>');
  return ctx;
}
