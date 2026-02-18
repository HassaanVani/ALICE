import React from 'react';

const styles = {
  container: {
    width: '100%',
    height: '100%',
    display: 'flex',
    gap: 12,
    padding: 12,
  },
  svgContainer: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  jointList: {
    width: 140,
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    justifyContent: 'center',
  },
  jointRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  jointLabel: {
    fontSize: 10,
    color: '#a1a1aa',
    fontFamily: 'var(--font-mono)',
    width: 22,
    textAlign: 'right',
  },
  jointBar: {
    flex: 1,
    height: 6,
    background: '#18181b',
    borderRadius: 3,
    overflow: 'hidden',
  },
  jointValue: {
    fontSize: 10,
    color: '#52525b',
    fontFamily: 'var(--font-mono)',
    width: 42,
    textAlign: 'right',
  },
  gripperLabel: {
    fontSize: 10,
    color: '#a1a1aa',
    fontFamily: 'var(--font-mono)',
    textAlign: 'center',
    marginTop: 8,
  },
};

const JOINT_NAMES = ['J1', 'J2', 'J3', 'J4', 'J5', 'J6'];

// Simple 2D arm kinematics for visualization
function computeArmPoints(joints) {
  const segmentLengths = [60, 50, 40, 25, 20, 15];
  const points = [{ x: 160, y: 260 }]; // base position
  let cumulativeAngle = -Math.PI / 2; // start pointing up

  for (let i = 0; i < Math.min(joints.length, 6); i++) {
    const angle = ((joints[i] || 0) * Math.PI) / 180;
    cumulativeAngle += angle * 0.5; // scale rotation for visual clarity
    const len = segmentLengths[i];
    const prev = points[points.length - 1];
    points.push({
      x: prev.x + Math.cos(cumulativeAngle) * len,
      y: prev.y + Math.sin(cumulativeAngle) * len,
    });
  }

  return points;
}

export default function ArmStatus({ joints, gripperOpen }) {
  const armPoints = computeArmPoints(joints);
  const endEffector = armPoints[armPoints.length - 1];

  return (
    <div style={styles.container}>
      {/* SVG Arm Diagram */}
      <div style={styles.svgContainer}>
        <svg viewBox="0 0 320 300" style={{ width: '100%', height: '100%' }}>
          <defs>
            <linearGradient id="armGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#1d4ed8" stopOpacity="0.4" />
            </linearGradient>
            <filter id="glow">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Grid */}
          {Array.from({ length: 7 }).map((_, i) => (
            <React.Fragment key={`grid-${i}`}>
              <line
                x1={i * 53}
                y1={0}
                x2={i * 53}
                y2={300}
                stroke="#27272a"
                strokeWidth={0.5}
                opacity={0.3}
              />
              <line
                x1={0}
                y1={i * 50}
                x2={320}
                y2={i * 50}
                stroke="#27272a"
                strokeWidth={0.5}
                opacity={0.3}
              />
            </React.Fragment>
          ))}

          {/* Base platform */}
          <rect x={130} y={260} width={60} height={12} rx={3} fill="#27272a" />
          <rect x={140} y={255} width={40} height={8} rx={2} fill="#3f3f46" />

          {/* Arm segments */}
          {armPoints.map((pt, i) => {
            if (i === 0) return null;
            const prev = armPoints[i - 1];
            const thickness = 6 - i * 0.7;
            return (
              <line
                key={`seg-${i}`}
                x1={prev.x}
                y1={prev.y}
                x2={pt.x}
                y2={pt.y}
                stroke="url(#armGrad)"
                strokeWidth={thickness}
                strokeLinecap="round"
                filter="url(#glow)"
              />
            );
          })}

          {/* Joint circles */}
          {armPoints.map((pt, i) => (
            <g key={`joint-${i}`}>
              <circle
                cx={pt.x}
                cy={pt.y}
                r={i === 0 ? 6 : 4}
                fill="#09090b"
                stroke="#3b82f6"
                strokeWidth={1.5}
              />
              <circle cx={pt.x} cy={pt.y} r={1.5} fill="#3b82f6" />
            </g>
          ))}

          {/* End effector / Gripper */}
          <g transform={`translate(${endEffector.x}, ${endEffector.y})`}>
            {/* Left finger */}
            <rect
              x={gripperOpen ? -10 : -5}
              y={-2}
              width={3}
              height={14}
              rx={1}
              fill="#22c55e"
              opacity={0.8}
              style={{ transition: 'x 0.3s ease' }}
            />
            {/* Right finger */}
            <rect
              x={gripperOpen ? 7 : 2}
              y={-2}
              width={3}
              height={14}
              rx={1}
              fill="#22c55e"
              opacity={0.8}
              style={{ transition: 'x 0.3s ease' }}
            />
          </g>

          {/* Gripper state label */}
          <text
            x={endEffector.x}
            y={endEffector.y + 24}
            textAnchor="middle"
            fill={gripperOpen ? '#22c55e' : '#eab308'}
            fontSize={8}
            fontFamily="monospace"
          >
            {gripperOpen ? 'OPEN' : 'CLOSED'}
          </text>

          {/* Coordinate info */}
          <text x={6} y={14} fill="#52525b" fontSize={8} fontFamily="monospace">
            EE: ({endEffector.x.toFixed(0)}, {endEffector.y.toFixed(0)})
          </text>
        </svg>
      </div>

      {/* Joint angle readout */}
      <div style={styles.jointList}>
        {JOINT_NAMES.map((name, i) => {
          const angle = joints[i] || 0;
          const normalized = (angle + 180) / 360; // map -180..180 to 0..1
          return (
            <div key={name} style={styles.jointRow}>
              <span style={styles.jointLabel}>{name}</span>
              <div style={styles.jointBar}>
                <div
                  style={{
                    width: `${Math.max(2, normalized * 100)}%`,
                    height: '100%',
                    background: Math.abs(angle) > 150 ? '#ef4444' : '#3b82f6',
                    borderRadius: 3,
                    transition: 'width 0.2s ease',
                  }}
                />
              </div>
              <span style={styles.jointValue}>{angle.toFixed(1)}</span>
            </div>
          );
        })}
        <div style={styles.gripperLabel}>
          Gripper: <span style={{ color: gripperOpen ? '#22c55e' : '#eab308' }}>
            {gripperOpen ? 'OPEN' : 'CLOSED'}
          </span>
        </div>
      </div>
    </div>
  );
}
