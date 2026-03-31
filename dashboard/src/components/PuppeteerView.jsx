/**
 * PuppeteerView — hand tracking + arm teleoperation, integrated into the dashboard.
 *
 * Shows webcam feed with hand skeleton overlay on the left, and the 3D arm
 * model on the right. Hand position streams to the puppet server at 30 FPS.
 * Pinch = gripper close. Fist = grip. Everything in one window.
 */

import React, { useRef, useEffect, useState, useCallback } from 'react';
import { HandTracker } from '../utils/hand-tracker.js';
import { PuppetBridge } from '../utils/puppet-bridge.js';
import SimulatedArm from './SimulatedArm/SimulatedArm.jsx';

export default function PuppeteerView() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const trackerRef = useRef(null);
  const bridgeRef = useRef(null);

  const [tracking, setTracking] = useState(false);
  const [bridgeConnected, setBridgeConnected] = useState(false);
  const [armAngles, setArmAngles] = useState([0, 0, 0, 0, 0]);
  const [gripperOpen, setGripperOpen] = useState(true);
  const [gestures, setGestures] = useState({ pinching: false, fist: false });
  const [error, setError] = useState(null);

  // Initialize puppet bridge
  useEffect(() => {
    const bridge = new PuppetBridge();
    bridgeRef.current = bridge;

    bridge.callbacks.onConnect = () => setBridgeConnected(true);
    bridge.callbacks.onDisconnect = () => setBridgeConnected(false);
    bridge.callbacks.onArmUpdate = (msg) => {
      setArmAngles(msg.angles || [0, 0, 0, 0, 0]);
      setGripperOpen(!msg.gripper);
    };

    bridge.connect();

    return () => bridge.disconnect();
  }, []);

  // Hand tracking results → puppet bridge
  const handleLandmarks = useCallback((landmarks) => {
    const bridge = bridgeRef.current;
    if (!bridge) return;

    bridge.updateLandmarks(landmarks);

    if (landmarks) {
      setGestures({
        pinching: bridge.isPinching,
        fist: bridge.isFist,
      });
    }
  }, []);

  // Start hand tracking
  const startTracking = useCallback(async () => {
    if (tracking) return;
    setError(null);

    try {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas) return;

      const tracker = new HandTracker(video, canvas, handleLandmarks);
      trackerRef.current = tracker;

      await tracker.initialize();
      await tracker.start();
      setTracking(true);

      // Start streaming hand data to puppet server
      if (bridgeRef.current?.connected) {
        bridgeRef.current.startStreaming();
      }
    } catch (e) {
      setError(e.message);
    }
  }, [tracking, handleLandmarks]);

  // Stop tracking on unmount
  useEffect(() => {
    return () => {
      trackerRef.current?.stop();
      bridgeRef.current?.stopStreaming();
    };
  }, []);

  // Auto-start streaming when bridge connects while tracking
  useEffect(() => {
    if (tracking && bridgeConnected) {
      bridgeRef.current?.startStreaming();
    }
  }, [tracking, bridgeConnected]);

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%', gap: 1 }}>
      {/* Left: Webcam + hand overlay */}
      <div style={{ flex: 1, position: 'relative', background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <video
          ref={videoRef}
          style={{ width: '100%', height: '100%', objectFit: 'contain', transform: 'scaleX(-1)' }}
          autoPlay
          playsInline
          muted
        />
        <canvas
          ref={canvasRef}
          width={640}
          height={480}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'contain',
            transform: 'scaleX(-1)',
            pointerEvents: 'none',
          }}
        />

        {/* Overlay UI */}
        <div style={{
          position: 'absolute', top: 12, left: 14, right: 14,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          pointerEvents: 'none',
        }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: bridgeConnected ? 'var(--green)' : 'var(--red)',
              boxShadow: `0 0 6px ${bridgeConnected ? 'var(--green)' : 'var(--red)'}`,
            }} />
            <span style={{ fontSize: 10, color: 'var(--text-secondary)', fontWeight: 500 }}>
              {bridgeConnected ? 'Puppet Server' : 'Disconnected'}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {gestures.pinching && (
              <span style={{ fontSize: 9, fontWeight: 600, color: 'var(--accent)', background: 'var(--accent-soft)', padding: '2px 8px', borderRadius: 100 }}>
                PINCH
              </span>
            )}
            {gestures.fist && (
              <span style={{ fontSize: 9, fontWeight: 600, color: 'var(--orange)', background: 'rgba(255,159,10,0.15)', padding: '2px 8px', borderRadius: 100 }}>
                FIST
              </span>
            )}
          </div>
        </div>

        {/* Start button (before tracking starts) */}
        {!tracking && (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)',
          }}>
            <button
              onClick={startTracking}
              style={{
                background: 'var(--accent-soft)',
                border: '1px solid rgba(124,92,255,0.3)',
                color: 'var(--accent)',
                fontSize: 13,
                fontWeight: 600,
                fontFamily: 'var(--font)',
                padding: '10px 28px',
                borderRadius: 100,
                cursor: 'pointer',
                letterSpacing: '0.02em',
              }}
            >
              Start Hand Tracking
            </button>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 10 }}>
              Requires webcam access
            </span>
            {error && (
              <span style={{ fontSize: 11, color: 'var(--red)', marginTop: 8 }}>{error}</span>
            )}
          </div>
        )}
      </div>

      {/* Right: 3D arm visualization */}
      <div style={{ flex: 1, position: 'relative', background: '#000' }}>
        <SimulatedArm angles={armAngles} gripperOpen={gripperOpen} />
        <div className="viewport-tag">Live Arm</div>
      </div>
    </div>
  );
}
