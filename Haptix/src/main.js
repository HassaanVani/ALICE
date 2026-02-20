import './styles.css';
import { HandTracker } from './hand-tracker.js';
import { GestureController } from './gesture-controller.js';
import { SceneManager } from './scene-manager.js';
import { SceneRegistry } from './scene-registry.js';
import { TensorBridge } from './tensor-bridge.js';
import { PuppetBridge } from './puppet-bridge.js';

class App {
    constructor() {
        this.sceneManager = null;
        this.handTracker = null;
        this.gestureController = null;
        this.currentScene = 'solar-system';
        this.tensorBridge = null;
        this.glassBrainScene = null;
        this.puppetBridge = null;
        this.puppetModeActive = false;
        this.registry = new SceneRegistry();
        this.roboticArmScene = null;
        this._previousScene = null;
    }

    async init() {
        const canvas = document.getElementById('scene-canvas');
        const video = document.getElementById('webcam');
        const handCanvas = document.getElementById('hand-canvas');
        const loadingOverlay = document.getElementById('loading-overlay');
        const gestureIndicator = document.getElementById('gesture-indicator');
        const gestureText = document.getElementById('gesture-text');

        this.sceneManager = new SceneManager(canvas);
        this.tensorBridge = new TensorBridge();

        // Discover and register all scenes dynamically
        await this.registry.discoverScenes();
        for (const scene of this.registry.getAll()) {
            if (scene.id === 'glass-brain') {
                this.sceneManager.registerScene(scene.id, (THREE) => {
                    this.glassBrainScene = scene.factory(THREE, this.tensorBridge);
                    return this.glassBrainScene;
                }, scene.metadata);
            } else if (scene.id === 'robotic-arm') {
                // Capture arm scene instance for live updates
                this.sceneManager.registerScene(scene.id, (THREE) => {
                    this.roboticArmScene = scene.factory(THREE);
                    return this.roboticArmScene;
                }, scene.metadata);
            } else {
                this.sceneManager.registerScene(scene.id, scene.factory, scene.metadata);
            }
        }

        // Build dropdown dynamically
        const dropdownMenu = document.getElementById('dropdown-menu');
        if (dropdownMenu) {
            this.registry.buildDropdown(dropdownMenu);
        }

        this.gestureController = new GestureController();
        this.cursorData = { visible: false, clicking: false, x: 0, y: 0 };
        const handCursor = document.getElementById('hand-cursor');

        this.gestureController
            .onZoom((delta) => {
                this.sceneManager.zoom(delta);
            })
            .onRotate((deltaX, deltaY) => {
                this.sceneManager.rotate(deltaX, deltaY);
            })
            .onPan((deltaX, deltaY) => {
                this.sceneManager.pan(deltaX, deltaY);
            })
            .onRecenter(() => {
                this.sceneManager.recenter();
            })
            .onCursor((data) => {
                this.cursorData = data;
                this.sceneManager.setCursorData(data);
                if (data.visible) {
                    handCursor.style.left = data.x + 'px';
                    handCursor.style.top = data.y + 'px';
                    handCursor.classList.add('visible');
                    handCursor.classList.toggle('clicking', data.clicking);
                } else {
                    handCursor.classList.remove('visible', 'clicking');
                }
            })
            .onGestureChange((gesture) => {
                gestureIndicator.classList.remove('active');

                let label = 'Ready';
                if (gesture === 'tracking') label = 'Tracking';
                else if (gesture === 'cursor') label = 'Cursor';
                else if (gesture === 'clicking') label = 'Click!';
                else if (gesture === 'pinch-hold') label = 'Hold to zoom...';
                else if (gesture === 'zoom-in') label = 'Zoom in';
                else if (gesture === 'zoom-out') label = 'Zoom out';
                else if (gesture === 'rotating') label = 'Rotating';
                else if (gesture === 'panning') label = 'Panning';
                else if (gesture === 'recentered') label = 'Recentered!';
                else if (gesture.startsWith('recenter')) label = gesture;

                gestureText.textContent = label;

                if (gesture !== 'none' && gesture !== 'tracking') {
                    gestureIndicator.classList.add('active');
                }
            });

        this.puppetBridge = new PuppetBridge();
        this.puppetBridge
            .onConnect(() => { /* puppet connected */ })
            .onArmUpdate((data) => {
                if (this.puppetModeActive && this.roboticArmScene) {
                    this.roboticArmScene.setArmAngles(data.angles, data.gripper);
                }
                if (this.puppetModeActive) {
                    document.getElementById('gesture-text').textContent =
                        `Arm: [${data.angles.map(a => a.toFixed(0)).join(', ')}]`;
                }
            })
            .onPuppetState((state) => {
                const text = document.getElementById('gesture-text');
                if (!this.puppetModeActive || !text) return;

                const labels = {
                    idle: 'PUPPET (idle)',
                    live: 'PUPPET MODE',
                    recording: 'TEACHING...',
                    playback: 'PLAYBACK...'
                };
                text.textContent = labels[state] || `PUPPET (${state})`;
            })
            .onTeachingComplete((msg) => {
                const text = document.getElementById('gesture-text');
                if (text) text.textContent = `Saved: ${msg.name} (${msg.frames} frames)`;
            });

        this.handTracker = new HandTracker(video, handCanvas, (landmarks) => {
            this.gestureController.processLandmarks(landmarks);

            if (this.puppetModeActive && this.puppetBridge.connected) {
                this.puppetBridge.updateLandmarks(landmarks);
            }
        });

        try {
            await this.handTracker.initialize();
            await this.handTracker.start();

            this.resizeHandCanvas(video, handCanvas);
            video.addEventListener('loadedmetadata', () => {
                this.resizeHandCanvas(video, handCanvas);
            });
        } catch (error) {
            console.error('Camera initialization failed:', error);
            const gestureText = document.getElementById('gesture-text');
            if (gestureText) {
                gestureText.textContent = 'No camera';
            }
        }

        await this.sceneManager.switchScene(this.currentScene);
        this.sceneManager.start();
        loadingOverlay.classList.add('hidden');

        this.setupSceneButtons();
        this.setupKeyboardFallback();
        this.setupControls();
        this.setupUpload();
    }

