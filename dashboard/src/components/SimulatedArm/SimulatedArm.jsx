import React, { useRef, useEffect } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { computeJointPositions } from './forwardKinematics';
import {
  DEFAULT_ANGLES, SCALE, COLORS, ARM_DIMS,
  LINK_RADIUS, JOINT_RADIUS, BASE_RADIUS, BASE_PLATFORM_HEIGHT,
  GRIPPER_LENGTH, GRIPPER_WIDTH, GRIPPER_SPREAD_OPEN, GRIPPER_SPREAD_CLOSED,
} from './armConstants';

const styles = {
  container: {
    width: '100%',
    height: '100%',
    position: 'relative',
    background: '#09090b',
  },
  label: {
    position: 'absolute',
    bottom: 8,
    left: 8,
    fontSize: 10,
    color: '#52525b',
    fontFamily: 'var(--font-mono)',
    pointerEvents: 'none',
  },
  hud: {
    position: 'absolute',
    top: 8,
    right: 8,
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    pointerEvents: 'none',
  },
  hudLine: {
    fontSize: 10,
    fontFamily: 'var(--font-mono)',
    color: '#a1a1aa',
  },
};

const JOINT_LABELS = ['BASE', 'SHLD', 'ELBW', 'WRPT', 'WRRL'];

function lerpAngle(current, target, alpha) {
  return current + (target - current) * alpha;
}

