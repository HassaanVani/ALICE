import React, { useRef, useEffect, useState, useMemo } from 'react';
import * as THREE from 'three';

// Workspace dimensions (cm mapped to Three.js units)
const WORKSPACE_WIDTH = 60;
const WORKSPACE_DEPTH = 40;
const GRID_RES_X = 54;
const GRID_RES_Z = 38;
const TOTAL_PARTICLES = GRID_RES_X * GRID_RES_Z;

// Heatmap Color Ramp (Thermal: Dark Navy -> Cyan -> Green -> Amber -> Laser Crimson -> White)
function getHeatmapColor(t, outColor) {
  const clamped = Math.max(0, Math.min(1, t));
  if (clamped < 0.2) {
    const s = clamped / 0.2;
    outColor.setRGB(0.04 + s * 0.0, 0.08 + s * 0.55, 0.2 + s * 0.65);
  } else if (clamped < 0.45) {
    const s = (clamped - 0.2) / 0.25;
    outColor.setRGB(0.0 + s * 0.1, 0.63 + s * 0.25, 0.85 - s * 0.6);
  } else if (clamped < 0.7) {
    const s = (clamped - 0.45) / 0.25;
    outColor.setRGB(0.1 + s * 0.9, 0.88 - s * 0.1, 0.25 - s * 0.2);
  } else if (clamped < 0.9) {
    const s = (clamped - 0.7) / 0.2;
    outColor.setRGB(1.0, 0.78 - s * 0.6, 0.05 + s * 0.2);
  } else {
    const s = (clamped - 0.9) / 0.1;
    outColor.setRGB(1.0, 0.18 + s * 0.82, 0.25 + s * 0.75);
  }
}

