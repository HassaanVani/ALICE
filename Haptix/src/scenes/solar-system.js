export function createSolarSystemScene(THREE) {
    const scene = new THREE.Scene();

    const starGeometry = new THREE.BufferGeometry();
    const starCount = 2000;
    const positions = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i++) {
        positions[i] = (Math.random() - 0.5) * 500;
    }
    starGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const starMaterial = new THREE.PointsMaterial({ color: 0xffffff, size: 0.5 });
    scene.add(new THREE.Points(starGeometry, starMaterial));

    const sunGeometry = new THREE.SphereGeometry(2, 64, 64);
    const sunMaterial = new THREE.MeshBasicMaterial({ color: 0xffdd44 });
    const sun = new THREE.Mesh(sunGeometry, sunMaterial);
    scene.add(sun);

    const sunGlowGeometry = new THREE.SphereGeometry(2.3, 32, 32);
    const sunGlowMaterial = new THREE.MeshBasicMaterial({
        color: 0xffaa00,
        transparent: true,
        opacity: 0.3
    });
    const sunGlow = new THREE.Mesh(sunGlowGeometry, sunGlowMaterial);
    scene.add(sunGlow);

    const sunLight = new THREE.PointLight(0xffffff, 2, 100);
    scene.add(sunLight);
    scene.add(new THREE.AmbientLight(0x333333));

    const planets = [];
    const planetData = [
        { name: 'Mercury', color: 0x8c7853, size: 0.15, distance: 4, speed: 4.15 },
        { name: 'Venus', color: 0xffc649, size: 0.25, distance: 5.5, speed: 1.62 },
        { name: 'Earth', color: 0x6b93d6, size: 0.26, distance: 7, speed: 1.0 },
        { name: 'Mars', color: 0xc1440e, size: 0.18, distance: 9, speed: 0.53 },
        { name: 'Jupiter', color: 0xd8ca9d, size: 0.7, distance: 13, speed: 0.084 },
        { name: 'Saturn', color: 0xead6b8, size: 0.6, distance: 17, speed: 0.034 },
        { name: 'Uranus', color: 0xd1e7e7, size: 0.4, distance: 21, speed: 0.012 },
        { name: 'Neptune', color: 0x5b5ddf, size: 0.38, distance: 25, speed: 0.006 }
    ];

    planetData.forEach((data) => {
        const geometry = new THREE.SphereGeometry(data.size, 32, 32);
        const material = new THREE.MeshStandardMaterial({ color: data.color });
        const planet = new THREE.Mesh(geometry, material);
        planet.userData = { ...data, angle: Math.random() * Math.PI * 2 };
        planets.push(planet);
        scene.add(planet);

        if (data.name === 'Saturn') {
            const ringGeometry = new THREE.RingGeometry(data.size * 1.4, data.size * 2, 64);
            const ringMaterial = new THREE.MeshBasicMaterial({
                color: 0xc9b896,
                side: THREE.DoubleSide,
                transparent: true,
                opacity: 0.7
            });
            const ring = new THREE.Mesh(ringGeometry, ringMaterial);
            ring.rotation.x = Math.PI / 2.5;
            planet.add(ring);
        }

        const orbitGeometry = new THREE.RingGeometry(data.distance - 0.02, data.distance + 0.02, 128);
        const orbitMaterial = new THREE.MeshBasicMaterial({
            color: 0x444466,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.3
        });
        const orbit = new THREE.Mesh(orbitGeometry, orbitMaterial);
        orbit.rotation.x = -Math.PI / 2;
        scene.add(orbit);
    });

    const update = (delta, elapsed) => {
        sun.rotation.y += delta * 0.1;
        sunGlow.rotation.y -= delta * 0.05;

        planets.forEach((planet) => {
            planet.userData.angle += delta * planet.userData.speed * 0.2;
            planet.position.x = Math.cos(planet.userData.angle) * planet.userData.distance;
            planet.position.z = Math.sin(planet.userData.angle) * planet.userData.distance;
            planet.rotation.y += delta;
        });
    };

    return {
        scene,
        update,
        defaultDistance: 35,
        minDistance: 8,
        maxDistance: 80
    };
}
