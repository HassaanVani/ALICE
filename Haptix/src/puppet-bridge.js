export class PuppetBridge {
    constructor(serverUrl = 'ws://localhost:8766') {
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
            onError: null,
            onStateSync: null,
            onHeartbeat: null
        };
        this.lastState = null;
        this.lastHeartbeat = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this._autoReconnect = true;

        this.PINCH_THRESHOLD = 0.08;
        this.FIST_THRESHOLD = 0.15;
    }

    connect() {
        try {
            this.socket = new WebSocket(this.serverUrl);

            this.socket.onopen = () => {
                this.connected = true;
                this.callbacks.onConnect?.();
            };

            this.socket.onclose = () => {
                this.connected = false;
                this.stopStreaming();
                this.callbacks.onDisconnect?.();
                this._attemptReconnect();
            };

            this.socket.onerror = (error) => {
                this.callbacks.onError?.(error);
            };

            this.socket.onmessage = (event) => {
                this._handleMessage(event.data);
            };
        } catch (e) {
            this.callbacks.onError?.(e);
        }
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
                if (!this.connected && this._autoReconnect) {
                    this.connect();
                }
            }, 2000 * this.reconnectAttempts);
        }
    }

    _handleMessage(data) {
        try {
            const msg = JSON.parse(data);
            if (msg.type === 'arm_position') {
                this.callbacks.onArmUpdate?.(msg);
            } else if (msg.type === 'state_sync') {
                this.lastState = msg.state;
                this.callbacks.onStateSync?.(msg.state);
            } else if (msg.type === 'heartbeat') {
                this.lastHeartbeat = msg.timestamp;
                this.callbacks.onHeartbeat?.(msg.timestamp);
            }
        } catch (e) { }
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

        const handSpan = Math.sqrt(
            (middleTip.x - wrist.x) ** 2 +
            (middleTip.y - wrist.y) ** 2
        );

        const normalizedDepth = Math.max(0, Math.min(1, (0.3 - handSpan) / 0.2));
        return normalizedDepth;
    }

    _updateGestures(landmarks) {
        const thumb = landmarks[4];
        const index = landmarks[8];

        const pinchDist = Math.sqrt(
            (thumb.x - index.x) ** 2 +
            (thumb.y - index.y) ** 2
        );

        this.isPinching = pinchDist < this.PINCH_THRESHOLD;

        const fingerTips = [8, 12, 16, 20];
        const palm = landmarks[0];
        let avgDist = 0;

        for (const tipIdx of fingerTips) {
            const tip = landmarks[tipIdx];
            avgDist += Math.sqrt(
                (tip.x - palm.x) ** 2 +
                (tip.y - palm.y) ** 2
            );
        }
        avgDist /= fingerTips.length;
        this.isFist = avgDist < this.FIST_THRESHOLD;
    }

    startStreaming() {
        if (this.streaming || !this.connected) return;

        this.streaming = true;
        const interval = 1000 / this.targetFps;

        this.streamInterval = setInterval(() => {
            this._sendHandData();
        }, interval);
    }

    stopStreaming() {
        this.streaming = false;
        if (this.streamInterval) {
            clearInterval(this.streamInterval);
            this.streamInterval = null;
        }
    }

    _sendHandData() {
        if (!this.connected || !this.socket || !this.lastLandmarks) return;

        const data = {
            type: 'hand_position',
            timestamp: Date.now(),
            position: this.handPosition,
            gestures: {
                pinching: this.isPinching,
                fist: this.isFist
            },
            landmarks: this.lastLandmarks.map(lm => ({
                x: lm.x,
                y: lm.y,
                z: lm.z || 0
            }))
        };

        this.socket.send(JSON.stringify(data));
    }

    sendCommand(command, params = {}) {
        if (!this.connected || !this.socket) return;

        const msg = JSON.stringify({ command, ...params });
        this.socket.send(msg);
    }

    startTeaching(name) {
        this.sendCommand('start_teaching', { name });
    }

    stopTeaching() {
        this.sendCommand('stop_teaching');
    }

    playMotion(name) {
        this.sendCommand('play_motion', { name });
    }

    setSpeed(speed) {
        this.sendCommand('set_speed', { speed });
    }

    onConnect(callback) {
        this.callbacks.onConnect = callback;
        return this;
    }

    onDisconnect(callback) {
        this.callbacks.onDisconnect = callback;
        return this;
    }

    onArmUpdate(callback) {
        this.callbacks.onArmUpdate = callback;
        return this;
    }

    onError(callback) {
        this.callbacks.onError = callback;
        return this;
    }

    onStateSync(callback) {
        this.callbacks.onStateSync = callback;
        return this;
    }

    onHeartbeat(callback) {
        this.callbacks.onHeartbeat = callback;
        return this;
    }
}
