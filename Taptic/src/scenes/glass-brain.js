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
    const voxelLayers = [];

    const layerConfigs = [
        { name: 'conv1', color: 0x4488ff, label: 'Conv1' },
        { name: 'conv2', color: 0x44ff88, label: 'Conv2' },
        { name: 'conv3', color: 0xff8844, label: 'Conv3' },
        { name: 'fc1', color: 0xff44ff, label: 'FC1' },
        { name: 'fc2', color: 0xffff44, label: 'FC2' }
    ];

    layerConfigs.forEach((config, layerIndex) => {
        const layerGroup = new THREE.Group();
        layerGroup.position.x = (layerIndex - 2) * LAYER_SPACING;
        layerGroup.userData = { name: config.name, index: layerIndex };

        const voxels = [];
        const geometry = new THREE.BoxGeometry(VOXEL_SIZE, VOXEL_SIZE, VOXEL_SIZE);

        for (let x = 0; x < GRID_SIZE; x++) {
            for (let y = 0; y < GRID_SIZE; y++) {
                for (let z = 0; z < GRID_SIZE; z++) {
                    const material = new THREE.MeshBasicMaterial({
                        color: config.color,
                        transparent: true,
                        opacity: 0
                    });

                    const voxel = new THREE.Mesh(geometry, material);
                    const offset = (GRID_SIZE * VOXEL_SIZE) / 2;
                    voxel.position.set(
                        (x * VOXEL_SIZE) - offset,
                        (y * VOXEL_SIZE) - offset,
                        (z * VOXEL_SIZE) - offset
                    );
                    voxel.userData = { x, y, z, baseOpacity: 0 };

                    voxels.push(voxel);
                    layerGroup.add(voxel);
                }
            }
        }

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

        voxelLayers.push({ group: layerGroup, voxels, config, label: labelDiv });
        scene.add(layerGroup);
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

            const totalVoxels = layer.voxels.length;
            const dataLen = data.length;

            layer.voxels.forEach((voxel, i) => {
                const dataIndex = Math.floor((i / totalVoxels) * dataLen);
                const value = data[dataIndex] || 0;
                const normalized = Math.max(0, Math.min(1, value));

                voxel.userData.baseOpacity = normalized * 0.8;
            });
        });
    };

    if (tensorBridge) {
        tensorBridge.onActivation(updateVoxelsFromData);
    }

    let time = 0;

    const update = (delta, elapsed) => {
        time = elapsed;

        voxelLayers.forEach((layer, idx) => {
            const distance = Math.abs(idx - currentLayerIndex);
            const targetScale = distance === 0 ? 1.2 : 0.8 - distance * 0.1;

            layer.group.scale.lerp(
                new THREE.Vector3(targetScale, targetScale, targetScale),
                0.05
            );

            layer.voxels.forEach((voxel, i) => {
                const { baseOpacity, x, y } = voxel.userData;
                const pulse = Math.sin(elapsed * 2 + x * 0.2 + y * 0.2) * 0.1;
                const inFocus = distance === 0 ? 1 : 0.3;
                voxel.material.opacity = Math.max(0, baseOpacity + pulse) * inFocus;
            });
        });

        connections.forEach(conn => {
            const pulse = Math.sin(elapsed * 3 + conn.userData.pulsePhase);
            conn.material.opacity = 0.05 + pulse * 0.05;
        });

        shell.rotation.y += delta * 0.05;
        shell.rotation.x = Math.sin(elapsed * 0.3) * 0.1;

        currentLayerIndex += (targetLayerIndex - currentLayerIndex) * 0.1;
    };

    return {
        scene,
        update,
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
