import './styles.css';
import { HandTracker } from './hand-tracker.js';
import { GestureController } from './gesture-controller.js';
import { SceneManager } from './scene-manager.js';
import { createSolarSystemScene } from './scenes/solar-system.js';
import { createGoldAtomScene } from './scenes/gold-atom.js';
import { createBrainScene } from './scenes/brain.js';
import { createMarsScene } from './scenes/mars.js';
import { createDNAScene } from './scenes/dna.js';
import { createBlackHoleScene } from './scenes/black-hole.js';
import { createCellScene } from './scenes/cell.js';
import { createGalaxyScene } from './scenes/galaxy.js';
import { createEarthScene } from './scenes/earth.js';
import { createUIDemo } from './scenes/ui-demo.js';
import { createParticleRoom } from './scenes/particle-room.js';
import { createCustomModelScene } from './scenes/custom-model.js';
import { createMoleculeMaker } from './scenes/molecule-maker.js';

class App {
    constructor() {
        this.sceneManager = null;
        this.handTracker = null;
        this.gestureController = null;
        this.currentScene = 'solar-system';
    }

    async init() {
        const canvas = document.getElementById('scene-canvas');
        const video = document.getElementById('webcam');
        const handCanvas = document.getElementById('hand-canvas');
        const loadingOverlay = document.getElementById('loading-overlay');
        const gestureIndicator = document.getElementById('gesture-indicator');
        const gestureText = document.getElementById('gesture-text');

        this.sceneManager = new SceneManager(canvas);
        this.sceneManager.registerScene('solar-system', createSolarSystemScene);
        this.sceneManager.registerScene('gold-atom', createGoldAtomScene);
        this.sceneManager.registerScene('brain', createBrainScene);
        this.sceneManager.registerScene('mars', createMarsScene);
        this.sceneManager.registerScene('dna', createDNAScene);
        this.sceneManager.registerScene('black-hole', createBlackHoleScene);
        this.sceneManager.registerScene('cell', createCellScene);
        this.sceneManager.registerScene('galaxy', createGalaxyScene);
        this.sceneManager.registerScene('earth', createEarthScene);
        this.sceneManager.registerScene('ui-demo', createUIDemo);
        this.sceneManager.registerScene('particle-room', createParticleRoom);
        this.sceneManager.registerScene('molecule-maker', createMoleculeMaker);

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

        this.handTracker = new HandTracker(video, handCanvas, (landmarks) => {
            this.gestureController.processLandmarks(landmarks);
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

        // --- WEBSOCKET CONNECTION ---
        this.connectToBrain();
    }

    connectToBrain() {
        const ws = new WebSocket('ws://localhost:8765');

        ws.onopen = () => {
            console.log('Connected to A.L.I.C.E. Brain');
            const gestureText = document.getElementById('gesture-text');
            if (gestureText) gestureText.textContent = "Brain Connected";
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'brain_state') {
                    this.sceneManager.updateBrainState(data);
                }
            } catch (e) {
                console.error('Error parsing brain data', e);
            }
        };

        ws.onclose = () => {
            console.log('Disconnected from Brain. Retrying in 3s...');
            setTimeout(() => this.connectToBrain(), 3000);
        };

        ws.onerror = (err) => {
            console.log('Brain WS Error (Is main.py running?)');
        };
    }

    resizeHandCanvas(video, canvas) {
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
    }

    setupSceneButtons() {
        const toggle = document.getElementById('dropdown-toggle');
        const menu = document.getElementById('dropdown-menu');
        const label = document.getElementById('current-scene-label');
        const items = document.querySelectorAll('.dropdown-item:not(.upload-item)');

        toggle?.addEventListener('click', () => {
            menu.classList.toggle('hidden');
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('#scene-dropdown')) {
                menu?.classList.add('hidden');
            }
        });

        items.forEach((item) => {
            item.addEventListener('click', async () => {
                const sceneName = item.dataset.scene;
                if (!sceneName || sceneName === this.currentScene) {
                    menu?.classList.add('hidden');
                    return;
                }

                items.forEach(i => i.classList.remove('active'));
                item.classList.add('active');
                label.textContent = item.textContent;
                menu?.classList.add('hidden');

                const isInteractive = sceneName === 'ui-demo' || sceneName === 'particle-room' || sceneName === 'molecule-maker';
                this.gestureController.setInteractiveMode(isInteractive);

                this.currentScene = sceneName;
                await this.sceneManager.switchScene(sceneName);
            });
        });
    }

    setupUpload() {
        const uploadBtn = document.getElementById('upload-btn');
        const fileInput = document.getElementById('model-upload');

        uploadBtn?.addEventListener('click', () => {
            fileInput?.click();
        });

        fileInput?.addEventListener('change', async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;

            const url = URL.createObjectURL(file);

            this.sceneManager.registerScene('custom', (THREE) => createCustomModelScene(THREE, url));

            document.querySelectorAll('.scenario-btn').forEach(b => b.classList.remove('active'));
            uploadBtn.classList.add('active');
            uploadBtn.querySelector('svg')?.remove();
            uploadBtn.textContent = file.name.slice(0, 12) + (file.name.length > 12 ? '...' : '');

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
            zoomValue.textContent = val.toFixed(1) + '×';
        });

        rotationSlider?.addEventListener('input', (e) => {
            const val = parseFloat(e.target.value);
            this.gestureController.setRotationSensitivity(val);
            rotationValue.textContent = val.toFixed(1) + '×';
        });

        panSlider?.addEventListener('input', (e) => {
            const val = parseFloat(e.target.value);
            this.gestureController.setPanSensitivity(val);
            panValue.textContent = val.toFixed(1) + '×';
        });
    }

    setupKeyboardFallback() {
        let keys = {};

        window.addEventListener('keydown', (e) => { keys[e.key] = true; });
        window.addEventListener('keyup', (e) => { keys[e.key] = false; });

        const tick = () => {
            if (keys['ArrowUp'] || keys['w']) this.sceneManager.zoom(0.5);
            if (keys['ArrowDown'] || keys['s']) this.sceneManager.zoom(-0.5);
            if (keys['ArrowLeft'] || keys['a']) this.sceneManager.rotate(-0.03, 0);
            if (keys['ArrowRight'] || keys['d']) this.sceneManager.rotate(0.03, 0);
            if (keys['q']) this.sceneManager.rotate(0, -0.03);
            if (keys['e']) this.sceneManager.rotate(0, 0.03);
            requestAnimationFrame(tick);
        };
        tick();
    }
}

new App().init();
