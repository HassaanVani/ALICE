import { useState, useEffect, useRef } from 'react';
import { useAliceSocket } from './AliceSocketProvider.jsx';

export function useCameraStream() {
  const { connected, send, addTextListener, removeTextListener } = useAliceSocket();
  const [cameraConnected, setCameraConnected] = useState(false);
  const frameRef = useRef(null);

  // Request camera stream once connected
  useEffect(() => {
    if (connected) {
      send(JSON.stringify({ command: 'stream_camera' }));
      setCameraConnected(true);
    } else {
      setCameraConnected(false);
    }
  }, [connected, send]);

  useEffect(() => {
    const handler = (raw) => {
      try {
        const msg = JSON.parse(raw);
        if (msg.type === 'camera_frame' && (msg.jpeg_b64 || msg.data)) {
          if (frameRef.current) {
            URL.revokeObjectURL(frameRef.current);
          }
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
    };

    addTextListener(handler);
    return () => {
      removeTextListener(handler);
      if (frameRef.current) URL.revokeObjectURL(frameRef.current);
    };
  }, [addTextListener, removeTextListener]);

  return { frameRef, cameraConnected };
}