export default function SimulatedArm({ angles = DEFAULT_ANGLES, gripperOpen = true }) {
  const containerRef = useRef(null);
  const rendererRef = useRef(null);
  const controlsRef = useRef(null);
  const rafRef = useRef(null);

  // Arm mesh refs — populated once in setup
  const armPartsRef = useRef(null);

  // Animation state
  const currentAnglesRef = useRef([...DEFAULT_ANGLES]);
  const targetAnglesRef = useRef([...DEFAULT_ANGLES]);
  const gripperOpenRef = useRef(true);

  // ── Setup Three.js scene (runs once) ──
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x09090b, 0.025);

    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
    camera.position.set(6, 5, 8);
    camera.lookAt(0, 2, 0);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x09090b, 1);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // OrbitControls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 1.5, 0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 3;
    controls.maxDistance = 20;
    controls.update();
    controlsRef.current = controls;

    // ── Environment ──

    // Ground
    const groundGeom = new THREE.PlaneGeometry(20, 20);
    const groundMat = new THREE.MeshStandardMaterial({ color: COLORS.ground, roughness: 0.9 });
    const ground = new THREE.Mesh(groundGeom, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    // Grid
    const grid = new THREE.GridHelper(20, 40, COLORS.grid, COLORS.grid);
    grid.material.opacity = 0.3;
    grid.material.transparent = true;
    grid.position.y = 0.001;
    scene.add(grid);

    // Reach circle
    const maxReach = (ARM_DIMS.shoulderLength + ARM_DIMS.elbowLength + ARM_DIMS.wristLength) * SCALE;
    const reachGeom = new THREE.RingGeometry(maxReach - 0.05, maxReach, 64);
    const reachMat = new THREE.MeshBasicMaterial({
      color: COLORS.reachCircle, transparent: true, opacity: 0.1, side: THREE.DoubleSide,
    });
    const reach = new THREE.Mesh(reachGeom, reachMat);
    reach.rotation.x = -Math.PI / 2;
    reach.position.y = 0.002;
    scene.add(reach);

    // ── Arm Meshes ──

    const linkGeom = new THREE.CylinderGeometry(1, 1, 1, 8);
    const jointGeom = new THREE.SphereGeometry(1, 12, 8);

    // Base platform
    const basePlatGeom = new THREE.CylinderGeometry(BASE_RADIUS, BASE_RADIUS * 1.1, BASE_PLATFORM_HEIGHT, 16);
    const basePlat = new THREE.Mesh(basePlatGeom, new THREE.MeshStandardMaterial({
      color: COLORS.base, roughness: 0.6, metalness: 0.3,
    }));
    basePlat.position.y = BASE_PLATFORM_HEIGHT / 2;
    basePlat.castShadow = true;
    scene.add(basePlat);

    // Base column
    const baseCol = new THREE.Mesh(linkGeom.clone(), new THREE.MeshStandardMaterial({
      color: COLORS.baseTop, roughness: 0.5, metalness: 0.2,
    }));
    baseCol.castShadow = true;
    scene.add(baseCol);

    // Arm links
    const linkColors = [COLORS.upperArm, COLORS.forearm, COLORS.hand];
    const links = linkColors.map((color) => {
      const mesh = new THREE.Mesh(linkGeom.clone(), new THREE.MeshStandardMaterial({
        color, roughness: 0.4, metalness: 0.3, emissive: color, emissiveIntensity: 0.05,
      }));
      mesh.castShadow = true;
      scene.add(mesh);
      return mesh;
    });

    // Joint spheres (shoulder, elbow, wrist, EE)
    const joints = Array.from({ length: 4 }, () => {
      const mesh = new THREE.Mesh(jointGeom.clone(), new THREE.MeshStandardMaterial({
        color: COLORS.joint, roughness: 0.3, metalness: 0.4,
        emissive: COLORS.jointEmissive, emissiveIntensity: 0.1,
      }));
      mesh.castShadow = true;
      scene.add(mesh);
      return mesh;
    });

    // Gripper
    const gripperGroup = new THREE.Group();
    const fingerGeom = new THREE.BoxGeometry(GRIPPER_WIDTH, GRIPPER_LENGTH, GRIPPER_WIDTH);
    const makeFinger = () => new THREE.Mesh(fingerGeom, new THREE.MeshStandardMaterial({
      color: COLORS.gripperOpen, roughness: 0.3, metalness: 0.2,
      emissive: COLORS.gripperOpen, emissiveIntensity: 0.15,
    }));
    const leftFinger = makeFinger();
    const rightFinger = makeFinger();
    gripperGroup.add(leftFinger, rightFinger);
    scene.add(gripperGroup);

    armPartsRef.current = { baseCol, links, joints, gripperGroup, leftFinger, rightFinger };

    // ── Lighting ──

    scene.add(new THREE.AmbientLight(0x404060, 0.6));

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
    dirLight.position.set(5, 10, 5);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.set(1024, 1024);
    dirLight.shadow.camera.near = 0.5;
    dirLight.shadow.camera.far = 30;
    dirLight.shadow.camera.left = -10;
    dirLight.shadow.camera.right = 10;
    dirLight.shadow.camera.top = 10;
    dirLight.shadow.camera.bottom = -10;
    scene.add(dirLight);

    const pointLight = new THREE.PointLight(0x3b82f6, 0.5, 15);
    pointLight.position.set(-3, 5, 3);
    scene.add(pointLight);

    // ── Helpers ──

    const upVec = new THREE.Vector3(0, 1, 0);
    const tmpA = new THREE.Vector3();
    const tmpB = new THREE.Vector3();

    function positionCylinder(mesh, p1, p2, radius) {
      tmpA.set(p1.x, p1.y, p1.z);
      tmpB.set(p2.x, p2.y, p2.z);
      mesh.position.copy(tmpA).add(tmpB).multiplyScalar(0.5);
      const dir = tmpB.clone().sub(tmpA);
      const len = dir.length();
      mesh.scale.set(radius, Math.max(len, 0.001), radius);
      if (len > 0.001) {
        mesh.quaternion.setFromUnitVectors(upVec, dir.normalize());
      }
    }

    function updateArmVisuals() {
      const parts = armPartsRef.current;
      if (!parts) return;

      const pos = computeJointPositions(currentAnglesRef.current);
      const isOpen = gripperOpenRef.current;

      // Base column
      positionCylinder(parts.baseCol, pos.base, pos.shoulder, LINK_RADIUS * 1.5);

      // Arm links
      positionCylinder(parts.links[0], pos.shoulder, pos.elbow, LINK_RADIUS);
      positionCylinder(parts.links[1], pos.elbow, pos.wrist, LINK_RADIUS * 0.85);
      positionCylinder(parts.links[2], pos.wrist, pos.endEffector, LINK_RADIUS * 0.7);

      // Joints
      const jp = [pos.shoulder, pos.elbow, pos.wrist, pos.endEffector];
      const js = [JOINT_RADIUS, JOINT_RADIUS * 0.9, JOINT_RADIUS * 0.8, JOINT_RADIUS * 0.7];
      jp.forEach((p, i) => {
        parts.joints[i].position.set(p.x, p.y, p.z);
        parts.joints[i].scale.setScalar(js[i]);
      });

      // Gripper position and orientation
      const ee = pos.endEffector;
      const w = pos.wrist;
      parts.gripperGroup.position.set(ee.x, ee.y, ee.z);

      tmpA.set(ee.x - w.x, ee.y - w.y, ee.z - w.z);
      if (tmpA.length() > 0.001) {
        tmpA.normalize();
        parts.gripperGroup.quaternion.setFromUnitVectors(upVec, tmpA);
        const rollQuat = new THREE.Quaternion().setFromAxisAngle(tmpA, pos.wristRoll);
        parts.gripperGroup.quaternion.premultiply(rollQuat);
      }

      // Finger spread
      const spread = isOpen ? GRIPPER_SPREAD_OPEN : GRIPPER_SPREAD_CLOSED;
      parts.leftFinger.position.set(-spread, GRIPPER_LENGTH / 2, 0);
      parts.rightFinger.position.set(spread, GRIPPER_LENGTH / 2, 0);

      // Finger color
      const gc = isOpen ? COLORS.gripperOpen : COLORS.gripperClosed;
      [parts.leftFinger, parts.rightFinger].forEach((f) => {
        f.material.color.setHex(gc);
        f.material.emissive.setHex(gc);
      });
    }

    // ── Resize ──

    const handleResize = () => {
      const rect = container.getBoundingClientRect();
      renderer.setSize(rect.width, rect.height);
      camera.aspect = rect.width / rect.height;
      camera.updateProjectionMatrix();
    };
    handleResize();
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    // ── Animation Loop ──

    const animate = () => {
      const cur = currentAnglesRef.current;
      const tgt = targetAnglesRef.current;
      for (let i = 0; i < 5; i++) {
        cur[i] = lerpAngle(cur[i], tgt[i], 0.1);
      }
      updateArmVisuals();
      controls.update();
      renderer.render(scene, camera);
      rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      resizeObserver.disconnect();
      controls.dispose();
      renderer.dispose();
      container.removeChild(renderer.domElement);
    };
  }, []);

  // ── Sync props to animation refs ──
  useEffect(() => {
    if (angles && angles.length >= 5) {
      targetAnglesRef.current = [...angles];
    }
    gripperOpenRef.current = gripperOpen;
  }, [angles, gripperOpen]);

  return (
    <div ref={containerRef} style={styles.container}>
      <div style={styles.hud}>
        {(angles || DEFAULT_ANGLES).map((a, i) => (
          <span key={i} style={styles.hudLine}>
            {JOINT_LABELS[i]}: {(a || 0).toFixed(1)}
          </span>
        ))}
        <span style={{ ...styles.hudLine, color: gripperOpen ? '#22c55e' : '#eab308' }}>
          {gripperOpen ? 'GRIP OPEN' : 'GRIP CLOSED'}
        </span>
      </div>
      <div style={styles.label}>
        SIMULATED ARM | 5-axis FK
      </div>
    </div>
  );
}
