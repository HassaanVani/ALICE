import React, { useRef, useEffect } from 'react';

const styles = {
  container: {
    width: '100%',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  layerRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  layerLabel: {
    fontSize: 10,
    color: '#a1a1aa',
    fontFamily: 'var(--font-mono)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    display: 'flex',
    justifyContent: 'space-between',
  },
  barContainer: {
    display: 'flex',
    gap: 1,
    alignItems: 'flex-end',
    height: 48,
    background: 'rgba(255,255,255,0.02)',
    borderRadius: 3,
    padding: '4px 2px',
    overflow: 'hidden',
  },
  placeholder: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    color: '#52525b',
    fontSize: 11,
    fontFamily: 'var(--font-mono)',
  },
};

function valueToColor(val) {
  // Map -1..1 or 0..1 activations to a color gradient
  const v = Math.max(0, Math.min(1, Math.abs(val)));
  if (val < 0) {
    // Negative: blue spectrum
    const r = Math.floor(20 + v * 30);
    const g = Math.floor(20 + v * 60);
    const b = Math.floor(100 + v * 155);
    return `rgb(${r},${g},${b})`;
  }
  // Positive: cyan-to-green spectrum
  const r = Math.floor(20 + v * 20);
  const g = Math.floor(80 + v * 175);
  const b = Math.floor(180 - v * 100);
  return `rgb(${r},${g},${b})`;
}

function LayerBars({ layer }) {
  const maxBars = 64;
  const values = layer.values.length > maxBars
    ? layer.values.filter((_, i) => i % Math.ceil(layer.values.length / maxBars) === 0)
    : layer.values;

  const max = Math.max(...values.map(Math.abs), 0.001);
  const mean = values.reduce((a, b) => a + Math.abs(b), 0) / (values.length || 1);

  return (
    <div style={styles.layerRow}>
      <div style={styles.layerLabel}>
        <span>{layer.name}</span>
        <span style={{ color: '#52525b' }}>
          avg: {mean.toFixed(3)} | {layer.values.length} units
        </span>
      </div>
      <div style={styles.barContainer}>
        {values.map((val, i) => {
          const height = (Math.abs(val) / max) * 100;
          return (
            <div
              key={i}
              style={{
                flex: 1,
                minWidth: 2,
                maxWidth: 8,
                height: `${Math.max(height, 2)}%`,
                background: valueToColor(val),
                borderRadius: '1px 1px 0 0',
                opacity: 0.6 + (Math.abs(val) / max) * 0.4,
                transition: 'height 0.1s ease',
              }}
            />
          );
        })}
      </div>
    </div>
  );
}

export default function ActivationPanel({ activations }) {
  if (!activations || activations.length === 0) {
    return (
      <div style={{ ...styles.container, gap: 14 }}>
        {[1, 2, 3].map((n) => (
          <div key={n} style={styles.layerRow}>
            <div style={{ ...styles.layerLabel, opacity: 0.4 }}>
              <span style={{
                width: 60,
                height: 10,
                borderRadius: 3,
                background: 'linear-gradient(90deg, #27272a 25%, #3f3f46 50%, #27272a 75%)',
                backgroundSize: '200% 100%',
                animation: 'shimmer 1.5s infinite',
                display: 'inline-block',
              }} />
            </div>
            <div style={{
              ...styles.barContainer,
              background: 'linear-gradient(90deg, #27272a 25%, #3f3f46 50%, #27272a 75%)',
              backgroundSize: '200% 100%',
              animation: `shimmer 1.5s infinite ${n * 0.2}s`,
            }} />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div style={styles.container}>
      {activations.map((layer, i) => (
        <LayerBars key={`${layer.name}-${i}`} layer={layer} />
      ))}
    </div>
  );
}
