import { useState, useEffect, useRef, useCallback } from 'react';
import { TENSOR_WS_URL } from '../ws-config.js';

/**
 * Decodes binary activation data from the ALICE backend.
 *
 * Binary protocol (matches server.py and Haptix TensorBridge):
 *   [4 bytes: num_layers (uint32 LE)]
 *   For each layer:
 *     [4 bytes: name_length (uint32 LE)]
 *     [N bytes: layer_name (UTF-8)]
 *     [4 bytes: num_values (uint32 LE)]
 *     [num_values * 4 bytes: float32 LE values]
 */
function decodeBinaryActivations(buffer) {
  const view = new DataView(buffer);
  const layers = [];
  let offset = 0;

  try {
    if (buffer.byteLength < 4) return layers;

    const numLayers = view.getUint32(offset, true);
    offset += 4;

    for (let i = 0; i < numLayers; i++) {
      const nameLen = view.getUint32(offset, true);
      offset += 4;

      const nameBytes = new Uint8Array(buffer, offset, nameLen);
      const name = new TextDecoder().decode(nameBytes);
      offset += nameLen;

      const numValues = view.getUint32(offset, true);
      offset += 4;

      const values = [];
      for (let j = 0; j < numValues; j++) {
        values.push(view.getFloat32(offset, true));
        offset += 4;
      }

      layers.push({ name, values });
    }
  } catch {
    // Malformed binary frame — skip silently
  }

  return layers;
}

export function useTensorStream() {
  const [activations, setActivations] = useState([]);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(TENSOR_WS_URL);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onopen = () => {
        // Server auto-broadcasts tensors to all clients — no subscription needed
      };

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          const layers = decodeBinaryActivations(event.data);
          if (layers.length > 0) {
            setActivations(layers);
          }
        }
        // Ignore text messages (handled by useAliceState)
      };

      ws.onclose = () => {
        wsRef.current = null;
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (err) {
      reconnectTimer.current = setTimeout(connect, 3000);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  return { activations };
}
