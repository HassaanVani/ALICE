import React, { useRef, useEffect } from 'react';
import * as THREE from 'three';

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
};

// --- Brain shape signed distance function ---
// Returns < 0 inside the brain volume
function brainSDF(px, py, pz) {
  // Ellipsoid base: wide (x), shorter (y), medium depth (z front-back)
  const ex = px / 4.2;
  const ey = py / 3.2;
  const ez = pz / 3.6;
  let d = ex * ex + ey * ey + ez * ez - 1;

  // Medial fissure — groove along the top midline (x≈0, y>0)
  if (py > 0) {
    d += 0.55 * Math.exp(-px * px * 1.8) * Math.pow(Math.max(0, py / 3.2), 0.8);
  }

  // Frontal lobe bulge (+z)
  d -= 0.12 * Math.exp(-((ez - 0.7) ** 2) * 5);

  // Occipital taper (-z)
  if (pz < -2) {
    d += 0.08 * Math.pow((-pz - 2) / 1.6, 2);
  }

  // Temporal lobe bumps (lower sides)
  const tx = Math.abs(px) / 4.2;
  d -= 0.08 * Math.exp(-((tx - 0.75) ** 2) * 12 - ((ey + 0.35) ** 2) * 8);

  return d;
}

// Pre-compute neuron positions inside the brain volume
function generateNeuronPositions() {
  const RES = 14;
  const positions = [];
  const rangeX = 9.8, rangeY = 7.8, rangeZ = 8.8;

  for (let xi = 0; xi < RES; xi++) {
    for (let yi = 0; yi < RES; yi++) {
      for (let zi = 0; zi < RES; zi++) {
        const x = (xi / (RES - 1) - 0.5) * rangeX;
        const y = (yi / (RES - 1) - 0.5) * rangeY;
        const z = (zi / (RES - 1) - 0.5) * rangeZ;

        if (brainSDF(x, y, z) < -0.05) {
          // Deterministic organic jitter
          const jx = x + Math.sin(xi * 7.1 + yi * 13.3) * 0.13;
          const jy = y + Math.sin(yi * 11.7 + zi * 7.9) * 0.13;
          const jz = z + Math.sin(zi * 5.3 + xi * 11.1) * 0.13;
          positions.push([jx, jy, jz]);
        }
      }
    }
  }

  // Sort front-to-back (z descending) — frontal → occipital maps to early → late layers
  positions.sort((a, b) => b[2] - a[2]);
  return positions;
}

const NEURON_POSITIONS = generateNeuronPositions();
const NEURON_COUNT = NEURON_POSITIONS.length;

// Layer color gradient (front→back): cyan → blue → violet → purple → green → orange
const LAYER_COLORS = [
  new THREE.Color(0x06b6d4),
  new THREE.Color(0x3b82f6),
  new THREE.Color(0x8b5cf6),
  new THREE.Color(0xa855f7),
  new THREE.Color(0x22c55e),
  new THREE.Color(0xf97316),
];

// Deform icosahedron vertices into a brain shape
function deformShellToBrain(geometry) {
  const pos = geometry.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i);
    const y = pos.getY(i);
    const z = pos.getZ(i);

    const len = Math.sqrt(x * x + y * y + z * z) || 1;
    const nx = x / len;
    const ny = y / len;
    const nz = z / len;

    // Ellipsoid scaling
    let sx = nx * 4.8;
    let sy = ny * 3.6;
    let sz = nz * 4.1;

    // Medial fissure indent
    if (sy > 0.3) {
      const indent = 0.7 * Math.exp(-sx * sx * 0.12) * Math.pow(Math.max(0, (sy - 0.3) / 3.3), 0.6);
      sy -= indent;
    }

    // Frontal bulge
    if (nz > 0.2) {
      sz += 0.25 * Math.exp(-((nz - 0.7) ** 2) * 3);
    }

    // Occipital taper
    if (nz < -0.5) {
      const taper = 0.15 * Math.pow((-nz - 0.5) / 0.5, 2);
      sx *= 1 - taper * 0.3;
      sy *= 1 - taper * 0.2;
    }

    // Temporal lobe bumps
    const absnx = Math.abs(nx);
    if (absnx > 0.4 && ny < -0.1) {
      const bump = 0.2 * Math.exp(-((absnx - 0.7) ** 2) * 8 - ((ny + 0.3) ** 2) * 6);
      sx += bump * Math.sign(nx);
    }

    pos.setXYZ(i, sx, sy, sz);
  }
  pos.needsUpdate = true;
  geometry.computeVertexNormals();
}

