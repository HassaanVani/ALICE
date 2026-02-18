export function createBlackHoleScene(THREE) {
    const scene = new THREE.Scene();

    const starGeo = new THREE.BufferGeometry();
    const starCount = 3000;
    const starPositions = new Float32Array(starCount * 3);

    for (let i = 0; i < starCount * 3; i += 3) {
        const r = 50 + Math.random() * 150;
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        starPositions[i] = r * Math.sin(phi) * Math.cos(theta);
        starPositions[i + 1] = r * Math.sin(phi) * Math.sin(theta);
        starPositions[i + 2] = r * Math.cos(phi);
    }

    starGeo.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
    const starMat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.3 });
    scene.add(new THREE.Points(starGeo, starMat));

    const eventHorizon = new THREE.Mesh(
        new THREE.SphereGeometry(3, 64, 64),
        new THREE.MeshBasicMaterial({ color: 0x000000 })
    );
    scene.add(eventHorizon);

    const glowLayers = [];
    for (let i = 0; i < 5; i++) {
        const glow = new THREE.Mesh(
            new THREE.SphereGeometry(3.2 + i * 0.3, 32, 32),
            new THREE.MeshBasicMaterial({
                color: new THREE.Color().setHSL(0.05 + i * 0.02, 1, 0.5),
                transparent: true,
                opacity: 0.1 - i * 0.015,
                side: THREE.BackSide
            })
        );
        glowLayers.push(glow);
        scene.add(glow);
    }

    const diskGroup = new THREE.Group();
    const diskSegments = 200;
    const diskRings = 30;

    for (let r = 0; r < diskRings; r++) {
        const ringRadius = 5 + r * 0.8;
        const ringGeo = new THREE.TorusGeometry(ringRadius, 0.15 + Math.random() * 0.1, 8, diskSegments);
        const hue = 0.08 - r * 0.002;
        const ringMat = new THREE.MeshBasicMaterial({
            color: new THREE.Color().setHSL(hue, 1, 0.4 + Math.random() * 0.2),
            transparent: true,
            opacity: 0.7 - r * 0.02
        });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.rotation.x = Math.PI / 2 + (Math.random() - 0.5) * 0.1;
        ring.userData = { baseSpeed: 0.5 / (r + 1) };
        diskGroup.add(ring);
    }
    scene.add(diskGroup);

    const jets = [];
    for (let sign of [-1, 1]) {
        const jetGroup = new THREE.Group();
        for (let i = 0; i < 50; i++) {
            const size = 0.3 - i * 0.005;
            const particle = new THREE.Mesh(
                new THREE.SphereGeometry(size, 8, 8),
                new THREE.MeshBasicMaterial({
                    color: new THREE.Color().setHSL(0.6, 0.8, 0.6),
                    transparent: true,
                    opacity: 0.8 - i * 0.015
                })
            );
            particle.position.y = sign * (4 + i * 0.6);
            particle.position.x = (Math.random() - 0.5) * (i * 0.1);
            particle.position.z = (Math.random() - 0.5) * (i * 0.1);
            jetGroup.add(particle);
        }
        jets.push(jetGroup);
        scene.add(jetGroup);
    }

    const lensingRing = new THREE.Mesh(
        new THREE.TorusGeometry(4, 0.3, 16, 100),
        new THREE.MeshBasicMaterial({
            color: 0xffffff,
            transparent: true,
            opacity: 0.3
        })
    );
    scene.add(lensingRing);

    const update = (delta, elapsed) => {
        diskGroup.children.forEach((ring, i) => {
            ring.rotation.z += delta * ring.userData.baseSpeed;
        });

        jets.forEach(jet => {
            jet.rotation.y += delta * 0.2;
        });

        lensingRing.rotation.x = Math.sin(elapsed * 0.5) * 0.3;
        lensingRing.rotation.y = elapsed * 0.1;

        glowLayers.forEach((glow, i) => {
            glow.scale.setScalar(1 + Math.sin(elapsed * 2 + i) * 0.05);
        });
    };

    return {
        scene,
        update,
        defaultDistance: 35,
        minDistance: 8,
        maxDistance: 100
    };
}

export const metadata = { name: "Black Hole", category: "Space", description: "Black hole gravitational lensing", interactive: false };
export default (THREE) => createBlackHoleScene(THREE);
