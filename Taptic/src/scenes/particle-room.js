export function createParticleRoom(THREE) {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a15);

    scene.add(new THREE.AmbientLight(0x404060, 0.4));
    const pointLight = new THREE.PointLight(0x6366f1, 1, 30);
    pointLight.position.set(0, 5, 0);
    scene.add(pointLight);

    const roomSize = 10;
    const wallMat = new THREE.MeshStandardMaterial({
        color: 0x1e1e2e,
        transparent: true,
        opacity: 0.3,
        side: THREE.BackSide
    });
    const room = new THREE.Mesh(
        new THREE.BoxGeometry(roomSize, roomSize, roomSize),
        wallMat
    );
    scene.add(room);

    const gridHelper = new THREE.GridHelper(roomSize, 20, 0x333355, 0x222244);
    gridHelper.position.y = -roomSize / 2;
    scene.add(gridHelper);

    const particles = [];
    const particleCount = 40;
    const colors = [0xff6b6b, 0x4ecdc4, 0x45b7d1, 0x96ceb4, 0xffeaa7, 0xdfe6e9, 0xa29bfe, 0xfd79a8];

    for (let i = 0; i < particleCount; i++) {
        const radius = 0.15 + Math.random() * 0.25;
        const geo = new THREE.SphereGeometry(radius, 16, 16);
        const mat = new THREE.MeshStandardMaterial({
            color: colors[Math.floor(Math.random() * colors.length)],
            emissive: colors[Math.floor(Math.random() * colors.length)],
            emissiveIntensity: 0.3,
            metalness: 0.5,
            roughness: 0.3
        });
        const particle = new THREE.Mesh(geo, mat);

        const bound = roomSize / 2 - radius - 0.5;
        particle.position.set(
            (Math.random() - 0.5) * bound * 2,
            (Math.random() - 0.5) * bound * 2,
            (Math.random() - 0.5) * bound * 2
        );

        particle.userData = {
            velocity: new THREE.Vector3(
                (Math.random() - 0.5) * 0.06,
                (Math.random() - 0.5) * 0.06,
                (Math.random() - 0.5) * 0.06
            ),
            radius,
            grabbed: false,
            mass: radius * radius * radius
        };

        particles.push(particle);
        scene.add(particle);
    }

    const grabIndicator = new THREE.Mesh(
        new THREE.SphereGeometry(0.5, 16, 16),
        new THREE.MeshBasicMaterial({
            color: 0x3b82f6,
            transparent: true,
            opacity: 0.3,
            wireframe: true
        })
    );
    grabIndicator.visible = false;
    scene.add(grabIndicator);

    let grabbedParticle = null;
    let lastGrabPos = new THREE.Vector3();
    const raycaster = new THREE.Raycaster();

    const update = (delta, elapsed, cursorData, camera) => {
        if (cursorData && camera && cursorData.visible) {
            const ndc = new THREE.Vector2(
                (cursorData.x / window.innerWidth) * 2 - 1,
                -(cursorData.y / window.innerHeight) * 2 + 1
            );

            raycaster.setFromCamera(ndc, camera);

            if (cursorData.clicking) {
                if (!grabbedParticle) {
                    const intersects = raycaster.intersectObjects(particles);
                    if (intersects.length > 0) {
                        grabbedParticle = intersects[0].object;
                        grabbedParticle.userData.grabbed = true;
                        grabbedParticle.material.emissiveIntensity = 0.8;
                        lastGrabPos.copy(grabbedParticle.position);
                    }
                }

                if (grabbedParticle) {
                    const planeNormal = new THREE.Vector3(0, 0, 1).applyQuaternion(camera.quaternion);
                    const plane = new THREE.Plane(planeNormal, -grabbedParticle.position.dot(planeNormal));
                    const targetPoint = new THREE.Vector3();
                    raycaster.ray.intersectPlane(plane, targetPoint);

                    if (targetPoint) {
                        const newPos = targetPoint.clone();
                        const bound = roomSize / 2 - grabbedParticle.userData.radius;
                        newPos.clamp(
                            new THREE.Vector3(-bound, -bound, -bound),
                            new THREE.Vector3(bound, bound, bound)
                        );

                        grabbedParticle.userData.velocity.copy(newPos).sub(grabbedParticle.position).multiplyScalar(0.5);
                        grabbedParticle.position.lerp(newPos, 0.3);
                        lastGrabPos.copy(grabbedParticle.position);
                    }

                    grabIndicator.visible = true;
                    grabIndicator.position.copy(grabbedParticle.position);
                    grabIndicator.scale.setScalar(grabbedParticle.userData.radius * 3);
                }
            } else {
                if (grabbedParticle) {
                    grabbedParticle.userData.grabbed = false;
                    grabbedParticle.material.emissiveIntensity = 0.3;
                    grabbedParticle = null;
                }
                grabIndicator.visible = false;
            }
        }

        particles.forEach(p => {
            if (p.userData.grabbed) return;

            p.position.add(p.userData.velocity);

            const bound = roomSize / 2 - p.userData.radius;
            ['x', 'y', 'z'].forEach(axis => {
                if (Math.abs(p.position[axis]) > bound) {
                    p.position[axis] = Math.sign(p.position[axis]) * bound;
                    p.userData.velocity[axis] *= -0.95;
                }
            });

            p.userData.velocity.multiplyScalar(0.998);
        });

        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const a = particles[i];
                const b = particles[j];
                const dist = a.position.distanceTo(b.position);
                const minDist = a.userData.radius + b.userData.radius;

                if (dist < minDist && dist > 0) {
                    const normal = new THREE.Vector3().subVectors(b.position, a.position).normalize();
                    const relVel = new THREE.Vector3().subVectors(a.userData.velocity, b.userData.velocity);
                    const velAlongNormal = relVel.dot(normal);

                    if (velAlongNormal > 0) continue;

                    const totalMass = a.userData.mass + b.userData.mass;
                    const impulse = normal.clone().multiplyScalar(-velAlongNormal * 1.8);

                    if (!a.userData.grabbed) {
                        a.userData.velocity.add(impulse.clone().multiplyScalar(b.userData.mass / totalMass));
                    }
                    if (!b.userData.grabbed) {
                        b.userData.velocity.sub(impulse.clone().multiplyScalar(a.userData.mass / totalMass));
                    }

                    const overlap = minDist - dist;
                    const correction = normal.clone().multiplyScalar(overlap / 2);
                    if (!a.userData.grabbed) a.position.sub(correction);
                    if (!b.userData.grabbed) b.position.add(correction);
                }
            }
        }

        pointLight.intensity = 1 + Math.sin(elapsed * 2) * 0.2;
    };

    return {
        scene,
        update,
        defaultDistance: 15,
        minDistance: 8,
        maxDistance: 25,
        isInteractive: true
    };
}
