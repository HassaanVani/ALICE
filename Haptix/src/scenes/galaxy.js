export function createGalaxyScene(THREE) {
    const scene = new THREE.Scene();

    const bgStars = new THREE.BufferGeometry();
    const bgCount = 5000;
    const bgPos = new Float32Array(bgCount * 3);
    for (let i = 0; i < bgCount * 3; i += 3) {
        const r = 100 + Math.random() * 200;
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        bgPos[i] = r * Math.sin(phi) * Math.cos(theta);
        bgPos[i + 1] = r * Math.sin(phi) * Math.sin(theta);
        bgPos[i + 2] = r * Math.cos(phi);
    }
    bgStars.setAttribute('position', new THREE.BufferAttribute(bgPos, 3));
    scene.add(new THREE.Points(bgStars, new THREE.PointsMaterial({ color: 0xffffff, size: 0.2 })));

    const galaxy = new THREE.Group();

    const coreGeo = new THREE.SphereGeometry(3, 32, 32);
    const coreMat = new THREE.MeshBasicMaterial({
        color: 0xffffcc,
        transparent: true,
        opacity: 0.9
    });
    const core = new THREE.Mesh(coreGeo, coreMat);
    galaxy.add(core);

    for (let i = 1; i <= 4; i++) {
        const glow = new THREE.Mesh(
            new THREE.SphereGeometry(3 + i * 1.5, 32, 32),
            new THREE.MeshBasicMaterial({
                color: new THREE.Color().setHSL(0.12, 0.5, 0.5),
                transparent: true,
                opacity: 0.15 - i * 0.03
            })
        );
        galaxy.add(glow);
    }

    const armStars = [];
    const armCount = 4;
    const starsPerArm = 2000;

    const starGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(armCount * starsPerArm * 3);
    const colors = new Float32Array(armCount * starsPerArm * 3);

    let idx = 0;
    for (let arm = 0; arm < armCount; arm++) {
        const armOffset = (arm / armCount) * Math.PI * 2;

        for (let i = 0; i < starsPerArm; i++) {
            const distance = 5 + Math.pow(Math.random(), 0.5) * 40;
            const angle = armOffset + distance * 0.12 + (Math.random() - 0.5) * 0.5;
            const spread = (Math.random() - 0.5) * (distance * 0.15);

            positions[idx * 3] = Math.cos(angle) * distance + spread * 0.5;
            positions[idx * 3 + 1] = (Math.random() - 0.5) * (2 - distance * 0.02);
            positions[idx * 3 + 2] = Math.sin(angle) * distance + spread;

            const hue = 0.55 + Math.random() * 0.15;
            const color = new THREE.Color().setHSL(hue, 0.6, 0.6 + Math.random() * 0.3);
            colors[idx * 3] = color.r;
            colors[idx * 3 + 1] = color.g;
            colors[idx * 3 + 2] = color.b;

            idx++;
        }
    }

    starGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    starGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const starMat = new THREE.PointsMaterial({
        size: 0.3,
        vertexColors: true,
        transparent: true,
        opacity: 0.9
    });
    const stars = new THREE.Points(starGeo, starMat);
    galaxy.add(stars);

    const dustClouds = [];
    const dustMat = new THREE.MeshBasicMaterial({
        color: 0x442266,
        transparent: true,
        opacity: 0.1,
        side: THREE.DoubleSide
    });
    for (let i = 0; i < 20; i++) {
        const dust = new THREE.Mesh(
            new THREE.PlaneGeometry(15 + Math.random() * 10, 8 + Math.random() * 5),
            dustMat
        );
        const angle = Math.random() * Math.PI * 2;
        const r = 10 + Math.random() * 25;
        dust.position.set(Math.cos(angle) * r, 0, Math.sin(angle) * r);
        dust.rotation.x = Math.PI / 2 + (Math.random() - 0.5) * 0.3;
        dust.rotation.z = angle;
        dustClouds.push(dust);
        galaxy.add(dust);
    }

    scene.add(galaxy);

    const update = (delta, elapsed) => {
        galaxy.rotation.y += delta * 0.02;

        core.scale.setScalar(1 + Math.sin(elapsed) * 0.02);

        const posAttr = stars.geometry.attributes.position;
        for (let i = 0; i < posAttr.count; i++) {
            const x = posAttr.getX(i);
            const z = posAttr.getZ(i);
            const angle = Math.atan2(z, x);
            const dist = Math.sqrt(x * x + z * z);
            const speed = 0.001 / (dist * 0.1 + 1);
            const newAngle = angle + speed;
            posAttr.setX(i, Math.cos(newAngle) * dist);
            posAttr.setZ(i, Math.sin(newAngle) * dist);
        }
        posAttr.needsUpdate = true;
    };

    return {
        scene,
        update,
        defaultDistance: 60,
        minDistance: 10,
        maxDistance: 150
    };
}

export const metadata = { name: "Galaxy", category: "Space", description: "Spiral galaxy simulation", interactive: false };
export default (THREE) => createGalaxyScene(THREE);
