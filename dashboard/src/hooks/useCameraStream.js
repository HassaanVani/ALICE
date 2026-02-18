import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = `ws://${window.location.hostname || 'localhost'}:8765`;

export function useCameraStream() {
  const [cameraConnected, setCameraConnected] = useState(false);
  const frameRef = useRef(null); // Holds the latest ImageBitmap or Blob URL
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(WS_URL);
      ws.binaryType = 'blob';
      wsRef.current = ws;

      ws.onopen = () => {
        setCameraConnected(true);
        console.log('[useCameraStream] Connected');
        // Request camera stream from server (server expects "command" field)
        ws.send(JSON.stringify({ command: 'stream_camera' }));
      };

      ws.onmessage = (event) => {
        if (event.data instanceof Blob) {
          // Revoke previous URL to prevent memory leak
          if (frameRef.current) {
            URL.revokeObjectURL(frameRef.current);
          }
          frameRef.current = URL.createObjectURL(event.data);
        } else if (typeof event.data === 'string') {
          // Handle JSON messages (e.g., camera frame as base64)
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'camera_frame' && (msg.jpeg_b64 || msg.data)) {
              if (frameRef.current) {
                URL.revokeObjectURL(frameRef.current);
              }
              // Convert base64 JPEG to blob URL
              const binary = atob(msg.jpeg_b64 || msg.data);
              const array = new Uint8Array(binary.length);
              for (let i = 0; i < binary.length; i++) {
                array[i] = binary.charCodeAt(i);
              }
              const blob = new Blob([array], { type: 'image/jpeg' });
              frameRef.current = URL.createObjectURL(blob);
            }
          } catch {
            // Not a camera message
          }
        }
      };

      ws.onclose = () => {
        setCameraConnected(false);
        wsRef.current = null;
        console.log('[useCameraStream] Disconnected, reconnecting...');
        reconnectTimer.current = setTimeout(connect, 2000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (err) {
      reconnectTimer.current = setTimeout(connect, 2000);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
      if (frameRef.current) URL.revokeObjectURL(frameRef.current);
    };
  }, [connect]);

  return { frameRef, cameraConnected };
}
