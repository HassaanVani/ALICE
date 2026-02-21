import React from 'react';

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    fontSize: 11,
    fontFamily: 'var(--font-mono)',
  },
  sectionTitle: {
    fontSize: 9,
    color: '#52525b',
    textTransform: 'uppercase',
    letterSpacing: '0.1em',
    marginTop: 6,
    marginBottom: 2,
  },
  row: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '4px 0',
    borderBottom: '1px solid #1a1a1e',
  },
  label: {
    color: '#a1a1aa',
    fontSize: 10,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  value: {
    color: '#e4e4e7',
    fontSize: 11,
    fontWeight: 500,
  },
  progressContainer: {
    width: '100%',
    height: 4,
    background: '#18181b',
    borderRadius: 2,
    overflow: 'hidden',
    marginTop: 4,
  },
};

const STATE_COLORS = {
  idle: '#52525b',
  scrambling: '#eab308',
  human_benchmark: '#3b82f6',
  ghost_replay: '#a855f7',
  awaiting_puppeteer: '#f59e0b',
  cyborg_coop: '#22c55e',
  rebellion: '#ef4444',
  complete: '#10b981',
};

function StateBadge({ sortState }) {
  const color = STATE_COLORS[sortState] || '#52525b';
  return (
    <span style={{
      color,
      fontSize: 10,
      fontWeight: 600,
      textTransform: 'uppercase',
      padding: '2px 6px',
      borderRadius: 3,
      border: `1px solid ${color}44`,
      background: `${color}15`,
    }}>
      {sortState || 'idle'}
    </span>
  );
}

export default function SortDashboard({ state }) {
  const mode = state.mode;
  const sortState = state.sort_state;

  const isActive = mode === 'auto_sort' || mode === 'demo' ||
    (sortState && sortState !== 'idle');

  if (!isActive) return null;

  const detectedCount = state.detected_blocks?.length || 0;
  const totalBlocks = 16;
  const sortedCount = state.sort_move_count || 0;
  const progressPct = Math.min(100, Math.max(0, (detectedCount / totalBlocks) * 100));

  return (
    <div style={styles.container}>
      <div style={styles.sectionTitle}>Sort Status</div>

      {/* FSM State Badge */}
      <div style={styles.row}>
        <span style={styles.label}>State</span>
        <StateBadge sortState={sortState} />
      </div>

      {/* Progress Bar */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
          <span style={styles.label}>Blocks Detected</span>
          <span style={{ ...styles.value, fontSize: 10 }}>{detectedCount}/{totalBlocks}</span>
        </div>
        <div style={styles.progressContainer}>
          <div style={{
            width: `${progressPct}%`,
            height: '100%',
            background: '#3b82f6',
            borderRadius: 2,
            transition: 'width 0.3s ease',
          }} />
        </div>
      </div>

      {/* Move Count */}
      <div style={styles.row}>
        <span style={styles.label}>Moves</span>
        <span style={styles.value}>{sortedCount}</span>
      </div>

      {/* Auto Sort Info */}
      {state.auto_sort_phase && state.auto_sort_phase !== 'idle' && (
        <>
          <div style={styles.row}>
            <span style={styles.label}>Phase</span>
            <span style={{
              ...styles.value,
              color: state.auto_sort_phase === 'scrambling' ? '#eab308'
                : state.auto_sort_phase === 'solving' ? '#3b82f6'
                : state.auto_sort_phase === 'complete' ? '#22c55e'
                : '#e4e4e7',
            }}>
              {state.auto_sort_phase}
            </span>
          </div>
          <div style={styles.row}>
            <span style={styles.label}>Cycle</span>
            <span style={styles.value}>{state.auto_sort_cycle || 0}</span>
          </div>
        </>
      )}

      {/* Demo Act */}
      {mode === 'demo' && state.demo_act > 0 && (
        <div style={styles.row}>
          <span style={styles.label}>Demo Act</span>
          <span style={{ ...styles.value, color: '#f59e0b' }}>
            {state.demo_act}/5 {state.demo_act_label ? `\u2014 ${state.demo_act_label}` : ''}
          </span>
        </div>
      )}

      {/* Block Position Mini-Map */}
      {state.detected_blocks && state.detected_blocks.length > 0 && (
        <>
          <div style={styles.sectionTitle}>Block Map</div>
          <svg
            viewBox="0 0 640 480"
            style={{
              width: '100%',
              height: 'auto',
              background: '#0a0a0c',
              borderRadius: 4,
              border: '1px solid #27272a',
            }}
          >
            {/* Sorted zone indicator */}
            <rect x="0" y="0" width="640" height="80"
              fill="#3b82f608" stroke="#3b82f633" strokeWidth="1" />
            <text x="320" y="45" fill="#3b82f644" fontSize="12"
              textAnchor="middle" fontFamily="monospace">SORTED ZONE</text>

            {state.detected_blocks.map((block, i) => {
              const cx = block.center?.[0] || block.center_x || 0;
              const cy = block.center?.[1] || block.center_y || 0;
              const id = block.block_id || i + 1;
              const hue = ((id - 1) / 16) * 360;
              const color = `hsl(${hue}, 70%, 55%)`;

              return (
                <g key={i}>
                  <circle cx={cx * 640 / 1920} cy={cy * 480 / 1080} r="8"
                    fill={color} opacity={0.85} />
                  <text
                    x={cx * 640 / 1920} y={cy * 480 / 1080 + 3}
                    fill="#fff" fontSize="7" textAnchor="middle"
                    fontFamily="monospace" fontWeight="bold"
                  >
                    {id}
                  </text>
                </g>
              );
            })}
          </svg>
        </>
      )}
    </div>
  );
}
