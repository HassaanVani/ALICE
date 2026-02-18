import React from 'react';

const COLORS = {
  red: '#ef4444',
  blue: '#3b82f6',
  green: '#22c55e',
  yellow: '#eab308',
  orange: '#f97316',
  purple: '#a855f7',
  default: '#e4e4e7',
};

function getBlockColor(block) {
  return COLORS[block.color?.toLowerCase()] || COLORS.default;
}

export default function BlockOverlay({ blocks }) {
  if (!blocks || blocks.length === 0) return null;

  return (
    <svg
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 10,
      }}
      viewBox="0 0 640 480"
      preserveAspectRatio="xMidYMid meet"
    >
      {blocks.map((block, i) => {
        const color = getBlockColor(block);
        const x = block.x ?? 0;
        const y = block.y ?? 0;
        const w = block.width ?? 40;
        const h = block.height ?? 40;
        const confidence = block.confidence ?? 0;
        const id = block.id ?? i;

        return (
          <g key={`block-${id}`}>
            {/* Bounding box */}
            <rect
              x={x - w / 2}
              y={y - h / 2}
              width={w}
              height={h}
              fill="none"
              stroke={color}
              strokeWidth={2}
              strokeDasharray={confidence < 0.5 ? '4,4' : 'none'}
              opacity={0.4 + confidence * 0.6}
            />

            {/* Corner accents */}
            <line x1={x - w / 2} y1={y - h / 2} x2={x - w / 2 + 8} y2={y - h / 2} stroke={color} strokeWidth={2} />
            <line x1={x - w / 2} y1={y - h / 2} x2={x - w / 2} y2={y - h / 2 + 8} stroke={color} strokeWidth={2} />
            <line x1={x + w / 2} y1={y - h / 2} x2={x + w / 2 - 8} y2={y - h / 2} stroke={color} strokeWidth={2} />
            <line x1={x + w / 2} y1={y - h / 2} x2={x + w / 2} y2={y - h / 2 + 8} stroke={color} strokeWidth={2} />

            {/* Center crosshair */}
            <circle cx={x} cy={y} r={2} fill={color} opacity={0.8} />

            {/* Label background */}
            <rect
              x={x - w / 2}
              y={y - h / 2 - 18}
              width={Math.max(w, 60)}
              height={16}
              fill="rgba(0,0,0,0.75)"
              rx={2}
            />

            {/* Block ID */}
            <text
              x={x - w / 2 + 4}
              y={y - h / 2 - 6}
              fill={color}
              fontSize={10}
              fontFamily="monospace"
              fontWeight="bold"
            >
              #{id}
            </text>

            {/* Confidence */}
            <text
              x={x - w / 2 + 30}
              y={y - h / 2 - 6}
              fill="#a1a1aa"
              fontSize={9}
              fontFamily="monospace"
            >
              {(confidence * 100).toFixed(0)}%
            </text>
          </g>
        );
      })}

      {/* Block count indicator */}
      <rect x={4} y={4} width={80} height={20} rx={3} fill="rgba(0,0,0,0.7)" />
      <text x={10} y={17} fill="#3b82f6" fontSize={10} fontFamily="monospace" fontWeight="bold">
        {blocks.length} BLOCKS
      </text>
    </svg>
  );
}
