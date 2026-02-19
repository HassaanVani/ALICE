/**
 * Robotic Arm Scene — 5-DOF arm visualization driven by PuppetBridge data.
 * Receives arm_position updates and animates joint rotations in real-time.
 */

export function createRoboticArmScene(THREE) {
    const scene = new THREE.Scene();

    // ── Lighting ──
    const ambientLight = new THREE.AmbientLight(0x404050, 0.6);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(5, 10, 7);
    dirLight.castShadow = true;
    scene.add(dirLight);

    const rimLight = new THREE.DirectionalLight(0x6366f1, 0.3);
    rimLight.position.set(-5, 3, -5);
    scene.add(rimLight);

    // ── Ground plane ──
    const groundGeometry = new THREE.PlaneGeometry(20, 20);
    const groundMaterial = new THREE.MeshStandardMaterial({
        color: 0x1a1a2e,
        roughness: 0.8,
        metalness: 0.2,
    });
    const ground = new THREE.Mesh(groundGeometry, groundMaterial);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.01;
    ground.receiveShadow = true;
    scene.add(ground);

    // Grid overlay
    const grid = new THREE.GridHelper(20, 40, 0x2a2a4a, 0x1a1a3a);
    grid.position.y = 0;
    scene.add(grid);

    // ── Materials ──
    const baseMat = new THREE.MeshStandardMaterial({
        color: 0x2d2d44,
        roughness: 0.4,
        metalness: 0.6,
    });

    const jointMat = new THREE.MeshStandardMaterial({
        color: 0x6366f1,
        roughness: 0.3,
        metalness: 0.7,
        emissive: 0x1a1a4a,
        emissiveIntensity: 0.3,
    });

    const segmentMat = new THREE.MeshStandardMaterial({
        color: 0x3d3d5c,
        roughness: 0.5,
        metalness: 0.5,
    });

    const gripperMat = new THREE.MeshStandardMaterial({
        color: 0x8b5cf6,
        roughness: 0.3,
        metalness: 0.6,
        emissive: 0x2a1a5a,
        emissiveIntensity: 0.2,
    });

    const activeMat = new THREE.MeshStandardMaterial({
        color: 0x22c55e,
        roughness: 0.3,
        metalness: 0.6,
        emissive: 0x0a4a1a,
        emissiveIntensity: 0.4,
    });

    // ── Arm structure (5-DOF) ──
    // Joint hierarchy: base (yaw) → shoulder (pitch) → elbow (pitch) → wrist pitch → wrist roll
    const ARM_LENGTHS = {
        base: 0.4,
        shoulder: 2.0,
        elbow: 1.8,
        wrist: 1.2,
        gripper: 0.4,
    };

    // Base platform
    const baseGeo = new THREE.CylinderGeometry(0.8, 1.0, ARM_LENGTHS.base, 32);
    const baseMesh = new THREE.Mesh(baseGeo, baseMat);
    baseMesh.position.y = ARM_LENGTHS.base / 2;
    baseMesh.castShadow = true;
    scene.add(baseMesh);

    // Joint 0: Base rotation (yaw) — pivot on top of base
    const joint0 = new THREE.Group();
    joint0.position.y = ARM_LENGTHS.base;
    baseMesh.add(joint0);

    const joint0Sphere = new THREE.Mesh(
        new THREE.SphereGeometry(0.25, 16, 16),
        jointMat
    );
    joint0.add(joint0Sphere);

    // Shoulder segment
    const shoulderGeo = new THREE.CylinderGeometry(0.15, 0.18, ARM_LENGTHS.shoulder, 12);
    const shoulderMesh = new THREE.Mesh(shoulderGeo, segmentMat);
    shoulderMesh.position.y = ARM_LENGTHS.shoulder / 2;
    shoulderMesh.castShadow = true;

    // Joint 1: Shoulder (pitch)
    const joint1 = new THREE.Group();
    joint0.add(joint1);
    joint1.add(shoulderMesh);

    const joint1Sphere = new THREE.Mesh(
        new THREE.SphereGeometry(0.2, 16, 16),
        jointMat
    );
    joint1Sphere.position.y = ARM_LENGTHS.shoulder;
    joint1.add(joint1Sphere);

    // Elbow segment
    const elbowGeo = new THREE.CylinderGeometry(0.12, 0.15, ARM_LENGTHS.elbow, 12);
    const elbowMesh = new THREE.Mesh(elbowGeo, segmentMat);
    elbowMesh.position.y = ARM_LENGTHS.elbow / 2;
    elbowMesh.castShadow = true;

    // Joint 2: Elbow (pitch)
    const joint2 = new THREE.Group();
    joint2.position.y = ARM_LENGTHS.shoulder;
    joint1.add(joint2);
    joint2.add(elbowMesh);

    const joint2Sphere = new THREE.Mesh(
        new THREE.SphereGeometry(0.16, 16, 16),
        jointMat
    );
    joint2Sphere.position.y = ARM_LENGTHS.elbow;
    joint2.add(joint2Sphere);

    // Wrist segment
    const wristGeo = new THREE.CylinderGeometry(0.08, 0.12, ARM_LENGTHS.wrist, 12);
    const wristMesh = new THREE.Mesh(wristGeo, segmentMat);
    wristMesh.position.y = ARM_LENGTHS.wrist / 2;
    wristMesh.castShadow = true;

    // Joint 3: Wrist pitch
    const joint3 = new THREE.Group();
    joint3.position.y = ARM_LENGTHS.elbow;
    joint2.add(joint3);
    joint3.add(wristMesh);

    // Joint 4: Wrist roll
    const joint4 = new THREE.Group();
    joint4.position.y = ARM_LENGTHS.wrist;
    joint3.add(joint4);

    const joint4Sphere = new THREE.Mesh(
        new THREE.SphereGeometry(0.12, 16, 16),
        jointMat
    );
    joint4.add(joint4Sphere);

    // Gripper
    const gripperBase = new THREE.Mesh(
        new THREE.BoxGeometry(0.2, 0.1, 0.15),
        gripperMat
    );
    gripperBase.position.y = 0.05;
    joint4.add(gripperBase);

    const leftFinger = new THREE.Mesh(
        new THREE.BoxGeometry(0.04, ARM_LENGTHS.gripper, 0.08),
        gripperMat
    );
    leftFinger.position.set(-0.1, ARM_LENGTHS.gripper / 2 + 0.1, 0);
    joint4.add(leftFinger);

    const rightFinger = new THREE.Mesh(
        new THREE.BoxGeometry(0.04, ARM_LENGTHS.gripper, 0.08),
        gripperMat
    );
    rightFinger.position.set(0.1, ARM_LENGTHS.gripper / 2 + 0.1, 0);
    joint4.add(rightFinger);

    // ── State ──
    const joints = [joint0, joint1, joint2, joint3, joint4];
    const jointSpheres = [joint0Sphere, joint1Sphere, joint2Sphere, joint4Sphere];

    // Target angles (degrees, from backend) and current smoothed angles
    let targetAngles = [90, 90, 90, 90, 90];
    let currentAngles = [90, 90, 90, 90, 90];
    let gripperClosed = false;
    let lastUpdateTime = 0;
    let isReceivingData = false;

    // Status indicator
    const statusGeo = new THREE.SphereGeometry(0.15, 16, 16);
    const statusMesh = new THREE.Mesh(statusGeo, activeMat.clone());
    statusMesh.position.set(1.2, 0.15, 1.2);
    scene.add(statusMesh);

    // ── Public API ──
    function setArmAngles(angles, gripper = false) {
        if (angles && angles.length >= 5) {
            targetAngles = angles.slice(0, 5);
        }
        gripperClosed = gripper;
        lastUpdateTime = performance.now();
        isReceivingData = true;
    }

    function degToRad(deg) {
        return (deg * Math.PI) / 180;
    }

    // Smooth interpolation factor
    const SMOOTHING = 0.15;

    const update = (delta, elapsed) => {
        // Smooth approach to target
        for (let i = 0; i < 5; i++) {
            currentAngles[i] += (targetAngles[i] - currentAngles[i]) * SMOOTHING;
        }

        // Apply joint rotations
        // Joint 0: base yaw — rotate around Y axis
        joint0.rotation.y = degToRad(currentAngles[0] - 90);

        // Joint 1: shoulder pitch — rotate around Z axis
        joint1.rotation.z = degToRad(currentAngles[1] - 90);

        // Joint 2: elbow pitch
        joint2.rotation.z = degToRad(currentAngles[2] - 90);

        // Joint 3: wrist pitch
        joint3.rotation.z = degToRad(currentAngles[3] - 90);

        // Joint 4: wrist roll
        joint4.rotation.y = degToRad(currentAngles[4] - 90);

        // Gripper animation
        const gripTarget = gripperClosed ? 0.04 : 0.1;
        const currentGripX = leftFinger.position.x;
        const newGripX = currentGripX + ((-gripTarget) - currentGripX) * SMOOTHING;
        leftFinger.position.x = newGripX;
        rightFinger.position.x = -newGripX;

        // Status indicator
        const now = performance.now();
        const timeSinceUpdate = now - lastUpdateTime;

        if (isReceivingData && timeSinceUpdate < 2000) {
            // Pulse green when receiving data
            const pulse = 0.4 + Math.sin(elapsed * 4) * 0.2;
            statusMesh.material.emissiveIntensity = pulse;
            statusMesh.material.color.setHex(0x22c55e);
            statusMesh.material.emissive.setHex(0x0a4a1a);
        } else {
            // Dim amber when idle
            isReceivingData = false;
            statusMesh.material.color.setHex(0xf59e0b);
            statusMesh.material.emissive.setHex(0x4a3a0a);
            statusMesh.material.emissiveIntensity = 0.2;
        }

        // Subtle joint glow pulse
        jointSpheres.forEach((sphere, i) => {
            const intensity = 0.2 + Math.sin(elapsed * 2 + i * 0.8) * 0.1;
            sphere.material.emissiveIntensity = intensity;
        });
    };

    return {
        scene,
        update,
        setArmAngles,
        defaultDistance: 8,
        minDistance: 3,
        maxDistance: 20,
    };
}

export const metadata = {
    name: 'Robotic Arm',
    category: 'Robotics',
    description: 'Live 5-DOF robotic arm visualization — puppet mode',
    interactive: false,
};

export default (THREE) => createRoboticArmScene(THREE);
