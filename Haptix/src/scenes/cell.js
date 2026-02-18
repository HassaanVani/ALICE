export function createCellScene(THREE) {
    const scene = new THREE.Scene();

    scene.add(new THREE.AmbientLight(0x404060, 0.5));
    const mainLight = new THREE.DirectionalLight(0xffffff, 0.6);
    mainLight.position.set(5, 5, 5);
    scene.add(mainLight);

    const cell = new THREE.Group();

    const membraneMat = new THREE.MeshPhysicalMaterial({
        color: 0xffccaa,
        transparent: true,
        opacity: 0.3,
        roughness: 0.2,
        metalness: 0,
        side: THREE.DoubleSide
    });
    const membrane = new THREE.Mesh(
        new THREE.SphereGeometry(8, 64, 64),
        membraneMat
    );
    cell.add(membrane);

    const nucleusMat = new THREE.MeshPhysicalMaterial({
        color: 0x6644aa,
        transparent: true,
        opacity: 0.7,
        roughness: 0.3
    });
    const nucleus = new THREE.Mesh(
        new THREE.SphereGeometry(2.5, 32, 32),
        nucleusMat
    );
    cell.add(nucleus);

    const nucleolusMat = new THREE.MeshStandardMaterial({
        color: 0x442288,
        emissive: 0x221144
    });
    const nucleolus = new THREE.Mesh(
        new THREE.SphereGeometry(0.8, 16, 16),
        nucleolusMat
    );
    nucleolus.position.set(0.5, 0.3, 0);
    nucleus.add(nucleolus);

    const mitoMat = new THREE.MeshStandardMaterial({
        color: 0xff6644,
        emissive: 0x331111
    });
    const mitochondria = [];
    for (let i = 0; i < 15; i++) {
        const mito = new THREE.Group();

        const outer = new THREE.Mesh(
            new THREE.CapsuleGeometry(0.4, 1.2, 8, 16),
            mitoMat
        );
        mito.add(outer);

        const cristaMat = new THREE.MeshBasicMaterial({ color: 0xffaa88 });
        for (let j = 0; j < 4; j++) {
            const crista = new THREE.Mesh(
                new THREE.PlaneGeometry(0.6, 0.3),
                cristaMat
            );
            crista.position.y = -0.4 + j * 0.25;
            crista.rotation.x = Math.PI / 2;
            mito.add(crista);
        }

        const angle = Math.random() * Math.PI * 2;
        const r = 3.5 + Math.random() * 3.5;
        mito.position.set(
            Math.cos(angle) * r,
            (Math.random() - 0.5) * 6,
            Math.sin(angle) * r
        );
        mito.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, 0);
        mito.userData = { rotSpeed: (Math.random() - 0.5) * 0.2 };
        mitochondria.push(mito);
        cell.add(mito);
    }

    const erGroup = new THREE.Group();
    const erMat = new THREE.MeshStandardMaterial({
        color: 0x44aa88,
        transparent: true,
        opacity: 0.6
    });
    for (let i = 0; i < 8; i++) {
        const tube = new THREE.Mesh(
            new THREE.TorusGeometry(2.8 + i * 0.15, 0.08, 8, 50),
            erMat
        );
        tube.rotation.x = Math.PI / 2 + (Math.random() - 0.5) * 0.3;
        tube.rotation.y = Math.random() * 0.3;
        tube.position.y = (i - 4) * 0.3;
        erGroup.add(tube);
    }
    erGroup.position.x = -3;
    cell.add(erGroup);

    const ribosomes = [];
    const riboMat = new THREE.MeshStandardMaterial({ color: 0x8866aa });
    for (let i = 0; i < 80; i++) {
        const ribo = new THREE.Mesh(
            new THREE.SphereGeometry(0.12, 8, 8),
            riboMat
        );
        const angle = Math.random() * Math.PI * 2;
        const r = 2 + Math.random() * 5.5;
        ribo.position.set(
            Math.cos(angle) * r,
            (Math.random() - 0.5) * 6,
            Math.sin(angle) * r
        );
        ribo.userData = {
            basePos: ribo.position.clone(),
            phase: Math.random() * Math.PI * 2
        };
        ribosomes.push(ribo);
        cell.add(ribo);
    }

    const golgiGroup = new THREE.Group();
    const golgiMat = new THREE.MeshStandardMaterial({
        color: 0xffcc44,
        transparent: true,
        opacity: 0.7
    });
    for (let i = 0; i < 5; i++) {
        const disc = new THREE.Mesh(
            new THREE.CylinderGeometry(1.2 - i * 0.1, 1.2 - i * 0.1, 0.15, 32),
            golgiMat
        );
        disc.position.y = i * 0.25;
        disc.rotation.x = 0.1 * i;
        golgiGroup.add(disc);
    }
    golgiGroup.position.set(4, 0, 2);
    cell.add(golgiGroup);

    scene.add(cell);

    const update = (delta, elapsed) => {
        cell.rotation.y += delta * 0.05;

        nucleus.position.x = Math.sin(elapsed * 0.3) * 0.2;
        nucleus.position.y = Math.cos(elapsed * 0.4) * 0.2;

        mitochondria.forEach(mito => {
            mito.rotation.z += delta * mito.userData.rotSpeed;
        });

        ribosomes.forEach(ribo => {
            const { basePos, phase } = ribo.userData;
            ribo.position.x = basePos.x + Math.sin(elapsed + phase) * 0.1;
            ribo.position.y = basePos.y + Math.cos(elapsed * 1.3 + phase) * 0.1;
        });

        erGroup.rotation.y += delta * 0.02;
        golgiGroup.rotation.y -= delta * 0.03;
    };

    return {
        scene,
        update,
        defaultDistance: 20,
        minDistance: 5,
        maxDistance: 50
    };
}

export const metadata = { name: "Cell", category: "Science", description: "Biological cell cross-section", interactive: false };
export default (THREE) => createCellScene(THREE);
