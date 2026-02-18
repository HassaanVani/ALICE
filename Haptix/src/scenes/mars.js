export function createMarsScene(THREE) {
    const scene = new THREE.Scene();

    const starGeometry = new THREE.BufferGeometry();
    const starCount = 1500;
    const positions = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i++) {
        positions[i] = (Math.random() - 0.5) * 400;
    }
    starGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const starMaterial = new THREE.PointsMaterial({ color: 0xffffff, size: 0.4 });
    scene.add(new THREE.Points(starGeometry, starMaterial));

    scene.add(new THREE.AmbientLight(0x404040, 0.4));
    const sunLight = new THREE.DirectionalLight(0xfff5e6, 1.2);
    sunLight.position.set(10, 5, 10);
    scene.add(sunLight);

    const marsGroup = new THREE.Group();

    const marsGeometry = new THREE.SphereGeometry(3, 128, 128);

    const positions2 = marsGeometry.attributes.position;
    for (let i = 0; i < positions2.count; i++) {
        const x = positions2.getX(i);
        const y = positions2.getY(i);
        const z = positions2.getZ(i);

        const theta = Math.atan2(z, x);
        const phi = Math.acos(y / 3);

        let height = 0;
        height += Math.sin(theta * 3) * Math.cos(phi * 2) * 0.05;
        height += Math.sin(theta * 7 + phi * 5) * 0.02;

        if (theta > 0.5 && theta < 1.5 && phi > 1.2 && phi < 1.8) {
            height += 0.15;
        }

        if (theta > -1 && theta < 0.5 && phi > 1.4 && phi < 1.7) {
            height -= 0.1;
        }

        const len = 3 + height;
        const normalized = new THREE.Vector3(x, y, z).normalize();
        positions2.setXYZ(i, normalized.x * len, normalized.y * len, normalized.z * len);
    }
    marsGeometry.computeVertexNormals();

    const canvas = document.createElement('canvas');
    canvas.width = 1024;
    canvas.height = 512;
    const ctx = canvas.getContext('2d');

    const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
    gradient.addColorStop(0, '#c1440e');
    gradient.addColorStop(0.3, '#d4652f');
    gradient.addColorStop(0.5, '#b5451e');
    gradient.addColorStop(0.7, '#8b3a14');
    gradient.addColorStop(1, '#a04015');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    for (let i = 0; i < 200; i++) {
        ctx.beginPath();
        ctx.arc(
            Math.random() * canvas.width,
            Math.random() * canvas.height,
            Math.random() * 20 + 5,
            0, Math.PI * 2
        );
        ctx.fillStyle = `rgba(${100 + Math.random() * 80}, ${40 + Math.random() * 30}, ${10 + Math.random() * 20}, 0.3)`;
        ctx.fill();
    }

    ctx.fillStyle = '#e8d4b8';
    ctx.beginPath();
    ctx.ellipse(512, 50, 200, 40, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(512, 462, 180, 35, 0, 0, Math.PI * 2);
    ctx.fill();

    const marsTexture = new THREE.CanvasTexture(canvas);

    const marsMaterial = new THREE.MeshStandardMaterial({
        map: marsTexture,
        roughness: 0.9,
        metalness: 0.1
    });

    const mars = new THREE.Mesh(marsGeometry, marsMaterial);
    marsGroup.add(mars);

    const atmosphereGeometry = new THREE.SphereGeometry(3.15, 64, 64);
    const atmosphereMaterial = new THREE.MeshBasicMaterial({
        color: 0xffccaa,
        transparent: true,
        opacity: 0.08,
        side: THREE.BackSide
    });
    const atmosphere = new THREE.Mesh(atmosphereGeometry, atmosphereMaterial);
    marsGroup.add(atmosphere);

    scene.add(marsGroup);

    const createMoon = (name, size, distance, color) => {
        const geometry = new THREE.SphereGeometry(size, 16, 16);
        const material = new THREE.MeshStandardMaterial({
            color: color,
            roughness: 0.9,
            metalness: 0.1
        });
        const moon = new THREE.Mesh(geometry, material);
        moon.userData = {
            name,
            distance,
            angle: Math.random() * Math.PI * 2,
            speed: 0.3 / distance
        };
        return moon;
    };

    const phobos = createMoon('Phobos', 0.15, 5, 0x888888);
    const deimos = createMoon('Deimos', 0.08, 7, 0x777777);
    scene.add(phobos);
    scene.add(deimos);

    const features = [
        { name: 'Olympus Mons', lat: 18.65, lon: -133.8, type: 'volcano' },
        { name: 'Valles Marineris', lat: -14, lon: -70, type: 'canyon' }
    ];

    features.forEach((feature) => {
        const phi = (90 - feature.lat) * (Math.PI / 180);
        const theta = (feature.lon + 180) * (Math.PI / 180);

        const markerGeometry = new THREE.SphereGeometry(0.06, 8, 8);
        const markerMaterial = new THREE.MeshBasicMaterial({
            color: feature.type === 'volcano' ? 0xff6644 : 0x4488ff
        });
        const marker = new THREE.Mesh(markerGeometry, markerMaterial);

        marker.position.setFromSphericalCoords(3.2, phi, theta);
        marsGroup.add(marker);
    });

    const update = (delta, elapsed) => {
        mars.rotation.y += delta * 0.1;

        [phobos, deimos].forEach((moon) => {
            moon.userData.angle += delta * moon.userData.speed;
            moon.position.x = Math.cos(moon.userData.angle) * moon.userData.distance;
            moon.position.z = Math.sin(moon.userData.angle) * moon.userData.distance;
            moon.position.y = Math.sin(moon.userData.angle * 0.5) * 0.5;
        });
    };

    return {
        scene,
        update,
        defaultDistance: 12,
        minDistance: 5,
        maxDistance: 30
    };
}