    resizeHandCanvas(video, canvas) {
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
    }

    setupSceneButtons() {
        const toggle = document.getElementById('dropdown-toggle');
        const menu = document.getElementById('dropdown-menu');
        const label = document.getElementById('current-scene-label');

        toggle?.addEventListener('click', () => {
            menu.classList.toggle('hidden');
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('#scene-dropdown')) {
                menu?.classList.add('hidden');
            }
        });

        // Delegate click events for dynamically generated items
        menu?.addEventListener('click', async (e) => {
            const item = e.target.closest('.dropdown-item:not(.upload-item)');
            if (!item) return;

            const sceneName = item.dataset.scene;
            if (!sceneName || sceneName === this.currentScene) {
                menu?.classList.add('hidden');
                return;
            }

            menu.querySelectorAll('.dropdown-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            label.textContent = item.textContent;
            menu?.classList.add('hidden');

            const sceneEntry = this.registry.get(sceneName);
            const isInteractive = sceneEntry?.metadata?.interactive || false;
            this.gestureController.setInteractiveMode(isInteractive);

            if (sceneName === 'glass-brain') {
                this.tensorBridge.connect();
            } else {
                this.tensorBridge.disconnect();
            }

            this.currentScene = sceneName;
            await this.sceneManager.switchScene(sceneName);
        });
    }

