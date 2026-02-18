import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export function createCustomModelScene(THREE, modelUrl) {
    const scene = new THREE.Scene();

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));

    const keyLight = new THREE.DirectionalLight(0xffffff, 1);
    keyLight.position.set(5, 10, 5);
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0xffffff, 0.4);
    fillLight.position.set(-5, 0, -5);
    scene.add(fillLight);

    const gridHelper = new THREE.GridHelper(20, 20, 0x444444, 0x222222);
    scene.add(gridHelper);

    let model = null;
    let mixer = null;

    const loader = new GLTFLoader();
    loader.load(
        modelUrl,
        (gltf) => {
            model = gltf.scene;

            const box = new THREE.Box3().setFromObject(model);
            const size = box.getSize(new THREE.Vector3());
            const center = box.getCenter(new THREE.Vector3());

            const maxDim = Math.max(size.x, size.y, size.z);
            const scale = 5 / maxDim;
            model.scale.setScalar(scale);

            model.position.sub(center.multiplyScalar(scale));
            model.position.y = 0;

            scene.add(model);

            if (gltf.animations && gltf.animations.length > 0) {
                mixer = new THREE.AnimationMixer(model);
                gltf.animations.forEach((clip) => {
                    mixer.clipAction(clip).play();
                });
            }
        },
        undefined,
        (error) => {
            console.error('Error loading model:', error);
        }
    );

    const update = (delta, elapsed) => {
        if (mixer) {
            mixer.update(delta);
        }
    };

    return {
        scene,
        update,
        defaultDistance: 10,
        minDistance: 2,
        maxDistance: 50
    };
}

export const metadata = { name: "Custom Model", category: "Custom", description: "Upload your own 3D model", interactive: false };
export default (THREE, url) => createCustomModelScene(THREE, url);
