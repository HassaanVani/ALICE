export function createDNAScene(THREE) {
    const scene = new THREE.Scene();

    scene.add(new THREE.AmbientLight(0x404060, 0.4));
    const mainLight = new THREE.DirectionalLight(0xffffff, 0.8);
    mainLight.position.set(5, 10, 5);
    scene.add(mainLight);

    const backLight = new THREE.DirectionalLight(0x4488ff, 0.3);
    backLight.position.set(-5, -5, -5);
    scene.add(backLight);

    const dna = new THREE.Group();

    const basePairs = 40;
    const helixRadius = 2;
    const verticalSpacing = 0.5;
    const twistRate = 0.3;

    const backboneMaterial = new THREE.MeshStandardMaterial({
        color: 0x2266ff,
        metalness: 0.4,
        roughness: 0.3
    });

    const backboneMaterial2 = new THREE.MeshStandardMaterial({
        color: 0xff4466,
        metalness: 0.4,
        roughness: 0.3
    });

    const baseMaterials = [
        new THREE.MeshStandardMaterial({ color: 0x44ff66, emissive: 0x114422 }),
        new THREE.MeshStandardMaterial({ color: 0xffaa22, emissive: 0x442211 }),
        new THREE.MeshStandardMaterial({ color: 0xff4488, emissive: 0x441122 }),
        new THREE.MeshStandardMaterial({ color: 0x44aaff, emissive: 0x112244 })
    ];

    const sphereGeo = new THREE.SphereGeometry(0.25, 16, 16);
    const cylinderGeo = new THREE.CylinderGeometry(0.08, 0.08, 1, 8);

    const strand1Points = [];
    const strand2Points = [];

    for (let i = 0; i < basePairs; i++) {
        const y = (i - basePairs / 2) * verticalSpacing;
        const angle = i * twistRate;

        const x1 = Math.cos(angle) * helixRadius;
        const z1 = Math.sin(angle) * helixRadius;
        const x2 = Math.cos(angle + Math.PI) * helixRadius;
        const z2 = Math.sin(angle + Math.PI) * helixRadius;

        strand1Points.push(new THREE.Vector3(x1, y, z1));
        strand2Points.push(new THREE.Vector3(x2, y, z2));

        const node1 = new THREE.Mesh(sphereGeo, backboneMaterial);
        node1.position.set(x1, y, z1);
        dna.add(node1);

        const node2 = new THREE.Mesh(sphereGeo, backboneMaterial2);
        node2.position.set(x2, y, z2);
        dna.add(node2);

        const midX = (x1 + x2) / 2;
        const midZ = (z1 + z2) / 2;
        const distance = Math.sqrt((x2 - x1) ** 2 + (z2 - z1) ** 2);

        const baseIndex = i % 4;
        const basePair = new THREE.Mesh(
            new THREE.CylinderGeometry(0.12, 0.12, distance * 0.9, 8),
            baseMaterials[baseIndex]
        );
        basePair.position.set(midX, y, midZ);
        basePair.rotation.z = Math.PI / 2;
        basePair.rotation.y = -angle;
        dna.add(basePair);
    }

    const curve1 = new THREE.CatmullRomCurve3(strand1Points);
    const curve2 = new THREE.CatmullRomCurve3(strand2Points);

    const tubeGeo1 = new THREE.TubeGeometry(curve1, 200, 0.1, 8, false);
    const tubeGeo2 = new THREE.TubeGeometry(curve2, 200, 0.1, 8, false);

    dna.add(new THREE.Mesh(tubeGeo1, backboneMaterial));
    dna.add(new THREE.Mesh(tubeGeo2, backboneMaterial2));

    scene.add(dna);

    const particles = [];
    const particleGeo = new THREE.SphereGeometry(0.05, 8, 8);
    const particleMat = new THREE.MeshBasicMaterial({
        color: 0x88ffff,
        transparent: true,
        opacity: 0.6
    });

    for (let i = 0; i < 100; i++) {
        const p = new THREE.Mesh(particleGeo, particleMat);
        p.position.set(
            (Math.random() - 0.5) * 12,
            (Math.random() - 0.5) * 25,
            (Math.random() - 0.5) * 12
        );
        p.userData = {
            velocity: new THREE.Vector3(
                (Math.random() - 0.5) * 0.02,
                (Math.random() - 0.5) * 0.02,
                (Math.random() - 0.5) * 0.02
            )
        };
        particles.push(p);
        scene.add(p);
    }

    const update = (delta, elapsed) => {
        dna.rotation.y += delta * 0.1;

        particles.forEach(p => {
            p.position.add(p.userData.velocity);
            if (Math.abs(p.position.x) > 6) p.userData.velocity.x *= -1;
            if (Math.abs(p.position.y) > 12) p.userData.velocity.y *= -1;
            if (Math.abs(p.position.z) > 6) p.userData.velocity.z *= -1;
        });
    };

    return {
        scene,
        update,
        defaultDistance: 20,
        minDistance: 5,
        maxDistance: 50
    };
}

export const metadata = { name: "DNA", category: "Science", description: "DNA double helix", interactive: false };
export default (THREE) => createDNAScene(THREE);
