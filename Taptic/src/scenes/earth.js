export function createEarthScene(THREE) {
    const scene = new THREE.Scene();

    scene.add(new THREE.AmbientLight(0x333344, 0.3));
    const sunLight = new THREE.DirectionalLight(0xffffee, 1.2);
    sunLight.position.set(50, 20, 30);
    scene.add(sunLight);

    const earthGroup = new THREE.Group();

    const textureLoader = new THREE.TextureLoader();

    const earthGeo = new THREE.SphereGeometry(5, 64, 64);
    const earthMat = new THREE.MeshPhongMaterial({
        color: 0x2244aa,
        emissive: 0x112233,
        shininess: 25
    });
    const earth = new THREE.Mesh(earthGeo, earthMat);
    earthGroup.add(earth);

    const landGeo = new THREE.IcosahedronGeometry(5.02, 4);
    const landPositions = landGeo.attributes.position;
    for (let i = 0; i < landPositions.count; i++) {
        const x = landPositions.getX(i);
        const y = landPositions.getY(i);
        const z = landPositions.getZ(i);
        const noise = Math.sin(x * 2) * Math.cos(y * 3) * Math.sin(z * 2);
        if (noise > 0.2) {
            const scale = 1.01 + noise * 0.015;
            landPositions.setXYZ(i, x * scale, y * scale, z * scale);
        }
    }
    landGeo.computeVertexNormals();
    const landMat = new THREE.MeshPhongMaterial({
        color: 0x228833,
        emissive: 0x112211,
        flatShading: true
    });
    const land = new THREE.Mesh(landGeo, landMat);
    earthGroup.add(land);

    const cloudGeo = new THREE.SphereGeometry(5.15, 48, 48);
    const cloudMat = new THREE.MeshPhongMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.4,
        depthWrite: false
    });
    const clouds = new THREE.Mesh(cloudGeo, cloudMat);
    earthGroup.add(clouds);

    const atmosGeo = new THREE.SphereGeometry(5.4, 48, 48);
    const atmosMat = new THREE.MeshBasicMaterial({
        color: 0x4488ff,
        transparent: true,
        opacity: 0.15,
        side: THREE.BackSide
    });
    const atmosphere = new THREE.Mesh(atmosGeo, atmosMat);
    earthGroup.add(atmosphere);

    earthGroup.rotation.z = 0.41;
    scene.add(earthGroup);

    const moonGroup = new THREE.Group();
    const moonGeo = new THREE.SphereGeometry(1.2, 32, 32);
    const moonMat = new THREE.MeshPhongMaterial({
        color: 0xaaaaaa,
        emissive: 0x222222
    });
    const moon = new THREE.Mesh(moonGeo, moonMat);

    const craterGeo = new THREE.CircleGeometry(0.15, 16);
    const craterMat = new THREE.MeshBasicMaterial({ color: 0x666666 });
    for (let i = 0; i < 20; i++) {
        const crater = new THREE.Mesh(craterGeo, craterMat);
        const phi = Math.acos(2 * Math.random() - 1);
        const theta = Math.random() * Math.PI * 2;
        crater.position.setFromSphericalCoords(1.21, phi, theta);
        crater.lookAt(0, 0, 0);
        moon.add(crater);
    }

    moonGroup.add(moon);
    moon.position.x = 15;
    scene.add(moonGroup);

    const orbitGeo = new THREE.TorusGeometry(15, 0.02, 8, 100);
    const orbitMat = new THREE.MeshBasicMaterial({
        color: 0x444466,
        transparent: true,
        opacity: 0.3
    });
    const orbit = new THREE.Mesh(orbitGeo, orbitMat);
    orbit.rotation.x = Math.PI / 2;
    scene.add(orbit);

    const satellites = [];
    const satGeo = new THREE.BoxGeometry(0.1, 0.1, 0.3);
    const panelGeo = new THREE.BoxGeometry(0.4, 0.02, 0.15);
    const satMat = new THREE.MeshStandardMaterial({ color: 0xcccccc, metalness: 0.8 });
    const panelMat = new THREE.MeshStandardMaterial({ color: 0x2244aa, metalness: 0.3 });

    for (let i = 0; i < 8; i++) {
        const sat = new THREE.Group();
        sat.add(new THREE.Mesh(satGeo, satMat));

        const panel1 = new THREE.Mesh(panelGeo, panelMat);
        panel1.position.x = 0.25;
        sat.add(panel1);

        const panel2 = new THREE.Mesh(panelGeo, panelMat);
        panel2.position.x = -0.25;
        sat.add(panel2);

        sat.userData = {
            radius: 6 + Math.random() * 2,
            angle: Math.random() * Math.PI * 2,
            speed: 0.3 + Math.random() * 0.3,
            inclination: (Math.random() - 0.5) * 0.5
        };
        satellites.push(sat);
        scene.add(sat);
    }

    const starGeo = new THREE.BufferGeometry();
    const starCount = 2000;
    const starPos = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i += 3) {
        const r = 80 + Math.random() * 120;
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        starPos[i] = r * Math.sin(phi) * Math.cos(theta);
        starPos[i + 1] = r * Math.sin(phi) * Math.sin(theta);
        starPos[i + 2] = r * Math.cos(phi);
    }
    starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
    scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xffffff, size: 0.2 })));

    const update = (delta, elapsed) => {
        earth.rotation.y += delta * 0.1;
        clouds.rotation.y += delta * 0.12;

        moonGroup.rotation.y += delta * 0.03;
        moon.rotation.y += delta * 0.02;

        satellites.forEach(sat => {
            sat.userData.angle += delta * sat.userData.speed;
            const { radius, angle, inclination } = sat.userData;
            sat.position.set(
                Math.cos(angle) * radius,
                Math.sin(inclination) * Math.sin(angle) * radius * 0.3,
                Math.sin(angle) * radius
            );
            sat.lookAt(0, 0, 0);
        });
    };

    return {
        scene,
        update,
        defaultDistance: 18,
        minDistance: 7,
        maxDistance: 60
    };
}
