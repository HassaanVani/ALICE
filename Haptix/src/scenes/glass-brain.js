/**
 * Glass Brain — Neural activation visualizer.
 *
 * Renders CNN + state-model layers as glowing neuron clusters arranged in a
 * brain-like ellipsoid.  Active neurons bloom, synaptic particle trails
 * flow between layers, and a pulsing energy ring highlights the focused layer.
 *
 * Receives real-time data from TensorBridge.
 */

export function createGlassBrainScene(THREE, tensorBridge = null) {
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x050510, 0.018);

    // ── Lighting ──────────────────────────────────────────────────────────
    const ambientLight = new THREE.AmbientLight(0x0a0a1e, 0.3);
    scene.add(ambientLight);

    const coreLight = new THREE.PointLight(0x4488ff, 1.5, 40);
    coreLight.position.set(0, 0, 0);
    scene.add(coreLight);

    const rimLight1 = new THREE.PointLight(0x00ffcc, 0.6, 50);
    rimLight1.position.set(12, 6, 8);
    scene.add(rimLight1);

    const rimLight2 = new THREE.PointLight(0xff00aa, 0.4, 50);
    rimLight2.position.set(-10, -4, -8);
    scene.add(rimLight2);

    // ── Config ────────────────────────────────────────────────────────────
    const NEURONS_PER_LAYER = 512;
    const NEURON_RADIUS = 0.06;

    const layerConfigs = [
        { name: 'conv1',         color: 0x3388ff, emissive: 0x1144aa, label: 'Conv1' },
        { name: 'conv2',         color: 0x33ffaa, emissive: 0x11aa66, label: 'Conv2' },
        { name: 'conv3',         color: 0xff8833, emissive: 0xaa5511, label: 'Conv3' },
        { name: 'fc1',           color: 0xff33ff, emissive: 0xaa11aa, label: 'FC1' },
        { name: 'fc2',           color: 0xffee33, emissive: 0xaaaa11, label: 'FC2' },
        { name: 'sensory_input', color: 0x00ffee, emissive: 0x00aa99, label: 'Sensory' },
        { name: 'motor_cortex',  color: 0xff0066, emissive: 0xaa0044, label: 'Motor' },
        { name: 'premotor',      color: 0x66ff00, emissive: 0x44aa00, label: 'Premotor' },
        { name: 'cerebellum',    color: 0xff6600, emissive: 0xaa4400, label: 'Cerebellum' },
        { name: 'basal_ganglia', color: 0xaa00ff, emissive: 0x6600aa, label: 'Basal G.' },
    ];

    // ── Shared geometry ───────────────────────────────────────────────────
    const neuronGeo = new THREE.IcosahedronGeometry(NEURON_RADIUS, 1);

    // ── Per-instance shader ───────────────────────────────────────────────
    // Glow intensity is driven by the instanceOpacity attribute.  The
    // fragment blends between a dim base color and a bright emissive based
    // on that value, producing a bloom-like effect without post-processing.

    const makeNeuronMaterial = (baseColor, emissiveColor) => {
        const bc = new THREE.Color(baseColor);
        const ec = new THREE.Color(emissiveColor);
        return new THREE.ShaderMaterial({
            transparent: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
            uniforms: {
                uBaseColor:     { value: bc },
                uEmissiveColor: { value: ec },
                uTime:          { value: 0 },
            },
            vertexShader: /* glsl */ `
                attribute float instanceOpacity;
                varying float vOpacity;
                varying vec3 vNormal;
                varying vec3 vWorldPos;
                void main() {
                    vOpacity = instanceOpacity;
                    vNormal = normalize(normalMatrix * normal);
                    vec4 worldPos = modelMatrix * instanceMatrix * vec4(position, 1.0);
                    vWorldPos = worldPos.xyz;
                    gl_Position = projectionMatrix * viewMatrix * worldPos;
                }
            `,
            fragmentShader: /* glsl */ `
                uniform vec3 uBaseColor;
                uniform vec3 uEmissiveColor;
                uniform float uTime;
                varying float vOpacity;
                varying vec3 vNormal;
                varying vec3 vWorldPos;
                void main() {
                    if (vOpacity < 0.01) discard;

                    // Fresnel rim glow
                    vec3 viewDir = normalize(cameraPosition - vWorldPos);
                    float fresnel = pow(1.0 - max(dot(vNormal, viewDir), 0.0), 2.5);

                    // Mix base → emissive based on activation
                    float glow = vOpacity * vOpacity;           // ease-in curve
                    vec3 color = mix(uBaseColor * 0.3, uEmissiveColor * 2.5, glow);
                    color += uEmissiveColor * fresnel * glow * 1.5;

                    float alpha = 0.08 + glow * 0.85 + fresnel * 0.3 * glow;
                    gl_FragColor = vec4(color, clamp(alpha, 0.0, 1.0));
                }
            `,
        });
    };

    // ── Build neuron layers ───────────────────────────────────────────────
    // Neurons are scattered inside an ellipsoid per layer, offset along X.

    const voxelLayers = [];
    const dummy = new THREE.Object3D();
    const LAYER_SPACING = 3.6;
    const totalWidth = (layerConfigs.length - 1) * LAYER_SPACING;

    const _sphericalRand = (radius) => {
        // Uniform random point inside a sphere (rejection sampling)
        let x, y, z;
        do {
            x = (Math.random() - 0.5) * 2;
            y = (Math.random() - 0.5) * 2;
            z = (Math.random() - 0.5) * 2;
        } while (x * x + y * y + z * z > 1);
        return { x: x * radius, y: y * radius, z: z * radius };
    };

    layerConfigs.forEach((config, layerIndex) => {
        const material = makeNeuronMaterial(config.color, config.emissive);
        const mesh = new THREE.InstancedMesh(neuronGeo, material, NEURONS_PER_LAYER);

        const opacityArray = new Float32Array(NEURONS_PER_LAYER);
        const opacityAttr = new THREE.InstancedBufferAttribute(opacityArray, 1);
        mesh.geometry.setAttribute('instanceOpacity', opacityAttr);

        // Ellipsoidal cluster — wider than tall, slightly flattened
        const clusterRadius = 1.4 + Math.random() * 0.3;
        const neuronPositions = [];

        for (let i = 0; i < NEURONS_PER_LAYER; i++) {
            const p = _sphericalRand(clusterRadius);
            // Squash into an ellipsoid (wider on x-local, flatter on y)
            dummy.position.set(p.x * 1.2, p.y * 0.8, p.z);
            // Slight random scale variation
            const s = 0.7 + Math.random() * 0.6;
            dummy.scale.setScalar(s);
            dummy.updateMatrix();
            mesh.setMatrixAt(i, dummy.matrix);
            opacityArray[i] = 0;
            neuronPositions.push({ x: p.x * 1.2, y: p.y * 0.8, z: p.z });
        }
        mesh.instanceMatrix.needsUpdate = true;

        // Center the layer
        mesh.position.x = (layerIndex - (layerConfigs.length - 1) / 2) * LAYER_SPACING;

        const baseOpacities = new Float32Array(NEURONS_PER_LAYER);

        voxelLayers.push({
            mesh,
            material,
            opacityAttr,
            baseOpacities,
            config,
            neuronPositions,
            clusterRadius,
            scale: 1.0,
            targetScale: 1.0,
            energy: 0,     // aggregate activation energy for effects
        });
        scene.add(mesh);
    });

    // ── Synaptic particle trails ──────────────────────────────────────────
    // Flowing particles between adjacent layers.  Speed + brightness
    // proportional to activation intensity.

    const PARTICLES_PER_LINK = 60;
    const synapseLinks = [];

    const particleGeo = new THREE.BufferGeometry();
    const particleMat = new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        uniforms: { uTime: { value: 0 } },
        vertexShader: /* glsl */ `
            attribute float aSize;
            attribute float aAlpha;
            attribute vec3 aColor;
            varying float vAlpha;
            varying vec3 vColor;
            void main() {
                vAlpha = aAlpha;
                vColor = aColor;
                vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
                gl_PointSize = aSize * (200.0 / -mvPos.z);
                gl_Position = projectionMatrix * mvPos;
            }
        `,
        fragmentShader: /* glsl */ `
            varying float vAlpha;
            varying vec3 vColor;
            void main() {
                float d = length(gl_PointCoord - vec2(0.5));
                if (d > 0.5) discard;
                float glow = 1.0 - smoothstep(0.0, 0.5, d);
                glow = pow(glow, 1.5);
                gl_FragColor = vec4(vColor * 1.5, glow * vAlpha);
            }
        `,
    });

    for (let i = 0; i < layerConfigs.length - 1; i++) {
        const layerA = voxelLayers[i];
        const layerB = voxelLayers[i + 1];
        const midColor = new THREE.Color(layerA.config.color).lerp(
            new THREE.Color(layerB.config.color), 0.5
        );

        const count = PARTICLES_PER_LINK;
        const positions = new Float32Array(count * 3);
        const sizes     = new Float32Array(count);
        const alphas    = new Float32Array(count);
        const colors    = new Float32Array(count * 3);
        const phases    = new Float32Array(count);   // 0-1 progress along path
        const startPts  = [];
        const endPts    = [];

        for (let j = 0; j < count; j++) {
            phases[j] = Math.random();
            sizes[j] = 1.5 + Math.random() * 2;
            alphas[j] = 0;

            // Pick random neuron endpoints in each layer
            const ai = Math.floor(Math.random() * NEURONS_PER_LAYER);
            const bi = Math.floor(Math.random() * NEURONS_PER_LAYER);
            startPts.push(layerA.neuronPositions[ai]);
            endPts.push(layerB.neuronPositions[bi]);

            const c = midColor.clone();
            c.offsetHSL(Math.random() * 0.06 - 0.03, 0, Math.random() * 0.1);
            colors[j * 3]     = c.r;
            colors[j * 3 + 1] = c.g;
            colors[j * 3 + 2] = c.b;
        }

        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geo.setAttribute('aSize',    new THREE.BufferAttribute(sizes, 1));
        geo.setAttribute('aAlpha',   new THREE.BufferAttribute(alphas, 1));
        geo.setAttribute('aColor',   new THREE.BufferAttribute(colors, 3));

        const points = new THREE.Points(geo, particleMat);
        scene.add(points);

        synapseLinks.push({
            points, geo, phases, startPts, endPts,
            positions, alphas,
            layerAIndex: i,
            layerBIndex: i + 1,
        });
    }

    // ── Energy pulse rings ─────────────────────────────────────────────────
    const ringGeo = new THREE.RingGeometry(1.8, 2.0, 64);
    const ringMat = new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        uniforms: {
            uColor:   { value: new THREE.Color(0x4488ff) },
            uTime:    { value: 0 },
            uEnergy:  { value: 0 },
        },
        vertexShader: /* glsl */ `
            varying vec2 vUv;
            void main() {
                vUv = uv;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: /* glsl */ `
            uniform vec3 uColor;
            uniform float uTime;
            uniform float uEnergy;
            varying vec2 vUv;
            void main() {
                float angle = atan(vUv.y - 0.5, vUv.x - 0.5);
                float sweep = sin(angle * 3.0 + uTime * 4.0) * 0.5 + 0.5;
                float alpha = sweep * uEnergy * 0.6;
                gl_FragColor = vec4(uColor * 1.8, alpha);
            }
        `,
    });

    const pulseRings = [];
    layerConfigs.forEach((config, idx) => {
        const ring = new THREE.Mesh(ringGeo, ringMat.clone());
        ring.material.uniforms.uColor.value = new THREE.Color(config.color);
        ring.position.x = (idx - (layerConfigs.length - 1) / 2) * LAYER_SPACING;
        ring.rotation.y = Math.PI / 2;
        scene.add(ring);
        pulseRings.push(ring);
    });

    // ── Ambient neural dust ───────────────────────────────────────────────
    const DUST_COUNT = 800;
    const dustPositions = new Float32Array(DUST_COUNT * 3);
    const dustSizes     = new Float32Array(DUST_COUNT);
    const dustAlphas    = new Float32Array(DUST_COUNT);
    const dustColors    = new Float32Array(DUST_COUNT * 3);
    const dustVelocities = [];

    for (let i = 0; i < DUST_COUNT; i++) {
        const r = 6 + Math.random() * 14;
        const theta = Math.random() * Math.PI * 2;
        const phi   = Math.acos(2 * Math.random() - 1);
        dustPositions[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
        dustPositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.6;
        dustPositions[i * 3 + 2] = r * Math.cos(phi);
        dustSizes[i] = 0.8 + Math.random() * 1.5;
        dustAlphas[i] = 0.05 + Math.random() * 0.15;
        const hue = Math.random();
        const c = new THREE.Color().setHSL(hue, 0.5, 0.6);
        dustColors[i * 3]     = c.r;
        dustColors[i * 3 + 1] = c.g;
        dustColors[i * 3 + 2] = c.b;
        dustVelocities.push({
            x: (Math.random() - 0.5) * 0.003,
            y: (Math.random() - 0.5) * 0.002,
            z: (Math.random() - 0.5) * 0.003,
        });
    }

    const dustGeo = new THREE.BufferGeometry();
    dustGeo.setAttribute('position', new THREE.BufferAttribute(dustPositions, 3));
    dustGeo.setAttribute('aSize',    new THREE.BufferAttribute(dustSizes, 1));
    dustGeo.setAttribute('aAlpha',   new THREE.BufferAttribute(dustAlphas, 1));
    dustGeo.setAttribute('aColor',   new THREE.BufferAttribute(dustColors, 3));

    const dustMat = particleMat.clone();
    const dustPoints = new THREE.Points(dustGeo, dustMat);
    scene.add(dustPoints);

    // ── Outer shell ───────────────────────────────────────────────────────
    const shellGeo = new THREE.IcosahedronGeometry(6.5, 2);
    const shellMat = new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        wireframe: true,
        blending: THREE.AdditiveBlending,
        uniforms: {
            uTime:   { value: 0 },
            uEnergy: { value: 0 },
            uColor:  { value: new THREE.Color(0x2244aa) },
        },
        vertexShader: /* glsl */ `
            varying vec3 vPos;
            void main() {
                vPos = position;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: /* glsl */ `
            uniform float uTime;
            uniform float uEnergy;
            uniform vec3 uColor;
            varying vec3 vPos;
            void main() {
                float wave = sin(vPos.y * 3.0 + uTime * 2.0) * 0.5 + 0.5;
                float alpha = (0.02 + wave * 0.04) * (0.5 + uEnergy * 0.5);
                gl_FragColor = vec4(uColor * (1.0 + uEnergy), alpha);
            }
        `,
    });
    const shell = new THREE.Mesh(shellGeo, shellMat);
    scene.add(shell);

    // ── State ─────────────────────────────────────────────────────────────
    let currentLayerIndex = 2;
    let targetLayerIndex = 2;
    let frozen = false;
    let globalEnergy = 0;

    // ── Data intake ───────────────────────────────────────────────────────
    const updateVoxelsFromData = (layerData) => {
        if (frozen) return;

        voxelLayers.forEach(layer => {
            const data = layerData?.get(layer.config.name);
            if (!data) return;

            const dataLen = data.length;
            let sum = 0;
            for (let i = 0; i < NEURONS_PER_LAYER; i++) {
                const di = Math.min(Math.floor((i / NEURONS_PER_LAYER) * dataLen), dataLen - 1);
                const v = Math.max(0, Math.min(1, data[di] || 0));
                layer.baseOpacities[i] = v;
                sum += v;
            }
            layer.energy = sum / NEURONS_PER_LAYER;
        });
    };

    if (tensorBridge) {
        tensorBridge.onActivation(updateVoxelsFromData);
    }

    // ── Update loop ───────────────────────────────────────────────────────
    const update = (delta, elapsed) => {
        // Global energy = average of all layer energies
        let totalEnergy = 0;

        // ── Neuron layers ──
        voxelLayers.forEach((layer, idx) => {
            const distance = Math.abs(idx - currentLayerIndex);
            layer.targetScale = distance < 0.8 ? 1.15 : Math.max(0.6, 0.95 - distance * 0.06);
            layer.scale += (layer.targetScale - layer.scale) * 0.06;
            layer.mesh.scale.setScalar(layer.scale);

            const inFocus = distance < 0.8 ? 1.0 : Math.max(0.15, 0.5 - distance * 0.08);

            const arr = layer.opacityAttr.array;
            for (let i = 0; i < NEURONS_PER_LAYER; i++) {
                const base = layer.baseOpacities[i];
                const p = layer.neuronPositions[i];
                // Spatial wave adds organic motion
                const wave = Math.sin(elapsed * 1.8 + p.x * 2.5 + p.y * 1.8 + p.z * 2.0) * 0.12;
                // Sparkle — random neurons briefly flash
                const sparkle = (Math.sin(elapsed * 12 + i * 7.3) > 0.97) ? 0.3 : 0;
                arr[i] = Math.max(0, (base + wave + sparkle * base)) * inFocus;
            }
            layer.opacityAttr.needsUpdate = true;

            // Update material time uniform
            layer.material.uniforms.uTime.value = elapsed;

            totalEnergy += layer.energy;
        });

        globalEnergy = totalEnergy / voxelLayers.length;

        // ── Pulse rings ──
        pulseRings.forEach((ring, idx) => {
            const layer = voxelLayers[idx];
            const dist = Math.abs(idx - currentLayerIndex);
            ring.material.uniforms.uTime.value = elapsed;
            ring.material.uniforms.uEnergy.value = layer.energy * (dist < 1 ? 1.0 : 0.3);
            ring.scale.setScalar(1.0 + Math.sin(elapsed * 2 + idx) * 0.05 * layer.energy);
        });

        // ── Synaptic particles ──
        const speed = 0.2 + globalEnergy * 0.6;
        synapseLinks.forEach(link => {
            const layerA = voxelLayers[link.layerAIndex];
            const layerB = voxelLayers[link.layerBIndex];
            const intensity = (layerA.energy + layerB.energy) * 0.5;

            for (let j = 0; j < link.phases.length; j++) {
                link.phases[j] += delta * speed * (0.5 + Math.random() * 0.5);
                if (link.phases[j] > 1) link.phases[j] -= 1;

                const t = link.phases[j];
                const s = link.startPts[j];
                const e = link.endPts[j];

                // Cubic ease for natural motion
                const st = t * t * (3 - 2 * t);

                const ax = layerA.mesh.position.x + s.x;
                const ay = s.y;
                const az = s.z;
                const bx = layerB.mesh.position.x + e.x;
                const by = e.y;
                const bz = e.z;
                // Add a slight arc
                const arcY = Math.sin(st * Math.PI) * 0.6;

                link.positions[j * 3]     = ax + (bx - ax) * st;
                link.positions[j * 3 + 1] = ay + (by - ay) * st + arcY;
                link.positions[j * 3 + 2] = az + (bz - az) * st;

                // Fade in at start, fade out at end
                const fade = Math.sin(st * Math.PI);
                link.alphas[j] = fade * intensity * 0.7;
            }

            link.geo.attributes.position.needsUpdate = true;
            link.geo.attributes.aAlpha.needsUpdate = true;
        });

        // ── Neural dust drift ──
        for (let i = 0; i < DUST_COUNT; i++) {
            const v = dustVelocities[i];
            dustPositions[i * 3]     += v.x + Math.sin(elapsed * 0.3 + i) * 0.001;
            dustPositions[i * 3 + 1] += v.y;
            dustPositions[i * 3 + 2] += v.z + Math.cos(elapsed * 0.3 + i) * 0.001;

            // Wrap around if too far
            const dist = Math.sqrt(
                dustPositions[i * 3] ** 2 +
                dustPositions[i * 3 + 1] ** 2 +
                dustPositions[i * 3 + 2] ** 2
            );
            if (dist > 20) {
                const scale = 6 / dist;
                dustPositions[i * 3]     *= scale;
                dustPositions[i * 3 + 1] *= scale;
                dustPositions[i * 3 + 2] *= scale;
            }
        }
        dustGeo.attributes.position.needsUpdate = true;

        // ── Shell ──
        shell.rotation.y += delta * 0.03;
        shell.rotation.x = Math.sin(elapsed * 0.2) * 0.08;
        shellMat.uniforms.uTime.value = elapsed;
        shellMat.uniforms.uEnergy.value = globalEnergy;

        // ── Core light pulses with global energy ──
        coreLight.intensity = 1.0 + globalEnergy * 3.0 + Math.sin(elapsed * 3) * 0.3;
        coreLight.color.setHSL(0.58 + globalEnergy * 0.1, 0.8, 0.5);

        // ── Camera focus layer interpolation ──
        currentLayerIndex += (targetLayerIndex - currentLayerIndex) * 0.08;
    };

    // ── Cleanup ───────────────────────────────────────────────────────────
    const dispose = () => {
        neuronGeo.dispose();
        voxelLayers.forEach(layer => {
            layer.material.dispose();
            layer.mesh.dispose();
        });
        synapseLinks.forEach(link => {
            link.geo.dispose();
        });
        particleMat.dispose();
        dustGeo.dispose();
        dustMat.dispose();
        ringGeo.dispose();
        pulseRings.forEach(r => r.material.dispose());
        shellGeo.dispose();
        shellMat.dispose();
    };

    // ── Public API ────────────────────────────────────────────────────────
    return {
        scene,
        update,
        dispose,
        defaultDistance: 14,
        minDistance: 5,
        maxDistance: 35,

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
        getCurrentLayer: () => layerConfigs[Math.round(currentLayerIndex)]?.name,
    };
}

export const metadata = {
    name: 'Glass Brain',
    category: 'Neural',
    description: 'Real-time neural activation viewer — glowing neurons, synaptic trails, energy pulses',
    interactive: false,
};

export default (THREE, tensorBridge) => createGlassBrainScene(THREE, tensorBridge);
