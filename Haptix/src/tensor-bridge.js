export class TensorBridge {
    constructor(serverUrl = 'ws://localhost:8765') {
        this.serverUrl = serverUrl;
        this.socket = null;
        this.connected = false;
        this.callbacks = {
            onActivation: null,
            onConnect: null,
            onDisconnect: null,
            onError: null,
            onStateSync: null,
            onHeartbeat: null
        };
        this.lastState = null;
        this.lastHeartbeat = null;
        this.layerData = new Map();
        this.frozen = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
    }

    connect() {
        try {
            this.socket = new WebSocket(this.serverUrl);
            this.socket.binaryType = 'arraybuffer';

            this.socket.onopen = () => {
                this.connected = true;
                this.reconnectAttempts = 0;
                this.callbacks.onConnect?.();
            };

            this.socket.onclose = () => {
                this.connected = false;
                this.callbacks.onDisconnect?.();
                this._attemptReconnect();
            };

            this.socket.onerror = (error) => {
                this.callbacks.onError?.(error);
            };

            this.socket.onmessage = (event) => {
                this._processMessage(event.data);
            };
        } catch (e) {
            this.callbacks.onError?.(e);
        }
    }

    disconnect() {
        this.maxReconnectAttempts = 0;
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.connected = false;
    }

    _attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            setTimeout(() => this.connect(), 2000);
        }
    }

    _processMessage(data) {
        if (data instanceof ArrayBuffer) {
            this._parseBinaryActivations(data);
        } else {
            try {
                const json = JSON.parse(data);
                if (json.type === 'activation') {
                    this._processJsonActivation(json);
                } else if (json.type === 'state_sync') {
                    this.lastState = json.state;
                    this.callbacks.onStateSync?.(json.state);
                } else if (json.type === 'heartbeat') {
                    this.lastHeartbeat = json.timestamp;
                    this.callbacks.onHeartbeat?.(json.timestamp);
                }
            } catch (e) { }
        }
    }

    _parseBinaryActivations(buffer) {
        const view = new DataView(buffer);
        let offset = 0;

        const layerCount = view.getUint32(offset, true);
        offset += 4;

        for (let i = 0; i < layerCount; i++) {
            const nameLen = view.getUint32(offset, true);
            offset += 4;

            const nameBytes = new Uint8Array(buffer, offset, nameLen);
            const name = new TextDecoder().decode(nameBytes);
            offset += nameLen;

            const dataLen = view.getUint32(offset, true);
            offset += 4;

            const values = new Float32Array(buffer, offset, dataLen);
            offset += dataLen * 4;

            this.layerData.set(name, values);
        }

        this.callbacks.onActivation?.(this.layerData);
    }

    _processJsonActivation(json) {
        for (const [name, values] of Object.entries(json.activations)) {
            this.layerData.set(name, new Float32Array(values));
        }
        this.callbacks.onActivation?.(this.layerData);
    }

    sendCommand(command, params = {}) {
        if (!this.connected || !this.socket) return;

        const message = JSON.stringify({ command, ...params });
        this.socket.send(message);
    }

    toggleFreeze() {
        this.frozen = !this.frozen;
        this.sendCommand('freeze', { frozen: this.frozen });
        return this.frozen;
    }

    selectLayer(layerName) {
        this.sendCommand('select_layer', { layer: layerName });
    }

    setRefreshRate(fps) {
        this.sendCommand('set_fps', { fps });
    }

    onActivation(callback) {
        this.callbacks.onActivation = callback;
        return this;
    }

    onConnect(callback) {
        this.callbacks.onConnect = callback;
        return this;
    }

    onDisconnect(callback) {
        this.callbacks.onDisconnect = callback;
        return this;
    }

    onError(callback) {
        this.callbacks.onError = callback;
        return this;
    }

    getLayerData(name) {
        return this.layerData.get(name);
    }

    getLayerNames() {
        return Array.from(this.layerData.keys());
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