    setupUpload() {
        const fileInput = document.getElementById('model-upload');

        // Re-bind upload button (dynamically generated)
        document.getElementById('dropdown-menu')?.addEventListener('click', (e) => {
            const uploadBtn = e.target.closest('#upload-btn');
            if (uploadBtn) {
                fileInput?.click();
            }
        });

        fileInput?.addEventListener('change', async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;

            // Validate file type and size
            const ALLOWED_TYPES = ['.glb', '.gltf', '.obj', '.fbx', '.stl'];
            const MAX_SIZE_MB = 50;
            const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
            if (!ALLOWED_TYPES.includes(ext)) {
                alert(`Unsupported file type: ${ext}\nAllowed: ${ALLOWED_TYPES.join(', ')}`);
                fileInput.value = '';
                return;
            }
            if (file.size > MAX_SIZE_MB * 1024 * 1024) {
                alert(`File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max: ${MAX_SIZE_MB} MB`);
                fileInput.value = '';
                return;
            }

            const url = URL.createObjectURL(file);
            const { createCustomModelScene } = await import('./scenes/custom-model.js');

            this.sceneManager.registerScene('custom', (THREE) => createCustomModelScene(THREE, url));

            this.currentScene = 'custom';
            await this.sceneManager.switchScene('custom');

            fileInput.value = '';
        });
    }

    setupControls() {
        const panel = document.getElementById('controls-panel');
        const toggle = document.getElementById('panel-toggle');
        const zoomSlider = document.getElementById('zoom-sensitivity');
        const rotationSlider = document.getElementById('rotation-sensitivity');
        const panSlider = document.getElementById('pan-sensitivity');
        const zoomValue = document.getElementById('zoom-value');
        const rotationValue = document.getElementById('rotation-value');
        const panValue = document.getElementById('pan-value');

        toggle?.addEventListener('click', () => {
            panel.classList.toggle('collapsed');
        });

        zoomSlider?.addEventListener('input', (e) => {
            const val = parseFloat(e.target.value);
            this.gestureController.setZoomSensitivity(val);
            zoomValue.textContent = val.toFixed(1) + '\u00d7';
        });

        rotationSlider?.addEventListener('input', (e) => {
            const val = parseFloat(e.target.value);
            this.gestureController.setRotationSensitivity(val);
            rotationValue.textContent = val.toFixed(1) + '\u00d7';
        });

        panSlider?.addEventListener('input', (e) => {
            const val = parseFloat(e.target.value);
            this.gestureController.setPanSensitivity(val);
            panValue.textContent = val.toFixed(1) + '\u00d7';
        });
    }

    setupKeyboardFallback() {
        let keys = {};
        let prevKeys = {};

        // Store bound handlers for cleanup
        this._onKeyDown = (e) => { keys[e.key.toLowerCase()] = true; };
        this._onKeyUp = (e) => { keys[e.key.toLowerCase()] = false; };
        window.addEventListener('keydown', this._onKeyDown);
        window.addEventListener('keyup', this._onKeyUp);

        this._rafId = null;
        const tick = () => {
            if (keys['arrowup'] || keys['w']) this.sceneManager.zoom(0.5);
            if (keys['arrowdown'] || keys['s']) this.sceneManager.zoom(-0.5);
            if (keys['arrowleft'] || keys['a']) this.sceneManager.rotate(-0.03, 0);
            if (keys['arrowright'] || keys['d']) this.sceneManager.rotate(0.03, 0);
            if (keys['q']) this.sceneManager.rotate(0, -0.03);
            if (keys['e']) this.sceneManager.rotate(0, 0.03);

            if (this.glassBrainScene) {
                if (keys['[']) this.glassBrainScene.prevLayer();
                if (keys[']']) this.glassBrainScene.nextLayer();
            }

            if (keys['p'] && !prevKeys['p']) {
                this.puppetModeActive = !this.puppetModeActive;
                if (this.puppetModeActive) {
                    this.puppetBridge.connect();
                    this.puppetBridge.startStreaming();
                    document.getElementById('gesture-text').textContent = 'PUPPET MODE';

                    // Auto-switch to robotic arm scene
                    this._previousScene = this.currentScene;
                    if (this.currentScene !== 'robotic-arm') {
                        this.currentScene = 'robotic-arm';
                        this.sceneManager.switchScene('robotic-arm');
                        const label = document.getElementById('current-scene-label');
                        if (label) label.textContent = 'Robotic Arm';
                    }
                } else {
                    this.puppetBridge.stopStreaming();
                    this.puppetBridge.disconnect();
                    document.getElementById('gesture-text').textContent = 'Tracking';

                    // Restore previous scene
                    if (this._previousScene && this._previousScene !== 'robotic-arm') {
                        this.currentScene = this._previousScene;
                        this.sceneManager.switchScene(this._previousScene);
                        const label = document.getElementById('current-scene-label');
                        const entry = this.registry.get(this._previousScene);
                        if (label && entry) label.textContent = entry.metadata.name;
                    }
                    this._previousScene = null;
                }
            }

            if (keys['t'] && !prevKeys['t'] && this.puppetModeActive) {
                if (this.puppetBridge.connected) {
                    if (this.puppetBridge.puppetState !== 'recording') {
                        this.puppetBridge.startTeaching('motion_' + Date.now());
                    } else {
                        this.puppetBridge.stopTeaching();
                    }
                }
            }

            prevKeys = { ...keys };
            this._rafId = requestAnimationFrame(tick);
        };
        this._rafId = requestAnimationFrame(tick);
    }

    destroy() {
        // Clean up keyboard listeners
        if (this._onKeyDown) window.removeEventListener('keydown', this._onKeyDown);
        if (this._onKeyUp) window.removeEventListener('keyup', this._onKeyUp);
        // Cancel animation frame loop
        if (this._rafId != null) cancelAnimationFrame(this._rafId);
        // Disconnect bridges
        if (this.tensorBridge) this.tensorBridge.disconnect();
        if (this.puppetBridge) this.puppetBridge.disconnect();
    }
}

new App().init();