export default function SpatialMapViewport({ state = {} }) {
  const containerRef = useRef(null);
  const sceneRef = useRef(null);
  const rendererRef = useRef(null);
  const cameraRef = useRef(null);
  const particlesRef = useRef(null);
  const gazeConeRef = useRef(null);
  const objectsGroupRef = useRef(null);
  const animFrameRef = useRef(null);

  const [activeCamPreset, setActiveCamPreset] = useState('angle');
  const [hoveredObject, setHoveredObject] = useState(null);

  // Extract tracked objects from object_memory, spatial_objects, or detected_blocks
  const trackedObjects = useMemo(() => {
    const list = [];
    if (Array.isArray(state.object_memory) && state.object_memory.length > 0) {
      state.object_memory.forEach((obj, idx) => {
        if (!obj) return;
        const pos = obj.last_position || obj.preferred_position || [
          ((idx * 17) % 36) - 18,
          ((idx * 13) % 24) - 12,
        ];
        list.push({
          id: obj.object_id || `obj_${idx}`,
          label: obj.label || 'Object',
          category: obj.category || 'desk_item',
          confidence: obj.preference_strength ? Math.min(1, 0.6 + obj.preference_strength * 0.4) : 0.88,
          x: pos[0] != null ? (pos[0] > 100 ? (pos[0] - 320) / 12 : pos[0]) : 0,
          z: pos[1] != null ? (pos[1] > 100 ? (pos[1] - 240) / 12 : pos[1]) : 0,
          height: 3.5 + ((idx * 7) % 5),
          status: obj.status || 'tracked',
        });
      });
    } else if (Array.isArray(state.detected_blocks) && state.detected_blocks.length > 0) {
      state.detected_blocks.forEach((blk, idx) => {
        list.push({
          id: `blk_${idx}`,
          label: blk.color || 'Block',
          category: 'block',
          confidence: blk.confidence || 0.92,
          x: blk.x != null ? (blk.x - 320) / 14 : ((idx % 3) - 1) * 8,
          z: blk.y != null ? (blk.y - 240) / 14 : ((Math.floor(idx / 3)) - 1) * 8,
          height: 3.2,
          status: 'detected',
        });
      });
    } else {
      list.push(
        { id: 'demo_1', label: 'Pen Holder', category: 'stationery', confidence: 0.94, x: -10, z: 4, height: 7.0, status: 'scanned' },
        { id: 'demo_2', label: 'Center Desk Mug', category: 'drinkware', confidence: 0.98, x: 6, z: -2, height: 8.5, status: 'scanned' },
        { id: 'demo_3', label: 'Right Work Area', category: 'peripheral', confidence: 0.91, x: 20, z: 6, height: 2.2, status: 'active' }
      );
    }
    return list;
  }, [state.object_memory, state.detected_blocks]);

  // Three.js Scene Setup
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || 600;
    const height = container.clientHeight || 450;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x060911);
    scene.fog = new THREE.FogExp2(0x060911, 0.015);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 36, 42);
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    const ambient = new THREE.AmbientLight(0x223344, 1.2);
    scene.add(ambient);

    const dirLight = new THREE.DirectionalLight(0x88ccff, 1.5);
    dirLight.position.set(20, 50, 20);
    scene.add(dirLight);

    // 1. Desk Boundary & Holographic Base Grid
    const gridHelper = new THREE.GridHelper(WORKSPACE_WIDTH, 30, 0x00f0ff, 0x112233);
    gridHelper.position.y = -0.05;
    scene.add(gridHelper);

    const frameGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-WORKSPACE_WIDTH / 2, 0, -WORKSPACE_DEPTH / 2),
      new THREE.Vector3(WORKSPACE_WIDTH / 2, 0, -WORKSPACE_DEPTH / 2),
      new THREE.Vector3(WORKSPACE_WIDTH / 2, 0, WORKSPACE_DEPTH / 2),
      new THREE.Vector3(-WORKSPACE_WIDTH / 2, 0, WORKSPACE_DEPTH / 2),
      new THREE.Vector3(-WORKSPACE_WIDTH / 2, 0, -WORKSPACE_DEPTH / 2),
    ]);
    const frameMat = new THREE.LineBasicMaterial({ color: 0x00e5ff, transparent: true, opacity: 0.6 });
    scene.add(new THREE.Line(frameGeo, frameMat));

    // Robot arm mounting pedestal at far-left desk edge (-24, 0.6, -8)
    const baseGeo = new THREE.CylinderGeometry(4.0, 4.5, 1.2, 32);
    const baseMat = new THREE.MeshStandardMaterial({
      color: 0x15202e,
      roughness: 0.3,
      metalness: 0.8,
    });
    const baseMesh = new THREE.Mesh(baseGeo, baseMat);
    baseMesh.position.set(-24, 0.6, -8);
    scene.add(baseMesh);

    const ringGeo = new THREE.RingGeometry(4.6, 5.0, 32);
    const ringMat = new THREE.MeshBasicMaterial({ color: 0x00f0ff, side: THREE.DoubleSide, transparent: true, opacity: 0.7 });
    const ringMesh = new THREE.Mesh(ringGeo, ringMat);
    ringMesh.rotation.x = Math.PI / 2;
    ringMesh.position.set(-24, 0.05, -8);
    scene.add(ringMesh);

    // 2. Dense 3D Surface Heatmap
    const particlePositions = new Float32Array(TOTAL_PARTICLES * 3);
    const particleColors = new Float32Array(TOTAL_PARTICLES * 3);

    let idx = 0;
    for (let iz = 0; iz < GRID_RES_Z; iz++) {
      for (let ix = 0; ix < GRID_RES_X; ix++) {
        const x = ((ix / (GRID_RES_X - 1)) - 0.5) * WORKSPACE_WIDTH;
        const z = ((iz / (GRID_RES_Z - 1)) - 0.5) * WORKSPACE_DEPTH;
        particlePositions[idx * 3] = x;
        particlePositions[idx * 3 + 1] = 0.0;
        particlePositions[idx * 3 + 2] = z;

        particleColors[idx * 3] = 0.04;
        particleColors[idx * 3 + 1] = 0.4;
        particleColors[idx * 3 + 2] = 0.8;
        idx++;
      }
    }

    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));
    pGeo.setAttribute('color', new THREE.BufferAttribute(particleColors, 3));

    const canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');
    const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, 'rgba(255,255,255,1)');
    grad.addColorStop(0.35, 'rgba(120,220,255,0.85)');
    grad.addColorStop(0.7, 'rgba(0,180,255,0.3)');
    grad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 64, 64);
    const discTex = new THREE.CanvasTexture(canvas);

    const pMat = new THREE.PointsMaterial({
      size: 1.1,
      vertexColors: true,
      map: discTex,
      transparent: true,
      opacity: 0.92,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const particles = new THREE.Points(pGeo, pMat);
    scene.add(particles);
    particlesRef.current = { points: particles, positions: particlePositions, colors: particleColors };

    // 3. Holographic Gaze Cone (Angled from far left across desk to the right)
    const coneGeo = new THREE.ConeGeometry(7.0, 22, 16, 1, true);
    coneGeo.translate(0, -11, 0);
    const coneMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.18,
      wireframe: true,
      side: THREE.DoubleSide,
    });
    const gazeCone = new THREE.Mesh(coneGeo, coneMat);
    gazeCone.position.set(-20, 16, -6);
    gazeCone.rotation.z = -0.55; // Angle rightward across desk
    gazeCone.rotation.x = 0.25;
    scene.add(gazeCone);
    gazeConeRef.current = gazeCone;

    const objGroup = new THREE.Group();
    scene.add(objGroup);
    objectsGroupRef.current = objGroup;

    // Interactive Orbit / Pan controls
    let isDragging = false;
    let prevMouse = { x: 0, y: 0 };
    let spherical = { radius: 55, theta: Math.PI / 4, phi: Math.PI / 3 };

    const updateCameraPos = () => {
      camera.position.x = spherical.radius * Math.sin(spherical.phi) * Math.sin(spherical.theta);
      camera.position.y = spherical.radius * Math.cos(spherical.phi);
      camera.position.z = spherical.radius * Math.sin(spherical.phi) * Math.cos(spherical.theta);
      camera.lookAt(0, 2, 0);
    };
    updateCameraPos();

    const onMouseDown = (e) => {
      isDragging = true;
      prevMouse = { x: e.clientX, y: e.clientY };
    };

    const onMouseMove = (e) => {
      if (!isDragging) return;
      const dx = e.clientX - prevMouse.x;
      const dy = e.clientY - prevMouse.y;
      prevMouse = { x: e.clientX, y: e.clientY };

      spherical.theta -= dx * 0.008;
      spherical.phi = Math.max(0.15, Math.min(Math.PI / 2 - 0.05, spherical.phi - dy * 0.008));
      updateCameraPos();
    };

    const onMouseUp = () => { isDragging = false; };

    const onWheel = (e) => {
      e.preventDefault();
      spherical.radius = Math.max(20, Math.min(110, spherical.radius + e.deltaY * 0.04));
      updateCameraPos();
    };

    const domEl = renderer.domElement;
    domEl.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    domEl.addEventListener('wheel', onWheel, { passive: false });

    const resizeObserver = new ResizeObserver(() => {
      if (!container || !renderer || !camera) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
    resizeObserver.observe(container);

    let clock = new THREE.Clock();

    const animate = () => {
      animFrameRef.current = requestAnimationFrame(animate);
      const elapsedTime = clock.getElapsedTime();

      if (gazeConeRef.current) {
        gazeConeRef.current.rotation.y = elapsedTime * 0.3;
        const pulse = 0.15 + Math.sin(elapsedTime * 2.5) * 0.04;
        gazeConeRef.current.material.opacity = pulse;
      }

      renderer.render(scene, camera);
    };
    animate();

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      resizeObserver.disconnect();
      domEl.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      domEl.removeEventListener('wheel', onWheel);
      renderer.dispose();
      container.removeChild(renderer.domElement);
    };
  }, []);

  // Update Dynamic 3D Heatmap Surface Points when tracked objects or state update
  useEffect(() => {
    if (!particlesRef.current) return;
    const { points, positions, colors } = particlesRef.current;
    const tempColor = new THREE.Color();

    let idx = 0;
    for (let iz = 0; iz < GRID_RES_Z; iz++) {
      for (let ix = 0; ix < GRID_RES_X; ix++) {
        const x = positions[idx * 3];
        const z = positions[idx * 3 + 2];

        let elevation = 0.0;
        for (const obj of trackedObjects) {
          const dx = x - obj.x;
          const dz = z - obj.z;
          const distSq = dx * dx + dz * dz;
          const radius = 6.0;
          if (distSq < radius * radius) {
            const factor = 1.0 - Math.sqrt(distSq) / radius;
            elevation += factor * factor * (obj.height || 4.5);
          }
        }

        const microNoise = Math.sin(x * 0.4 + z * 0.3) * 0.15;
        const totalHeight = Math.max(0, elevation + microNoise);

        positions[idx * 3 + 1] = totalHeight;

        const heatNorm = Math.min(1.0, totalHeight / 8.0);
        getHeatmapColor(heatNorm, tempColor);
        colors[idx * 3] = tempColor.r;
        colors[idx * 3 + 1] = tempColor.g;
        colors[idx * 3 + 2] = tempColor.b;

        idx++;
      }
    }

    points.geometry.attributes.position.needsUpdate = true;
    points.geometry.attributes.color.needsUpdate = true;
  }, [trackedObjects]);

  // Update 3D Object Markers
  useEffect(() => {
    const group = objectsGroupRef.current;
    if (!group) return;

    while (group.children.length > 0) {
      const child = group.children[0];
      if (child.geometry) child.geometry.dispose();
      if (child.material) {
        if (Array.isArray(child.material)) child.material.forEach((m) => m.dispose());
        else child.material.dispose();
      }
      group.remove(child);
    }

    trackedObjects.forEach((obj) => {
      const objSubGroup = new THREE.Group();
      objSubGroup.position.set(obj.x, 0, obj.z);

      const ringGeo = new THREE.RingGeometry(2.2, 2.5, 24);
      const ringMat = new THREE.MeshBasicMaterial({
        color: 0x00f0ff,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.8,
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = Math.PI / 2;
      ring.position.y = 0.06;
      objSubGroup.add(ring);

      const cylGeo = new THREE.CylinderGeometry(1.8, 1.8, obj.height, 16, 2, true);
      cylGeo.translate(0, obj.height / 2, 0);
      const cylMat = new THREE.MeshStandardMaterial({
        color: 0x00ffff,
        emissive: 0x005577,
        roughness: 0.2,
        metalness: 0.9,
        transparent: true,
        opacity: 0.45,
        wireframe: true,
      });
      const cyl = new THREE.Mesh(cylGeo, cylMat);
      objSubGroup.add(cyl);

      const coreGeo = new THREE.SphereGeometry(0.6, 12, 12);
      const coreMat = new THREE.MeshBasicMaterial({ color: 0xffa600 });
      const core = new THREE.Mesh(coreGeo, coreMat);
      core.position.y = obj.height * 0.65;
      objSubGroup.add(core);

      group.add(objSubGroup);
    });
  }, [trackedObjects]);

  const setCameraPreset = (preset) => {
    setActiveCamPreset(preset);
    if (!cameraRef.current) return;
    const camera = cameraRef.current;
    if (preset === 'top') {
      camera.position.set(0, 58, 0.1);
    } else if (preset === 'front') {
      camera.position.set(0, 14, 52);
    } else {
      camera.position.set(0, 36, 42);
    }
    camera.lookAt(0, 2, 0);
  };

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%', cursor: 'grab' }} />

      {/* Top HUD Controls */}
      <div
        style={{
          position: 'absolute',
          top: 12,
          left: 14,
          right: 14,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          pointerEvents: 'none',
          zIndex: 5,
        }}
      >
        <div style={{ display: 'flex', gap: 6, pointerEvents: 'auto' }}>
          <button
            onClick={() => setCameraPreset('angle')}
            style={{
              padding: '4px 8px',
              fontSize: '10px',
              fontWeight: 600,
              fontFamily: 'monospace',
              letterSpacing: '0.05em',
              background: activeCamPreset === 'angle' ? 'rgba(0, 240, 255, 0.25)' : 'rgba(10, 20, 35, 0.7)',
              color: activeCamPreset === 'angle' ? '#00f0ff' : '#8899aa',
              border: '1px solid rgba(0, 240, 255, 0.3)',
              borderRadius: 4,
              cursor: 'pointer',
              backdropFilter: 'blur(8px)',
            }}
          >
            ISO 45°
          </button>
          <button
            onClick={() => setCameraPreset('top')}
            style={{
              padding: '4px 8px',
              fontSize: '10px',
              fontWeight: 600,
              fontFamily: 'monospace',
              letterSpacing: '0.05em',
              background: activeCamPreset === 'top' ? 'rgba(0, 240, 255, 0.25)' : 'rgba(10, 20, 35, 0.7)',
              color: activeCamPreset === 'top' ? '#00f0ff' : '#8899aa',
              border: '1px solid rgba(0, 240, 255, 0.3)',
              borderRadius: 4,
              cursor: 'pointer',
              backdropFilter: 'blur(8px)',
            }}
          >
            TOP-DOWN
          </button>
          <button
            onClick={() => setCameraPreset('front')}
            style={{
              padding: '4px 8px',
              fontSize: '10px',
              fontWeight: 600,
              fontFamily: 'monospace',
              letterSpacing: '0.05em',
              background: activeCamPreset === 'front' ? 'rgba(0, 240, 255, 0.25)' : 'rgba(10, 20, 35, 0.7)',
              color: activeCamPreset === 'front' ? '#00f0ff' : '#8899aa',
              border: '1px solid rgba(0, 240, 255, 0.3)',
              borderRadius: 4,
              cursor: 'pointer',
              backdropFilter: 'blur(8px)',
            }}
          >
            FRONT
          </button>
        </div>

        {/* Live Spatial Telemetry Pill */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '4px 10px',
            background: 'rgba(6, 12, 22, 0.85)',
            border: '1px solid rgba(0, 240, 255, 0.25)',
            borderRadius: 12,
            fontSize: '10px',
            fontFamily: 'monospace',
            color: '#8be9fd',
            backdropFilter: 'blur(8px)',
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: '#00f0ff',
              boxShadow: '0 0 8px #00f0ff',
              display: 'inline-block',
            }}
          />
          3D SPATIAL MAP · {trackedObjects.length} OBJECTS · FAR-LEFT CALIBRATED
        </div>
      </div>

      {/* Floating 3D Object Cards Overlay */}
      <div
        style={{
          position: 'absolute',
          bottom: 12,
          right: 14,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          maxHeight: '140px',
          overflowY: 'auto',
          pointerEvents: 'auto',
          zIndex: 5,
        }}
      >
        {trackedObjects.map((obj) => (
          <div
            key={obj.id}
            onMouseEnter={() => setHoveredObject(obj.id)}
            onMouseLeave={() => setHoveredObject(null)}
            style={{
              padding: '5px 9px',
              background: hoveredObject === obj.id ? 'rgba(0, 240, 255, 0.2)' : 'rgba(8, 16, 28, 0.8)',
              border: `1px solid ${hoveredObject === obj.id ? '#00f0ff' : 'rgba(0, 240, 255, 0.2)'}`,
              borderRadius: 6,
              fontSize: '10px',
              fontFamily: 'monospace',
              color: '#f0f6fc',
              backdropFilter: 'blur(8px)',
              transition: 'all 0.15s ease',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <span style={{ fontWeight: 600, color: '#00f0ff' }}>{obj.label}</span>
              <span style={{ color: '#ffd166' }}>{Math.round(obj.confidence * 100)}%</span>
            </div>
            <div style={{ fontSize: '9px', color: '#7d8590' }}>
              X: {obj.x.toFixed(1)}cm · Z: {obj.z.toFixed(1)}cm · H: {obj.height.toFixed(1)}cm
            </div>
          </div>
        ))}
      </div>

      {/* Bottom-left Heatmap Elevation Scale */}
      <div
        style={{
          position: 'absolute',
          bottom: 12,
          left: 14,
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          fontSize: '9px',
          fontFamily: 'monospace',
          color: '#8899aa',
          pointerEvents: 'none',
          zIndex: 5,
        }}
      >
        <div style={{ fontWeight: 600, color: '#00f0ff', letterSpacing: '0.05em' }}>
          3D SURROUNDINGS ELEVATION
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span>0cm</span>
          <div
            style={{
              width: 90,
              height: 6,
              borderRadius: 3,
              background: 'linear-gradient(to right, #0a192f, #00f0ff, #06d6a0, #ffd166, #ff0055, #ffffff)',
              boxShadow: '0 0 6px rgba(0, 240, 255, 0.4)',
            }}
          />
          <span>10cm+</span>
        </div>
      </div>
    </div>
  );
}