// Interpolate between layer colors by depth fraction (0 = front, 1 = back)
function getLayerColor(fraction, target) {
  const idx = fraction * (LAYER_COLORS.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.min(lo + 1, LAYER_COLORS.length - 1);
  target.copy(LAYER_COLORS[lo]).lerp(LAYER_COLORS[hi], idx - lo);
}

export default function BrainViewport({ activations }) {
  const containerRef = useRef(null);
  const rendererRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const neuronsRef = useRef(null);
  const glassRef = useRef(null);
  const rafRef = useRef(null);
  const timeRef = useRef(0);
  const [showWaiting, setShowWaiting] = React.useState(true);

  // Initialize Three.js scene
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Scene
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x09090b, 0.04);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
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

    // Glass brain shell — deformed icosahedron
    const shellGeometry = new THREE.IcosahedronGeometry(1, 4);
    deformShellToBrain(shellGeometry);
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

    // Neuron instances — small spheres packed inside the brain volume
    const neuronGeometry = new THREE.SphereGeometry(0.16, 6, 6);
    const neuronMaterial = new THREE.MeshStandardMaterial({
      color: 0x3b82f6,
      transparent: true,
      opacity: 0.7,
      emissive: 0x3b82f6,
      emissiveIntensity: 0.4,
    });
    const neurons = new THREE.InstancedMesh(neuronGeometry, neuronMaterial, NEURON_COUNT);
    neurons.instanceMatrix.setUsage(THREE.DynamicDrawUsage);

    // Place neurons at brain positions with depth-based layer coloring
    const dummy = new THREE.Object3D();
    const color = new THREE.Color();
    for (let i = 0; i < NEURON_COUNT; i++) {
      const [px, py, pz] = NEURON_POSITIONS[i];
      dummy.position.set(px, py, pz);
      dummy.scale.set(0.4, 0.4, 0.4);
      dummy.updateMatrix();
      neurons.setMatrixAt(i, dummy.matrix);

      // Color gradient by depth position
      getLayerColor(i / NEURON_COUNT, color);
      color.multiplyScalar(0.35); // dim when idle
      neurons.setColorAt(i, color);
    }
    neurons.instanceMatrix.needsUpdate = true;
    if (neurons.instanceColor) neurons.instanceColor.needsUpdate = true;
    scene.add(neurons);
    neuronsRef.current = neurons;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0x404060, 0.5);
    scene.add(ambientLight);

    const pointLight1 = new THREE.PointLight(0x3b82f6, 2, 30);
    pointLight1.position.set(8, 8, 8);
    scene.add(pointLight1);

    const pointLight2 = new THREE.PointLight(0x22c55e, 1, 20);
    pointLight2.position.set(-6, -4, 6);
    scene.add(pointLight2);

    const pointLight3 = new THREE.PointLight(0xa855f7, 0.8, 18);
    pointLight3.position.set(0, 8, -6);
    scene.add(pointLight3);

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

      // Orbit camera around the brain
      camera.position.x = 10 * Math.cos(t * 0.25);
      camera.position.z = 10 * Math.sin(t * 0.25);
      camera.position.y = 4 + Math.sin(t * 0.12) * 2.5;
      camera.lookAt(0, 0, 0);

      // Slowly rotate glass shell
      if (glassRef.current) {
        glassRef.current.rotation.y = t * 0.08;
        glassRef.current.rotation.x = Math.sin(t * 0.06) * 0.08;
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

  // Hide waiting label on first activation data
  useEffect(() => {
    if (activations && activations.length > 0 && showWaiting) {
      setShowWaiting(false);
    }
  }, [activations, showWaiting]);

  // Update neuron activations when data changes
  useEffect(() => {
    if (!neuronsRef.current || !activations || activations.length === 0) return;

    const neurons = neuronsRef.current;
    const dummy = new THREE.Object3D();
    const color = new THREE.Color();

    // Flatten all activation values
    const allValues = activations.flatMap((l) => l.values);
    const maxVal = Math.max(...allValues.map(Math.abs), 0.001);

    // Map activation layers to neuron depth zones
    const neuronsPerLayer = Math.ceil(NEURON_COUNT / activations.length);

    for (let i = 0; i < NEURON_COUNT; i++) {
      const [px, py, pz] = NEURON_POSITIONS[i];

      // Which activation layer does this neuron belong to
      const layerIdx = Math.min(activations.length - 1, Math.floor(i / neuronsPerLayer));
      const withinLayer = i - layerIdx * neuronsPerLayer;
      const layer = activations[layerIdx];
      const valIdx = withinLayer % layer.values.length;
      const val = layer.values[valIdx];
      const norm = Math.abs(val) / maxVal;

      // Scale by activation magnitude
      dummy.position.set(px, py, pz);
      const scale = 0.15 + norm * 0.85;
      dummy.scale.set(scale, scale, scale);
      dummy.updateMatrix();
      neurons.setMatrixAt(i, dummy.matrix);

      // Depth-based color modulated by activation
      getLayerColor(i / NEURON_COUNT, color);

      if (val < 0) {
        // Negative activations shift warm/red
        color.lerp(new THREE.Color(0.9, 0.1, 0.2), norm * 0.4);
      } else {
        // Positive activations brighten toward white
        color.lerp(new THREE.Color(1, 1, 1), norm * 0.25);
      }

      // Dim inactive neurons
      color.multiplyScalar(0.2 + norm * 0.8);
      neurons.setColorAt(i, color);
    }

    neurons.instanceMatrix.needsUpdate = true;
    if (neurons.instanceColor) neurons.instanceColor.needsUpdate = true;
  }, [activations]);

  return (
    <div ref={containerRef} style={styles.container}>
      {showWaiting && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          fontSize: 11,
          color: '#52525b',
          fontFamily: 'var(--font-mono)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          pointerEvents: 'none',
          zIndex: 2,
        }}>
          Waiting for tensor data...
        </div>
      )}
      <div style={styles.label}>
        GLASS BRAIN | {NEURON_COUNT} neurons | {activations?.length || 0} layers
      </div>
    </div>
  );
}
