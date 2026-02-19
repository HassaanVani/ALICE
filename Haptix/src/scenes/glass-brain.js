export function createGlassBrainScene(THREE, tensorBridge = null) {
    const scene = new THREE.Scene();

    scene.add(new THREE.AmbientLight(0x1a1a2e, 0.4));

    const keyLight = new THREE.PointLight(0x00ffff, 0.8, 60);
    keyLight.position.set(8, 8, 8);
    scene.add(keyLight);

    const fillLight = new THREE.PointLight(0xff00ff, 0.4, 60);
    fillLight.position.set(-8, -4, -8);
    scene.add(fillLight);

    const GRID_SIZE = 16;
    const VOXEL_SIZE = 0.15;
    const LAYER_SPACING = 4;
    const VOXELS_PER_LAYER = GRID_SIZE * GRID_SIZE * GRID_SIZE;
    const voxelLayers = [];

    const layerConfigs = [
        { name: 'conv1', color: 0x4488ff, label: 'Conv1' },
        { name: 'conv2', color: 0x44ff88, label: 'Conv2' },
        { name: 'conv3', color: 0xff8844, label: 'Conv3' },
        { name: 'fc1', color: 0xff44ff, label: 'FC1' },
        { name: 'fc2', color: 0xffff44, label: 'FC2' },
        { name: 'sensory_input', color: 0x00ffff, label: 'Sensory' },
        { name: 'motor_cortex', color: 0xff0066, label: 'Motor Cortex' },
        { name: 'premotor', color: 0x66ff00, label: 'Premotor' },
        { name: 'cerebellum', color: 0xff6600, label: 'Cerebellum' },
        { name: 'basal_ganglia', color: 0x9900ff, label: 'Basal Ganglia' }
    ];

    // Shared geometry for all layers
    const voxelGeometry = new THREE.BoxGeometry(VOXEL_SIZE, VOXEL_SIZE, VOXEL_SIZE);

    // Custom shader that supports per-instance opacity via an attribute
    const makeVoxelMaterial = (color) => {
        const c = new THREE.Color(color);
        return new THREE.ShaderMaterial({
            transparent: true,
            depthWrite: false,
            uniforms: {
                uColor: { value: c },
            },
            vertexShader: `
                attribute float instanceOpacity;
                varying float vOpacity;
                void main() {
                    vOpacity = instanceOpacity;
                    gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform vec3 uColor;
                varying float vOpacity;
                void main() {
                    if (vOpacity < 0.01) discard;
                    gl_FragColor = vec4(uColor, vOpacity);
                }
            `,
        });
    };

    const dummy = new THREE.Object3D();

    layerConfigs.forEach((config, layerIndex) => {
        const material = makeVoxelMaterial(config.color);

        const mesh = new THREE.InstancedMesh(voxelGeometry, material, VOXELS_PER_LAYER);
        mesh.userData = { name: config.name, index: layerIndex };

        // Per-instance opacity buffer
        const opacityArray = new Float32Array(VOXELS_PER_LAYER);
        const opacityAttr = new THREE.InstancedBufferAttribute(opacityArray, 1);
        mesh.geometry.setAttribute('instanceOpacity', opacityAttr);

        // Pre-compute instance transforms
        const offset = (GRID_SIZE * VOXEL_SIZE) / 2;
        const baseOpacities = new Float32Array(VOXELS_PER_LAYER);
        let i = 0;
        for (let x = 0; x < GRID_SIZE; x++) {
            for (let y = 0; y < GRID_SIZE; y++) {
                for (let z = 0; z < GRID_SIZE; z++) {
                    dummy.position.set(
                        (x * VOXEL_SIZE) - offset,
                        (y * VOXEL_SIZE) - offset,
                        (z * VOXEL_SIZE) - offset
                    );
                    dummy.updateMatrix();
                    mesh.setMatrixAt(i, dummy.matrix);
                    baseOpacities[i] = 0;
                    i++;
                }
            }
        }
        mesh.instanceMatrix.needsUpdate = true;

        // Position the layer
        mesh.position.x = (layerIndex - 2) * LAYER_SPACING;

        const labelDiv = document.createElement('div');
        labelDiv.className = 'layer-label';
        labelDiv.textContent = config.label;
        labelDiv.style.cssText = `
            position: absolute;
            color: white;
            font-family: monospace;
            font-size: 12px;
            pointer-events: none;
            opacity: 0.7;
        `;

        voxelLayers.push({
            mesh,
            material,
            opacityAttr,
            baseOpacities,
            config,
            label: labelDiv,
            scale: 1.0,
            targetScale: 1.0,
        });
        scene.add(mesh);
    });

    const connectionMaterial = new THREE.LineBasicMaterial({
        color: 0x4488ff,
        transparent: true,
        opacity: 0.1
    });

    const connections = [];
    for (let i = 0; i < layerConfigs.length - 1; i++) {
        const startX = (i - 2) * LAYER_SPACING;
        const endX = (i - 1) * LAYER_SPACING;

        for (let j = 0; j < 20; j++) {
            const startY = (Math.random() - 0.5) * 2;
            const startZ = (Math.random() - 0.5) * 2;
            const endY = (Math.random() - 0.5) * 2;
            const endZ = (Math.random() - 0.5) * 2;

            const points = [
                new THREE.Vector3(startX + 1, startY, startZ),
                new THREE.Vector3(endX - 1, endY, endZ)
            ];
            const geometry = new THREE.BufferGeometry().setFromPoints(points);
            const line = new THREE.Line(geometry, connectionMaterial.clone());
            line.userData = { pulsePhase: Math.random() * Math.PI * 2 };
            connections.push(line);
            scene.add(line);
        }
    }

    const shellGeometry = new THREE.IcosahedronGeometry(5, 1);
    const shellMaterial = new THREE.MeshBasicMaterial({
        color: 0x4488ff,
        transparent: true,
        opacity: 0.02,
        wireframe: true
    });
    const shell = new THREE.Mesh(shellGeometry, shellMaterial);
    scene.add(shell);

    let currentLayerIndex = 2;
    let targetLayerIndex = 2;
    let frozen = false;

    const updateVoxelsFromData = (layerData) => {
        if (frozen) return;

        voxelLayers.forEach(layer => {
            const data = layerData?.get(layer.config.name);
            if (!data) return;

            const dataLen = data.length;
            for (let i = 0; i < VOXELS_PER_LAYER; i++) {
                const dataIndex = Math.min(Math.floor((i / VOXELS_PER_LAYER) * dataLen), dataLen - 1);
                const value = data[dataIndex] || 0;
                layer.baseOpacities[i] = Math.max(0, Math.min(1, value)) * 0.8;
            }
        });
    };

    if (tensorBridge) {
        tensorBridge.onActivation(updateVoxelsFromData);
    }

    const update = (delta, elapsed) => {
        voxelLayers.forEach((layer, idx) => {
            const distance = Math.abs(idx - currentLayerIndex);
            layer.targetScale = distance === 0 ? 1.2 : 0.8 - distance * 0.1;
            layer.scale += (layer.targetScale - layer.scale) * 0.05;
            layer.mesh.scale.setScalar(layer.scale);

            const inFocus = distance === 0 ? 1 : 0.3;
            const arr = layer.opacityAttr.array;

            // Batch-update per-instance opacity
            let vi = 0;
            for (let x = 0; x < GRID_SIZE; x++) {
                for (let y = 0; y < GRID_SIZE; y++) {
                    for (let z = 0; z < GRID_SIZE; z++) {
                        const base = layer.baseOpacities[vi];
                        const pulse = Math.sin(elapsed * 2 + x * 0.2 + y * 0.2) * 0.1;
                        arr[vi] = Math.max(0, base + pulse) * inFocus;
                        vi++;
                    }
                }
            }
            layer.opacityAttr.needsUpdate = true;
        });

        connections.forEach(conn => {
            const pulse = Math.sin(elapsed * 3 + conn.userData.pulsePhase);
            conn.material.opacity = 0.05 + pulse * 0.05;
        });

        shell.rotation.y += delta * 0.05;
        shell.rotation.x = Math.sin(elapsed * 0.3) * 0.1;

        currentLayerIndex += (targetLayerIndex - currentLayerIndex) * 0.1;
    };

    const dispose = () => {
        voxelGeometry.dispose();
        voxelLayers.forEach(layer => {
            layer.material.dispose();
            layer.mesh.dispose();
        });
        connections.forEach(conn => {
            conn.geometry.dispose();
            conn.material.dispose();
        });
        shellGeometry.dispose();
        shellMaterial.dispose();
    };

    return {
        scene,
        update,
        dispose,
        defaultDistance: 12,
        minDistance: 4,
        maxDistance: 30,

        focusLayer: (index) => {
            targetLayerIndex = Math.max(0, Math.min(layerConfigs.length - 1, index));
        },

        nextLayer: () => {
            targetLayerIndex = Math.min(targetLayerIndex + 1, layerConfigs.length - 1);
        },

        prevLayer: () => {
            targetLayerIndex = Math.max(targetLayerIndex - 1, 0);
        },

        toggleFreeze: () => {
            frozen = !frozen;
            return frozen;
        },

        setActivations: updateVoxelsFromData,

        getCurrentLayer: () => layerConfigs[Math.round(currentLayerIndex)]?.name
    };
}

export const metadata = { name: "Glass Brain", category: "Neural", description: "Real-time neural activation viewer", interactive: false };
export default (THREE, tensorBridge) => createGlassBrainScene(THREE, tensorBridge);
