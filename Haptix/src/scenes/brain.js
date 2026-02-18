export function createBrainScene(THREE) {
    const scene = new THREE.Scene();

    scene.add(new THREE.AmbientLight(0x1a1a2e, 0.3));

    const keyLight = new THREE.PointLight(0x4488ff, 1, 50);
    keyLight.position.set(5, 5, 5);
    scene.add(keyLight);

    const fillLight = new THREE.PointLight(0xff4488, 0.5, 50);
    fillLight.position.set(-5, -2, -5);
    scene.add(fillLight);

    const neurons = [];
    const connections = [];
    const neuronCount = 2000;
    const connectionCount = 800;

    const brainShape = (u, v) => {
        const theta = u * Math.PI * 2;
        const phi = v * Math.PI;

        let r = 2.2;
        r += Math.sin(theta * 3) * Math.cos(phi * 2) * 0.3;
        r += Math.sin(theta * 7 + phi * 5) * 0.15;

        const squeeze = 1 - Math.pow(Math.sin(phi), 0.3) * 0.15;

        return {
            x: r * Math.sin(phi) * Math.cos(theta) * (theta < Math.PI ? 1.02 : 0.98) * squeeze,
            y: r * Math.cos(phi) * 0.85,
            z: r * Math.sin(phi) * Math.sin(theta) * 1.1
        };
    };

    const neuronGeometry = new THREE.SphereGeometry(0.03, 8, 8);
    const neuronMaterial = new THREE.MeshBasicMaterial({
        color: 0x88ccff,
        transparent: true,
        opacity: 0.9
    });

    for (let i = 0; i < neuronCount; i++) {
        const u = Math.random();
        const v = Math.random();
        const pos = brainShape(u, v);

        const jitter = 0.15;
        pos.x += (Math.random() - 0.5) * jitter;
        pos.y += (Math.random() - 0.5) * jitter;
        pos.z += (Math.random() - 0.5) * jitter;

        const neuron = new THREE.Mesh(neuronGeometry, neuronMaterial.clone());
        neuron.position.set(pos.x, pos.y, pos.z);

        const isActive = Math.random() > 0.7;
        neuron.userData = {
            baseOpacity: 0.4 + Math.random() * 0.3,
            pulseSpeed: 0.5 + Math.random() * 2,
            pulseOffset: Math.random() * Math.PI * 2,
            isActive,
            originalPos: { ...pos }
        };

        neurons.push(neuron);
        scene.add(neuron);
    }

    const connectionMaterial = new THREE.LineBasicMaterial({
        color: 0x4488ff,
        transparent: true,
        opacity: 0.15
    });

    for (let i = 0; i < connectionCount; i++) {
        const n1 = neurons[Math.floor(Math.random() * neurons.length)];
        let n2 = neurons[Math.floor(Math.random() * neurons.length)];

        const maxDist = 0.8;
        let attempts = 0;
        while (n1.position.distanceTo(n2.position) > maxDist && attempts < 10) {
            n2 = neurons[Math.floor(Math.random() * neurons.length)];
            attempts++;
        }

        if (n1 !== n2 && n1.position.distanceTo(n2.position) <= maxDist) {
            const points = [n1.position.clone(), n2.position.clone()];
            const geometry = new THREE.BufferGeometry().setFromPoints(points);
            const line = new THREE.Line(geometry, connectionMaterial.clone());
            line.userData = {
                n1Index: neurons.indexOf(n1),
                n2Index: neurons.indexOf(n2),
                pulseProgress: Math.random(),
                pulseSpeed: 0.3 + Math.random() * 0.5,
                isPulsing: false,
                pulseDirection: Math.random() > 0.5 ? 1 : -1
            };
            connections.push(line);
            scene.add(line);
        }
    }

    const pulseParticles = [];
    const pulseGeometry = new THREE.SphereGeometry(0.02, 6, 6);
    const pulseMaterial = new THREE.MeshBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0
    });

    for (let i = 0; i < 50; i++) {
        const pulse = new THREE.Mesh(pulseGeometry, pulseMaterial.clone());
        pulse.userData = {
            active: false,
            connectionIndex: -1,
            progress: 0,
            speed: 0
        };
        pulseParticles.push(pulse);
        scene.add(pulse);
    }

    const regions = [
        { name: 'Prefrontal Cortex', u: 0.5, v: 0.25, color: 0xff6644 },
        { name: 'Motor Cortex', u: 0.5, v: 0.35, color: 0x44ff88 },
        { name: 'Sensory Cortex', u: 0.5, v: 0.45, color: 0x44aaff },
        { name: 'Visual Cortex', u: 0.5, v: 0.8, color: 0xffaa44 }
    ];

    regions.forEach((region) => {
        const pos = brainShape(region.u, region.v);
        const markerGeom = new THREE.SphereGeometry(0.08, 16, 16);
        const markerMat = new THREE.MeshBasicMaterial({
            color: region.color,
            transparent: true,
            opacity: 0.8
        });
        const marker = new THREE.Mesh(markerGeom, markerMat);
        marker.position.set(pos.x, pos.y, pos.z);
        marker.userData = { pulseOffset: Math.random() * Math.PI * 2 };
        scene.add(marker);
    });

    const coreGeometry = new THREE.SphereGeometry(0.8, 32, 32);
    const coreMaterial = new THREE.MeshBasicMaterial({
        color: 0x2244aa,
        transparent: true,
        opacity: 0.1
    });
    const core = new THREE.Mesh(coreGeometry, coreMaterial);
    core.position.y = -0.3;
    scene.add(core);

    let time = 0;

    const update = (delta, elapsed) => {
        time = elapsed;

        neurons.forEach((neuron) => {
            const { baseOpacity, pulseSpeed, pulseOffset, isActive } = neuron.userData;

            if (isActive) {
                const pulse = Math.sin(elapsed * pulseSpeed + pulseOffset);
                neuron.material.opacity = baseOpacity + pulse * 0.3;

                const scale = 1 + pulse * 0.2;
                neuron.scale.setScalar(scale);

                const hue = 0.55 + pulse * 0.1;
                neuron.material.color.setHSL(hue, 0.8, 0.6);
            }
        });

        if (Math.random() < 0.1) {
            const inactivePulse = pulseParticles.find(p => !p.userData.active);
            if (inactivePulse) {
                const connIndex = Math.floor(Math.random() * connections.length);
                const conn = connections[connIndex];

                inactivePulse.userData.active = true;
                inactivePulse.userData.connectionIndex = connIndex;
                inactivePulse.userData.progress = 0;
                inactivePulse.userData.speed = 0.8 + Math.random() * 1.2;
                inactivePulse.material.opacity = 1;
            }
        }

        pulseParticles.forEach((pulse) => {
            if (pulse.userData.active) {
                const conn = connections[pulse.userData.connectionIndex];
                if (conn) {
                    const n1 = neurons[conn.userData.n1Index];
                    const n2 = neurons[conn.userData.n2Index];

                    pulse.userData.progress += delta * pulse.userData.speed;
                    const t = pulse.userData.progress;

                    if (t >= 1) {
                        pulse.userData.active = false;
                        pulse.material.opacity = 0;

                        const targetNeuron = n2;
                        targetNeuron.material.color.setHex(0xffffff);
                        targetNeuron.scale.setScalar(2);
                        setTimeout(() => {
                            targetNeuron.scale.setScalar(1);
                        }, 100);
                    } else {
                        pulse.position.lerpVectors(n1.position, n2.position, t);
                        pulse.material.opacity = Math.sin(t * Math.PI);
                    }
                }
            }
        });

        connections.forEach((conn) => {
            const baseOpacity = 0.08 + Math.sin(elapsed * 0.5 + connections.indexOf(conn)) * 0.05;
            conn.material.opacity = baseOpacity;
        });

        core.material.opacity = 0.05 + Math.sin(elapsed * 0.8) * 0.03;
        core.scale.setScalar(1 + Math.sin(elapsed * 1.2) * 0.05);
    };

    return {
        scene,
        update,
        defaultDistance: 6,
        minDistance: 3,
        maxDistance: 15
    };
}
