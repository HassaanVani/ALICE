/**
 * Puppet bridge — sends hand pose data to ALICE's puppet server.
 * Receives arm position updates back for visualization.
 */

import { PUPPET_WS_URL } from '../ws-config.js';

export class PuppetBridge {
  constructor(serverUrl = PUPPET_WS_URL) {
    this.serverUrl = serverUrl;
    this.socket = null;
    this.connected = false;
    this.streaming = false;
    this.streamInterval = null;
    this.targetFps = 30;

    this.lastLandmarks = null;
    this.handPosition = { x: 0.5, y: 0.5, z: 0.5 };
    this.isPinching = false;
    this.isFist = false;

    this.callbacks = {
      onConnect: null,
      onDisconnect: null,
      onArmUpdate: null,
      onPuppetState: null,
    };
    this.puppetState = 'idle';
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this._autoReconnect = true;
  }

  connect() {
    try {
      this.socket = new WebSocket(this.serverUrl);

      this.socket.onopen = () => {
        this.connected = true;
        this.reconnectAttempts = 0;
        this.callbacks.onConnect?.();
      };

      this.socket.onclose = () => {
        this.connected = false;
        this.stopStreaming();
        this.callbacks.onDisconnect?.();
        this._attemptReconnect();
      };

      this.socket.onerror = () => {};

      this.socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'arm_position') {
            this.callbacks.onArmUpdate?.(msg);
          } else if (msg.type === 'puppet_state') {
            this.puppetState = msg.state;
            this.callbacks.onPuppetState?.(msg.state);
          }
        } catch { /* non-JSON */ }
      };
    } catch { /* connection error */ }
  }

  disconnect() {
    this._autoReconnect = false;
    this.stopStreaming();
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.connected = false;
  }

  _attemptReconnect() {
    if (!this._autoReconnect) return;
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => {
        if (!this.connected && this._autoReconnect) this.connect();
      }, 2000 * this.reconnectAttempts);
    }
  }

  updateLandmarks(landmarks) {
    if (!landmarks || landmarks.length < 21) {
      this.lastLandmarks = null;
      return;
    }
    this.lastLandmarks = landmarks;

    const wrist = landmarks[0];
    const middleMcp = landmarks[9];
    this.handPosition = {
      x: (wrist.x + middleMcp.x) / 2,
      y: (wrist.y + middleMcp.y) / 2,
      z: this._estimateDepth(landmarks)
    };
    this._updateGestures(landmarks);
  }

  _estimateDepth(landmarks) {
    const wrist = landmarks[0];
    const middleTip = landmarks[12];
    const span = Math.sqrt((middleTip.x - wrist.x) ** 2 + (middleTip.y - wrist.y) ** 2);
    return Math.max(0, Math.min(1, (0.3 - span) / 0.2));
  }

  _updateGestures(landmarks) {
    const thumb = landmarks[4];
    const index = landmarks[8];
    const pinchDist = Math.sqrt((thumb.x - index.x) ** 2 + (thumb.y - index.y) ** 2);
    this.isPinching = pinchDist < 0.08;

    const palm = landmarks[0];
    let avg = 0;
    for (const i of [8, 12, 16, 20]) {
      const t = landmarks[i];
      avg += Math.sqrt((t.x - palm.x) ** 2 + (t.y - palm.y) ** 2);
    }
    this.isFist = avg / 4 < 0.15;
  }

  startStreaming() {
    if (this.streaming || !this.connected) return;
    this.streaming = true;
    this.streamInterval = setInterval(() => this._send(), 1000 / this.targetFps);
  }

  stopStreaming() {
    this.streaming = false;
    if (this.streamInterval) {
      clearInterval(this.streamInterval);
      this.streamInterval = null;
    }
  }

  _send() {
    if (!this.connected || !this.socket || !this.lastLandmarks) return;
    this.socket.send(JSON.stringify({
      type: 'hand_position',
      timestamp: Date.now(),
      position: this.handPosition,
      gestures: { pinching: this.isPinching, fist: this.isFist },
      landmarks: this.lastLandmarks.map(lm => ({ x: lm.x, y: lm.y, z: lm.z || 0 }))
    }));
  }

  sendCommand(command, params = {}) {
    if (!this.connected || !this.socket) return;
    this.socket.send(JSON.stringify({ command, ...params }));
  }
}
