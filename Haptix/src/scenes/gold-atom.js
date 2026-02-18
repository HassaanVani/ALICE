export function createGoldAtomScene(THREE) {
    const scene = new THREE.Scene();

    scene.add(new THREE.AmbientLight(0x404040, 0.5));
    const mainLight = new THREE.PointLight(0xffd700, 1, 50);
    mainLight.position.set(5, 5, 5);
    scene.add(mainLight);

    const nucleus = new THREE.Group();
    const protonCount = 79;
    const neutronCount = 118;

    const quarkColors = {
        up: 0xff3366,
        down: 0x3366ff,
        gluon: 0xffff00
    };

    function createNucleonWithQuarks(isProton) {
        const nucleon = new THREE.Group();

        const shellGeo = new THREE.SphereGeometry(0.12, 16, 16);
        const shellMat = new THREE.MeshStandardMaterial({
            color: isProton ? 0xff4444 : 0x4444ff,
            transparent: true,
            opacity: 0.3,
            metalness: 0.3,
            roughness: 0.7
        });
        const shell = new THREE.Mesh(shellGeo, shellMat);
        nucleon.add(shell);

        const quarkGeo = new THREE.SphereGeometry(0.035, 8, 8);
        const quarks = isProton ? ['up', 'up', 'down'] : ['up', 'down', 'down'];

        quarks.forEach((type, i) => {
            const quarkMat = new THREE.MeshStandardMaterial({
                color: quarkColors[type],
                emissive: quarkColors[type],
                emissiveIntensity: 0.5
            });
            const quark = new THREE.Mesh(quarkGeo, quarkMat);
            const angle = (i / 3) * Math.PI * 2;
            quark.position.set(
                Math.cos(angle) * 0.06,
                Math.sin(angle) * 0.06,
                (Math.random() - 0.5) * 0.04
            );
            quark.userData = { baseAngle: angle, speed: 2 + Math.random() };
            nucleon.add(quark);
        });

        const gluonGeo = new THREE.TorusGeometry(0.05, 0.008, 8, 16);
        const gluonMat = new THREE.MeshBasicMaterial({
            color: quarkColors.gluon,
            transparent: true,
            opacity: 0.6
        });
        for (let i = 0; i < 3; i++) {
            const gluon = new THREE.Mesh(gluonGeo, gluonMat);
            gluon.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, 0);
            nucleon.add(gluon);
        }

        return nucleon;
    }

    const totalNucleons = protonCount + neutronCount;
    const nucleusRadius = Math.pow(totalNucleons, 1 / 3) * 0.18;
    const nucleons = [];

    for (let i = 0; i < protonCount; i++) {
        const proton = createNucleonWithQuarks(true);
        const phi = Math.acos(2 * Math.random() - 1);
        const theta = Math.random() * Math.PI * 2;
        const r = nucleusRadius * Math.cbrt(Math.random());
        proton.position.setFromSphericalCoords(r, phi, theta);
        nucleus.add(proton);
        nucleons.push(proton);
    }

    for (let i = 0; i < neutronCount; i++) {
        const neutron = createNucleonWithQuarks(false);
        const phi = Math.acos(2 * Math.random() - 1);
        const theta = Math.random() * Math.PI * 2;
        const r = nucleusRadius * Math.cbrt(Math.random());
        neutron.position.setFromSphericalCoords(r, phi, theta);
        nucleus.add(neutron);
        nucleons.push(neutron);
    }

    scene.add(nucleus);

    const nucleusGlow = new THREE.Mesh(
        new THREE.SphereGeometry(nucleusRadius * 1.3, 32, 32),
        new THREE.MeshBasicMaterial({
            color: 0xffd700,
            transparent: true,
            opacity: 0.1
        })
    );
    scene.add(nucleusGlow);

    const electrons = [];
    const shells = [2, 8, 18, 32, 18, 1];
    const shellRadii = [1.8, 3, 4.5, 6.2, 8, 9.5];

    const electronGeometry = new THREE.SphereGeometry(0.06, 12, 12);
    const electronMaterial = new THREE.MeshStandardMaterial({
        color: 0x44ff44,
        emissive: 0x22ff22,
        emissiveIntensity: 0.3,
        metalness: 0.5,
        roughness: 0.3
    });

    shells.forEach((count, shellIndex) => {
        const radius = shellRadii[shellIndex];

        const cloudGeo = new THREE.SphereGeometry(radius, 32, 32);
        const cloudMat = new THREE.MeshBasicMaterial({
            color: 0x44ff44,
            transparent: true,
            opacity: 0.02,
            side: THREE.DoubleSide
        });
        scene.add(new THREE.Mesh(cloudGeo, cloudMat));

        for (let i = 0; i < count; i++) {
            const electron = new THREE.Mesh(electronGeometry, electronMaterial);
            const angle = (i / count) * Math.PI * 2;
            const tilt = Math.random() * Math.PI;
            electron.userData = {
                radius,
                angle,
                tilt,
                speed: 0.8 + (1 / (shellIndex + 1)) * 1.5,
                axis: new THREE.Vector3(
                    Math.random() - 0.5,
                    Math.random() - 0.5,
                    Math.random() - 0.5
                ).normalize()
            };
            electrons.push(electron);
            scene.add(electron);
        }
    });

    const update = (delta, elapsed) => {
        nucleus.rotation.y += delta * 0.15;
        nucleusGlow.scale.setScalar(1 + Math.sin(elapsed * 2) * 0.05);

        nucleons.forEach(nucleon => {
            nucleon.children.forEach((child, i) => {
                if (i > 0 && i < 4 && child.userData.speed) {
                    child.userData.baseAngle += delta * child.userData.speed;
                    const angle = child.userData.baseAngle;
                    child.position.set(
                        Math.cos(angle) * 0.06,
                        Math.sin(angle) * 0.06,
                        Math.sin(angle * 2) * 0.02
                    );
                }
            });
        });

        electrons.forEach((electron) => {
            const { radius, speed, axis } = electron.userData;
            electron.userData.angle += delta * speed;
            const angle = electron.userData.angle;

            const pos = new THREE.Vector3(
                Math.cos(angle) * radius,
                Math.sin(angle) * radius * 0.3,
                Math.sin(angle) * radius
            );
            pos.applyAxisAngle(axis, electron.userData.tilt);
            electron.position.copy(pos);
        });
    };

    return {
        scene,
        update,
        defaultDistance: 18,
        minDistance: 2,
        maxDistance: 40
    };
}

export const metadata = { name: "Gold Atom", category: "Science", description: "Atomic structure of gold", interactive: false };
export default (THREE) => createGoldAtomScene(THREE);
