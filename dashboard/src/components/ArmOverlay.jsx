import React, { useRef, useEffect } from 'react';
import { computeTopDownPositions } from './SimulatedArm/forwardKinematics';
import { DEFAULT_ANGLES, SCALE, ARM_DIMS } from './SimulatedArm/armConstants';

const COLORS = {
  upperArm: '#3b82f6',
  forearm: '#6366f1',
  hand: '#8b5cf6',
  joint: '#e4e4e7',
  ee: '#22c55e',
  eeClosed: '#eab308',
  reach: 'rgba(59, 130, 246, 0.08)',
  reachStroke: 'rgba(59, 130, 246, 0.15)',
};

/**
 * 2D top-down arm overlay for the camera panel.
 * Draws the arm's XZ projection over the live camera feed.
 */
export default function ArmOverlay({ angles = DEFAULT_ANGLES, gripperOpen = true }) {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);
  const anglesRef = useRef([...DEFAULT_ANGLES]);
  const gripperRef = useRef(true);

  useEffect(() => {
    anglesRef.current = angles && angles.length >= 5 ? [...angles] : [...DEFAULT_ANGLES];
    gripperRef.current = gripperOpen;
  }, [angles, gripperOpen]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let dpr = 1;

    const render = () => {
      const parent = canvas.parentElement;
      if (!parent) { rafRef.current = requestAnimationFrame(render); return; }

      const rect = parent.getBoundingClientRect();
      const w = Math.round(rect.width);
      const h = Math.round(rect.height);
      dpr = Math.min(window.devicePixelRatio, 2);

      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        canvas.style.width = w + 'px';
        canvas.style.height = h + 'px';
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }

      ctx.clearRect(0, 0, w, h);

      const pos = computeTopDownPositions(anglesRef.current);

      // Coordinate mapping: arm base at center-bottom of canvas
      const baseX = w / 2;
      const baseY = h * 0.82;
      const scale = h / 14;

      const toCanvas = (p) => ({
        x: baseX + p.x * scale,
        y: baseY - p.y * scale,
      });

      // Reach circle
      const maxReach = (ARM_DIMS.shoulderLength + ARM_DIMS.elbowLength + ARM_DIMS.wristLength) * SCALE;
      ctx.beginPath();
      ctx.arc(baseX, baseY, maxReach * scale, 0, Math.PI * 2);
      ctx.fillStyle = COLORS.reach;
      ctx.fill();
      ctx.strokeStyle = COLORS.reachStroke;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Arm segments
      const segments = [
        { from: 'shoulder', to: 'elbow', color: COLORS.upperArm, width: 4 },
        { from: 'elbow', to: 'wrist', color: COLORS.forearm, width: 3.5 },
        { from: 'wrist', to: 'endEffector', color: COLORS.hand, width: 3 },
      ];

      ctx.globalAlpha = 0.8;
      segments.forEach(({ from, to, color, width }) => {
        const p1 = toCanvas(pos[from]);
        const p2 = toCanvas(pos[to]);
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.strokeStyle = color;
        ctx.lineWidth = width;
        ctx.lineCap = 'round';
        ctx.stroke();
      });
      ctx.globalAlpha = 1;

      // Joint dots
      const jointKeys = ['base', 'elbow', 'wrist', 'endEffector'];
      const jointSizes = [4, 4.5, 4, 3.5];

      jointKeys.forEach((key, i) => {
        const p = toCanvas(pos[key]);
        const isEE = key === 'endEffector';
        ctx.beginPath();
        ctx.arc(p.x, p.y, jointSizes[i], 0, Math.PI * 2);
        ctx.fillStyle = isEE
          ? (gripperRef.current ? COLORS.ee : COLORS.eeClosed)
          : COLORS.joint;
        ctx.globalAlpha = 0.9;
        ctx.fill();
        ctx.globalAlpha = 1;
      });

      rafRef.current = requestAnimationFrame(render);
    };

    rafRef.current = requestAnimationFrame(render);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 10,
      }}
    />
  );
}
