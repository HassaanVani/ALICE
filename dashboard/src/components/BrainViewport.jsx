import React, { useRef, useEffect, useMemo } from 'react';
import * as THREE from 'three';

const styles = {
  container: {
    width: '100%',
    height: '100%',
    position: 'relative',
    background: '#09090b',
  },
  canvas: {
    width: '100%',
    height: '100%',
    display: 'block',
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
};

const VOXEL_GRID = 8; // 8x8x8 voxel grid
const VOXEL_COUNT = VOXEL_GRID ** 3;

export default function BrainViewport({ activations }) {
  const containerRef = useRef(null);
  const rendererRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const voxelsRef = useRef(null);
  const glassRef = useRef(null);
  const rafRef = useRef(null);
  const timeRef = useRef(0);

  // Initialize Three.js scene
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Scene
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x09090b, 0.06);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 100);
    camera.position.set(8, 6, 10);
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x09090b, 1);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Glass brain shell
    const shellGeometry = new THREE.IcosahedronGeometry(5.5, 3);
    const shellMaterial = new THREE.MeshPhysicalMaterial({
      color: 0x3b82f6,
      transparent: true,
      opacity: 0.04,
      roughness: 0.1,
      metalness: 0.0,
      transmission: 0.95,
      thickness: 0.5,
      wireframe: true,
      side: THREE.DoubleSide,
    });
    const shell = new THREE.Mesh(shellGeometry, shellMaterial);
    scene.add(shell);
    glassRef.current = shell;

    // Voxel grid as instanced mesh
    const voxelGeometry = new THREE.BoxGeometry(0.35, 0.35, 0.35);
    const voxelMaterial = new THREE.MeshStandardMaterial({
      color: 0x3b82f6,
      transparent: true,
      opacity: 0.6,
      emissive: 0x3b82f6,
      emissiveIntensity: 0.3,
    });
    const voxels = new THREE.InstancedMesh(voxelGeometry, voxelMaterial, VOXEL_COUNT);
    voxels.instanceMatrix.setUsage(THREE.DynamicDrawUsage);

    // Position voxels in grid
    const dummy = new THREE.Object3D();
    const offset = (VOXEL_GRID - 1) / 2;
    for (let x = 0; x < VOXEL_GRID; x++) {
      for (let y = 0; y < VOXEL_GRID; y++) {
        for (let z = 0; z < VOXEL_GRID; z++) {
          const idx = x * VOXEL_GRID * VOXEL_GRID + y * VOXEL_GRID + z;
          dummy.position.set(
            (x - offset) * 0.9,
            (y - offset) * 0.9,
            (z - offset) * 0.9
          );
          dummy.scale.set(0.3, 0.3, 0.3);
          dummy.updateMatrix();
          voxels.setMatrixAt(idx, dummy.matrix);
        }
      }
    }
    voxels.instanceMatrix.needsUpdate = true;
    scene.add(voxels);
    voxelsRef.current = voxels;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0x404060, 0.5);
    scene.add(ambientLight);

    const pointLight1 = new THREE.PointLight(0x3b82f6, 2, 30);
    pointLight1.position.set(8, 8, 8);
    scene.add(pointLight1);

    const pointLight2 = new THREE.PointLight(0x22c55e, 1, 20);
    pointLight2.position.set(-6, -4, 6);
    scene.add(pointLight2);

    // Axis helper (subtle)
    const axisLen = 6;
    const axisMat = (color) => new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.15 });
    const xLine = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(axisLen, 0, 0)]),
      axisMat(0xef4444)
    );
    const yLine = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, axisLen, 0)]),
      axisMat(0x22c55e)
    );
    const zLine = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, axisLen)]),
      axisMat(0x3b82f6)
    );
    scene.add(xLine, yLine, zLine);

    // Handle resize
    const handleResize = () => {
      const rect = container.getBoundingClientRect();
      renderer.setSize(rect.width, rect.height);
      camera.aspect = rect.width / rect.height;
      camera.updateProjectionMatrix();
    };
    handleResize();
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    // Animation loop
    const animate = () => {
      timeRef.current += 0.01;
      const t = timeRef.current;

      // Rotate camera orbit
      camera.position.x = 10 * Math.cos(t * 0.3);
      camera.position.z = 10 * Math.sin(t * 0.3);
      camera.position.y = 5 + Math.sin(t * 0.15) * 2;
      camera.lookAt(0, 0, 0);

      // Rotate glass shell
      if (glassRef.current) {
        glassRef.current.rotation.y = t * 0.1;
        glassRef.current.rotation.x = Math.sin(t * 0.08) * 0.1;
      }

      renderer.render(scene, camera);
      rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      resizeObserver.disconnect();
      renderer.dispose();
      container.removeChild(renderer.domElement);
    };
  }, []);

  // Update voxel activations when data changes
  useEffect(() => {
    if (!voxelsRef.current || !activations || activations.length === 0) return;

    const voxels = voxelsRef.current;
    const dummy = new THREE.Object3D();
    const offset = (VOXEL_GRID - 1) / 2;
    const color = new THREE.Color();

    // Flatten all activation values to map to voxels
    const allValues = activations.flatMap((l) => l.values);
    const maxVal = Math.max(...allValues.map(Math.abs), 0.001);

    for (let x = 0; x < VOXEL_GRID; x++) {
      for (let y = 0; y < VOXEL_GRID; y++) {
        for (let z = 0; z < VOXEL_GRID; z++) {
          const idx = x * VOXEL_GRID * VOXEL_GRID + y * VOXEL_GRID + z;
          const val = idx < allValues.length ? allValues[idx] : 0;
          const norm = Math.abs(val) / maxVal;

          dummy.position.set(
            (x - offset) * 0.9,
            (y - offset) * 0.9,
            (z - offset) * 0.9
          );

          const scale = 0.15 + norm * 0.85;
          dummy.scale.set(scale, scale, scale);
          dummy.updateMatrix();
          voxels.setMatrixAt(idx, dummy.matrix);

          // Color based on activation sign/magnitude
          if (val >= 0) {
            color.setRGB(0.1 + norm * 0.13, 0.3 + norm * 0.7, 0.9 - norm * 0.3);
          } else {
            color.setRGB(0.9 * norm, 0.15, 0.3 + norm * 0.3);
          }
          voxels.setColorAt(idx, color);
        }
      }
    }

    voxels.instanceMatrix.needsUpdate = true;
    if (voxels.instanceColor) voxels.instanceColor.needsUpdate = true;
  }, [activations]);

  return (
    <div ref={containerRef} style={styles.container}>
      <div style={styles.label}>
        GLASS BRAIN | {VOXEL_GRID}x{VOXEL_GRID}x{VOXEL_GRID} voxels
      </div>
    </div>
  );
}
