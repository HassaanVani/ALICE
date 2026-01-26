import * as THREE from 'three';

export class SceneManager {
    constructor(canvas) {
        this.canvas = canvas;
        this.scenes = {};
        this.currentSceneName = null;
        this.currentScene = null;
        this.cursorData = null;

        this.renderer = new THREE.WebGLRenderer({
            canvas,
            antialias: true,
            alpha: true
        });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setClearColor(0x09090b);

        this.camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 10000);
        this.cameraDistance = 10;
        this.cameraRotation = { x: 0.3, y: 0 };
        this.cameraTarget = new THREE.Vector3(0, 0, 0);
        this.targetDistance = 10;
        this.targetRotation = { x: 0.3, y: 0 };
        this.targetPan = new THREE.Vector3(0, 0, 0);

        this.updateCameraPosition();

        this.clock = new THREE.Clock();
        this.animationId = null;

        window.addEventListener('resize', () => this.handleResize());
    }

    setCursorData(data) {
        this.cursorData = data;
    }

    registerScene(name, sceneBuilder) {
        this.scenes[name] = sceneBuilder;
    }

    async switchScene(name) {
        if (!this.scenes[name]) return;

        if (this.currentScene) {
            this.disposeScene(this.currentScene);
        }

        this.currentSceneName = name;
        const sceneData = this.scenes[name](THREE);
        this.currentScene = sceneData;

        this.targetDistance = sceneData.defaultDistance || 10;
        this.cameraDistance = this.targetDistance;
        this.targetRotation = { x: 0.3, y: 0 };
        this.cameraRotation = { ...this.targetRotation };
        this.targetPan.set(0, 0, 0);
        this.cameraTarget.set(0, 0, 0);
        this.updateCameraPosition();
    }

    disposeScene(sceneData) {
        sceneData.scene.traverse((object) => {
            if (object.geometry) object.geometry.dispose();
            if (object.material) {
                if (Array.isArray(object.material)) {
                    object.material.forEach(m => m.dispose());
                } else {
                    object.material.dispose();
                }
            }
        });
    }

    zoom(delta) {
        this.targetDistance = Math.max(
            this.currentScene?.minDistance || 2,
            Math.min(this.currentScene?.maxDistance || 50, this.targetDistance - delta)
        );
    }

    rotate(deltaX, deltaY) {
        this.targetRotation.y += deltaX;
        this.targetRotation.x = Math.max(
            -Math.PI / 2.2,
            Math.min(Math.PI / 2.2, this.targetRotation.x + deltaY)
        );
    }

    pan(deltaX, deltaY) {
        const right = new THREE.Vector3();
        const up = new THREE.Vector3();

        this.camera.getWorldDirection(up);
        right.crossVectors(up, this.camera.up).normalize();
        up.crossVectors(right, up).normalize();

        const panSpeed = this.cameraDistance * 0.5;
        this.targetPan.add(right.multiplyScalar(-deltaX * panSpeed));
        this.targetPan.add(up.multiplyScalar(deltaY * panSpeed));
    }

    recenter() {
        this.targetPan.set(0, 0, 0);
        this.targetRotation = { x: 0.3, y: 0 };
        this.targetDistance = this.currentScene?.defaultDistance || 10;
    }

    updateCameraPosition() {
        this.camera.position.x = this.cameraTarget.x + this.cameraDistance * Math.sin(this.cameraRotation.y) * Math.cos(this.cameraRotation.x);
        this.camera.position.y = this.cameraTarget.y + this.cameraDistance * Math.sin(this.cameraRotation.x);
        this.camera.position.z = this.cameraTarget.z + this.cameraDistance * Math.cos(this.cameraRotation.y) * Math.cos(this.cameraRotation.x);
        this.camera.lookAt(this.cameraTarget);
    }

    start() {
        const animate = () => {
            this.animationId = requestAnimationFrame(animate);

            const delta = this.clock.getDelta();

            this.cameraDistance += (this.targetDistance - this.cameraDistance) * 0.08;
            this.cameraRotation.x += (this.targetRotation.x - this.cameraRotation.x) * 0.08;
            this.cameraRotation.y += (this.targetRotation.y - this.cameraRotation.y) * 0.08;
            this.cameraTarget.lerp(this.targetPan, 0.08);
            this.updateCameraPosition();

            if (this.currentScene?.update) {
                this.currentScene.update(delta, this.clock.elapsedTime, this.cursorData, this.camera);
            }

            if (this.currentScene) {
                this.renderer.render(this.currentScene.scene, this.camera);
            }
        };

        animate();
    }

    stop() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
    }

    updateBrainState(data) {
        if (this.currentSceneName === 'brain' && this.currentScene?.setActivationLevel) {
            // Aggregate activations to a simple scalar "activity level" for the demo
            // In a real app, we'd map specific tensors to specific 3D coordinates.
            let totalActivity = 0;
            if (data.activations) {
                // Sum up some values from the tensor arrays
                for (const key in data.activations) {
                    const tensor = data.activations[key];
                    // tensor is a nested list, flatten and sum simple
                    const flat = tensor.flat(Infinity);
                    const layerSum = flat.reduce((a, b) => a + Math.abs(b), 0);
                    totalActivity += layerSum;
                }
            }

            // Normalize roughly (assuming dummy data magnitude)
            const normalizedIntensity = totalActivity / 100.0;
            this.currentScene.setActivationLevel('global', normalizedIntensity);
        }
    }

    handleResize() {
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
    }
}
