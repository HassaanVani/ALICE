import { useState, useEffect, useRef, useCallback } from 'react';
import { AUDIENCE_WS_URL } from '../ws-config.js';

const REACTIONS = ['👏', '🔥', '😮', '💀', '🤖', '🧠'];

const BLOCK_COLORS = {
  1: '#ef4444', 2: '#f97316', 3: '#eab308', 4: '#84cc16',
  5: '#22c55e', 6: '#14b8a6', 7: '#06b6d4', 8: '#3b82f6',
  9: '#6366f1', 10: '#8b5cf6', 11: '#a855f7', 12: '#d946ef',
  13: '#ec4899', 14: '#f43f5e', 15: '#fb923c', 16: '#a3e635',
};

function getBlockColor(id) {
  return BLOCK_COLORS[id] || '#71717a';
}

// ─── Main Component ─────────────────────────────────────────────

export default function Audience() {
  const [connected, setConnected] = useState(false);
  const [clientId, setClientId] = useState(null);
  const [audienceCount, setAudienceCount] = useState(0);
  const [phase, setPhase] = useState({ label: 'Connecting...', desc: '', interactive: false });
  const [blocks, setBlocks] = useState([]);
  const [votes, setVotes] = useState({});
  const [myVote, setMyVote] = useState(null);
  const [leadingBlock, setLeadingBlock] = useState(null);
  const [lastWinner, setLastWinner] = useState(null);
  const [winnerFlash, setWinnerFlash] = useState(null);
  const [robotAction, setRobotAction] = useState(null);
  const [override, setOverride] = useState(null);  // rebellion: {crowd_choice, robot_choice, reason}
  const [sortState, setSortState] = useState('idle');
  const [score, setScore] = useState(0);
  const [floatingReactions, setFloatingReactions] = useState([]);
  const [tiltEnabled, setTiltEnabled] = useState(false);
  const [tilt, setTilt] = useState({ beta: 0, gamma: 0 });
  const [presetVotes, setPresetVotes] = useState({});
  const [myPresetVote, setMyPresetVote] = useState(null);
  const [presetResult, setPresetResult] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const reactionIdRef = useRef(0);
  const reactionTimers = useRef([]);

  // ── WebSocket ───────────────────────────────────────────────

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(AUDIENCE_WS_URL);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);

          if (msg.type === 'welcome') {
            setClientId(msg.client_id);
            setAudienceCount(msg.audience_count);
            if (msg.phase) setPhase(msg.phase);
            if (msg.votes) setVotes(msg.votes);
            if (msg.state?.detected_blocks) setBlocks(msg.state.detected_blocks);
            if (msg.state?.sort_state) setSortState(msg.state.sort_state);
            if (msg.state?.tetris_score) setScore(msg.state.tetris_score);
            if (msg.last_winner) setLastWinner(msg.last_winner);
          }

          else if (msg.type === 'state_update') {
            if (msg.phase) setPhase(msg.phase);
            if (msg.audience_count != null) setAudienceCount(msg.audience_count);
            if (msg.votes) setVotes(msg.votes);
            if (msg.state?.detected_blocks) setBlocks(msg.state.detected_blocks);
            if (msg.state?.sort_state) setSortState(msg.state.sort_state);
            if (msg.state?.tetris_score != null) setScore(msg.state.tetris_score);
            if (msg.last_winner) setLastWinner(msg.last_winner);
          }

          else if (msg.type === 'vote_update') {
            setVotes(msg.votes || {});
            setLeadingBlock(msg.leading);
          }

          else if (msg.type === 'vote_ack') {
            setMyVote(msg.block_id);
          }

          else if (msg.type === 'vote_winner') {
            setWinnerFlash(msg);
            setMyVote(null);
            setVotes({});
            // Clear flash after 3 seconds
            setTimeout(() => setWinnerFlash(null), 3000);
          }

          else if (msg.type === 'vote_override') {
            setOverride(msg);
            setMyVote(null);
            setVotes({});
            setTimeout(() => setOverride(null), 4000);
          }

          else if (msg.type === 'robot_action') {
            setRobotAction(msg);
            setTimeout(() => setRobotAction(null), 2000);
          }

          else if (msg.type === 'audience_count') {
            setAudienceCount(msg.count);
          }

          else if (msg.type === 'preset_vote_update') {
            setPresetVotes(msg.votes || {});
          }

          else if (msg.type === 'preset_vote_ack') {
            setMyPresetVote(msg.preset);
          }

          else if (msg.type === 'preset_result') {
            setPresetResult(msg);
            setTimeout(() => setPresetResult(null), 4000);
          }

          else if (msg.type === 'reaction') {
            spawnFloatingReaction(msg.emoji);
          }

        } catch { /* ignore parse errors */ }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        reconnectTimer.current = setTimeout(connect, 2000);
      };

      ws.onerror = () => ws.close();
    } catch {
      reconnectTimer.current = setTimeout(connect, 2000);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      reactionTimers.current.forEach(t => clearTimeout(t));
      reactionTimers.current = [];
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  // ── Send helpers ────────────────────────────────────────────

  const send = (msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  };

  const voteForBlock = (blockId) => {
    send({ type: 'vote_block', block_id: blockId });
  };

  const voteForPreset = (preset) => {
    send({ type: 'vote_preset', preset });
  };

  const sendReaction = (emoji) => {
    send({ type: 'reaction', emoji });
    spawnFloatingReaction(emoji);
  };

  // ── Floating reactions ──────────────────────────────────────

  const spawnFloatingReaction = (emoji) => {
    const id = reactionIdRef.current++;
    const x = 20 + Math.random() * 60; // 20-80% of screen width
    setFloatingReactions(prev => [...prev.slice(-20), { id, emoji, x }]);
    const timer = setTimeout(() => {
      setFloatingReactions(prev => prev.filter(r => r.id !== id));
      reactionTimers.current = reactionTimers.current.filter(t => t !== timer);
    }, 2000);
    reactionTimers.current.push(timer);
  };

  // ── Device tilt ─────────────────────────────────────────────

  const enableTilt = async () => {
    try {
      if (typeof DeviceOrientationEvent !== 'undefined' &&
          typeof DeviceOrientationEvent.requestPermission === 'function') {
        const perm = await DeviceOrientationEvent.requestPermission();
        if (perm !== 'granted') return;
      }
      setTiltEnabled(true);
    } catch { /* not available */ }
  };

  useEffect(() => {
    if (!tiltEnabled) return;
    let throttle = 0;
    const handle = (e) => {
      const beta = e.beta || 0;
      const gamma = e.gamma || 0;
      setTilt({ beta, gamma });
      // Throttle sends to ~10hz
      const now = Date.now();
      if (now - throttle > 100) {
        throttle = now;
        send({
          type: 'tilt',
          beta: Math.round(beta * 10) / 10,
          gamma: Math.round(gamma * 10) / 10,
        });
      }
    };
    window.addEventListener('deviceorientation', handle);
    return () => window.removeEventListener('deviceorientation', handle);
  }, [tiltEnabled]);

  // ── Derived state ───────────────────────────────────────────

  const isInteractive = phase.interactive;
  const totalVotes = Object.values(votes).reduce((a, b) => a + b, 0);
  const iWon = winnerFlash && winnerFlash.voter_ids?.includes(clientId);

  // ── Render ──────────────────────────────────────────────────

  return (
    <div style={styles.page}>

      {/* Floating reactions */}
      {floatingReactions.map(r => (
        <div key={r.id} style={{ ...styles.floatingReaction, left: `${r.x}%` }}>
          {r.emoji}
        </div>
      ))}

      {/* ── Header bar ── */}
      <div style={styles.header}>
        <div style={styles.headerRow}>
          <div style={styles.logoMark}>A</div>
          <div style={styles.headerInfo}>
            <div style={styles.phaseLabel}>{phase.label}</div>
            <div style={styles.phaseDesc}>{phase.desc}</div>
          </div>
          <div style={styles.headerRight}>
            <div style={{
              ...styles.connectionDot,
              background: connected ? '#22c55e' : '#ef4444',
              boxShadow: connected ? '0 0 8px #22c55e80' : '0 0 8px #ef444480',
            }} />
            <span style={styles.audienceCount}>{audienceCount}</span>
          </div>
        </div>
      </div>

      {/* ── Score bar (contextual) ── */}
      {(sortState !== 'idle' || score > 0) && (
        <div style={styles.scorebar}>
          {sortState === 'cyborg_coop' && <span>CYBORG MODE</span>}
          {sortState === 'rebellion' && <span style={{ color: '#ef4444' }}>ALICE IS IN CONTROL</span>}
          {sortState === 'awaiting_puppeteer' && <span style={{ color: '#22c55e' }}>PUPPETEER — VOLUNTEER UP!</span>}
          {sortState === 'human_benchmark' && <span>HUMAN SORTING...</span>}
          {sortState === 'ghost_replay' && <span>GHOST REPLAY</span>}
          {sortState === 'complete' && <span>COMPLETE!</span>}
          {score > 0 && <span>SCORE: {score}</span>}
        </div>
      )}

      {/* ── Winner flash ── */}
      {winnerFlash && (
        <div style={{
          ...styles.winnerBanner,
          background: iWon ? 'rgba(34,197,94,0.15)' : 'rgba(59,130,246,0.1)',
          borderColor: iWon ? '#22c55e' : '#3b82f6',
        }}>
          <div style={styles.winnerEmoji}>{iWon ? '🎯' : '🤖'}</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: iWon ? '#22c55e' : '#3b82f6' }}>
              {iWon ? 'Your pick won!' : `Block ${winnerFlash.block_id} chosen`}
            </div>
            <div style={{ fontSize: 11, color: '#71717a', marginTop: 2 }}>
              {winnerFlash.voter_count} vote{winnerFlash.voter_count !== 1 ? 's' : ''}
            </div>
          </div>
        </div>
      )}

      {/* ── Rebellion override banner ── */}
      {override && (
        <div style={{
          ...styles.overrideBanner,
          borderColor: override.reason === 'agreed' ? '#22c55e' : '#ef4444',
          background: override.reason === 'agreed' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
        }}>
          <div style={styles.overrideIcon}>
            {override.reason === 'agreed' ? '🤝' : '🚫'}
          </div>
          <div>
            {override.reason === 'agreed' ? (
              <div style={{ fontSize: 13, fontWeight: 700, color: '#22c55e' }}>
                You agreed! Both chose Block {override.robot_choice}
              </div>
            ) : (
              <>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#ef4444' }}>
                  OVERRIDDEN
                </div>
                <div style={{ fontSize: 11, color: '#a1a1aa', marginTop: 2 }}>
                  You voted Block {override.crowd_choice} → ALICE chose Block {override.robot_choice}
                </div>
              </>
            )}
            <div style={{ fontSize: 9, color: '#52525b', marginTop: 3 }}>
              {override.crowd_votes} vote{override.crowd_votes !== 1 ? 's' : ''} ignored
            </div>
          </div>
        </div>
      )}

      {/* ── Robot action feedback ── */}
      {robotAction && (
        <div style={styles.actionBanner}>
          <span style={styles.actionDot} />
          Robot: {robotAction.action} block {robotAction.block_id}
        </div>
      )}

      {/* ── Block map ── */}
      <div style={styles.blockMapContainer}>
        {blocks.length === 0 ? (
          <div style={styles.emptyMap}>
            {connected
              ? (isInteractive ? 'Waiting for blocks...' : 'Watching...')
              : 'Connecting...'}
          </div>
        ) : (
          <svg viewBox="0 0 640 480" style={styles.blockSvg}>
            {/* Grid lines */}
            {[160, 320, 480].map(x => (
              <line key={`vl${x}`} x1={x} y1={0} x2={x} y2={480}
                stroke="#ffffff08" strokeWidth={1} />
            ))}
            {[160, 320].map(y => (
              <line key={`hl${y}`} x1={0} y1={y} x2={640} y2={y}
                stroke="#ffffff08" strokeWidth={1} />
            ))}

            {blocks.map((block) => {
              const cx = block.center_x;
              const cy = block.center_y;
              const id = block.block_id;
              const color = getBlockColor(id);
              const voteCount = votes[id] || 0;
              const isMyVote = myVote === id;
              const isLeading = leadingBlock === id;
              const isWinner = winnerFlash?.block_id === id;
              const canVote = isInteractive;

              // Scale circle by votes
              const baseR = 18;
              const r = baseR + Math.min(voteCount * 3, 15);

              return (
                <g key={id}
                   onClick={() => canVote && voteForBlock(id)}
                   style={{ cursor: canVote ? 'pointer' : 'default' }}>

                  {/* Vote ring */}
                  {voteCount > 0 && (
                    <circle cx={cx} cy={cy} r={r + 6}
                      fill="none" stroke={color} strokeWidth={2}
                      opacity={0.3}
                      strokeDasharray={`${(voteCount / Math.max(totalVotes, 1)) * 2 * Math.PI * (r + 6)} 999`}
                    />
                  )}

                  {/* Winner pulse */}
                  {isWinner && (
                    <circle cx={cx} cy={cy} r={r + 12}
                      fill="none" stroke="#22c55e" strokeWidth={2}
                      opacity={0.6}>
                      <animate attributeName="r" from={r + 8} to={r + 30}
                        dur="0.8s" repeatCount="3" />
                      <animate attributeName="opacity" from="0.6" to="0"
                        dur="0.8s" repeatCount="3" />
                    </circle>
                  )}

                  {/* Block circle */}
                  <circle cx={cx} cy={cy} r={r}
                    fill={`${color}30`}
                    stroke={isMyVote ? '#ffffff' : isLeading ? '#fbbf24' : color}
                    strokeWidth={isMyVote ? 3 : isLeading ? 2.5 : 1.5}
                  />

                  {/* Block ID */}
                  <text x={cx} y={cy + 1}
                    textAnchor="middle" dominantBaseline="central"
                    fill="#ffffff" fontSize={12} fontWeight={700}
                    fontFamily="monospace"
                    style={{ pointerEvents: 'none' }}>
                    {id}
                  </text>

                  {/* Vote count badge */}
                  {voteCount > 0 && (
                    <g>
                      <circle cx={cx + r * 0.7} cy={cy - r * 0.7} r={9}
                        fill={isLeading ? '#fbbf24' : '#3b82f6'} />
                      <text x={cx + r * 0.7} y={cy - r * 0.7 + 1}
                        textAnchor="middle" dominantBaseline="central"
                        fill="#000" fontSize={9} fontWeight={800}
                        fontFamily="monospace" style={{ pointerEvents: 'none' }}>
                        {voteCount}
                      </text>
                    </g>
                  )}

                  {/* "YOU" indicator */}
                  {isMyVote && (
                    <text x={cx} y={cy + r + 14}
                      textAnchor="middle" fill="#ffffff" fontSize={8}
                      fontWeight={600} fontFamily="monospace" letterSpacing="0.1em"
                      style={{ pointerEvents: 'none' }}>
                      YOUR PICK
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        )}

        {/* Tap hint overlay */}
        {isInteractive && blocks.length > 0 && !myVote && (
          <div style={{
            ...styles.tapHint,
            ...(sortState === 'rebellion' ? {
              background: '#ef444420', borderColor: '#ef444440', color: '#ef4444',
            } : {}),
          }}>
            {sortState === 'rebellion' ? 'VOTE — BUT ALICE DECIDES' : 'TAP A BLOCK TO VOTE'}
          </div>
        )}
      </div>

      {/* ── Desk Preset Voting ── */}
      {phase.label === 'Organize!' && (
        <div style={styles.presetSection}>
          <div style={styles.presetTitle}>Vote for a desk layout</div>
          <div style={styles.presetGrid}>
            {[
              { name: 'studying', display: 'Study', icon: '📚' },
              { name: 'drawing', display: 'Draw', icon: '🎨' },
              { name: 'working', display: 'Work', icon: '💻' },
              { name: 'clean', display: 'Clean', icon: '✨' },
            ].map(p => (
              <button
                key={p.name}
                onClick={() => voteForPreset(p.name)}
                style={{
                  ...styles.presetButton,
                  ...(myPresetVote === p.name ? styles.presetButtonActive : {}),
                }}
              >
                <span style={{ fontSize: 20 }}>{p.icon}</span>
                <span style={{ fontSize: 11, fontWeight: 600 }}>{p.display}</span>
                {presetVotes[p.name] > 0 && (
                  <span style={styles.presetVoteCount}>{presetVotes[p.name]}</span>
                )}
              </button>
            ))}
          </div>
          {presetResult && (
            <div style={{
              ...styles.presetResultBanner,
              borderColor: presetResult.accepted ? '#22c55e' : '#ef4444',
              background: presetResult.accepted ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
            }}>
              {presetResult.accepted
                ? `ALICE is organizing: ${presetResult.preset}`
                : `ALICE refused: ${presetResult.reason || 'she disagrees'}`}
            </div>
          )}
        </div>
      )}

      {/* ── Tilt section ── */}
      <div style={styles.tiltSection}>
        {!tiltEnabled ? (
          <button onClick={enableTilt} style={styles.tiltButton}>
            Enable Tilt Control
          </button>
        ) : (
          <div style={styles.tiltBar}>
            <div style={styles.tiltDot}>
              <div style={{
                ...styles.tiltIndicator,
                transform: `translate(${Math.max(-20, Math.min(20, tilt.gamma / 2))}px, ${Math.max(-20, Math.min(20, tilt.beta / 2))}px)`,
              }} />
            </div>
            <span style={styles.tiltLabel}>TILT ACTIVE</span>
          </div>
        )}
      </div>

      {/* ── Reactions ── */}
      <div style={styles.reactionBar}>
        {REACTIONS.map(emoji => (
          <button key={emoji}
            onClick={() => sendReaction(emoji)}
            style={styles.reactionButton}>
            {emoji}
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────

const styles = {
  page: {
    minHeight: '100dvh',
    background: '#09090b',
    color: '#e4e4e7',
    fontFamily: "'SF Mono', 'Fira Code', 'Consolas', monospace",
    display: 'flex',
    flexDirection: 'column',
    position: 'relative',
    overflow: 'hidden',
    userSelect: 'none',
    WebkitUserSelect: 'none',
    touchAction: 'manipulation',
  },

  // Header
  header: {
    padding: '12px 16px',
    borderBottom: '1px solid #ffffff0a',
    flexShrink: 0,
  },
  headerRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
  },
  logoMark: {
    width: 32, height: 32, borderRadius: 8,
    background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 16, fontWeight: 800, color: '#fff',
    flexShrink: 0,
  },
  headerInfo: { flex: 1 },
  phaseLabel: {
    fontSize: 14, fontWeight: 700, color: '#e4e4e7',
    textTransform: 'uppercase', letterSpacing: '0.05em',
  },
  phaseDesc: { fontSize: 11, color: '#71717a', marginTop: 1 },
  headerRight: {
    display: 'flex', alignItems: 'center', gap: 6,
  },
  connectionDot: {
    width: 8, height: 8, borderRadius: '50%',
    transition: 'all 0.3s',
  },
  audienceCount: {
    fontSize: 13, fontWeight: 600, color: '#a1a1aa',
    fontVariantNumeric: 'tabular-nums',
  },

  // Score bar
  scorebar: {
    display: 'flex', justifyContent: 'center', gap: 16,
    padding: '6px 16px',
    fontSize: 10, fontWeight: 700, color: '#71717a',
    textTransform: 'uppercase', letterSpacing: '0.1em',
    borderBottom: '1px solid #ffffff06',
    flexShrink: 0,
  },

  // Winner banner
  winnerBanner: {
    margin: '8px 16px', padding: '12px 16px',
    borderRadius: 10, border: '1px solid',
    display: 'flex', alignItems: 'center', gap: 12,
    animation: 'fadeInScale 0.3s ease',
    flexShrink: 0,
  },
  winnerEmoji: { fontSize: 28, flexShrink: 0 },

  // Override banner (rebellion)
  overrideBanner: {
    margin: '8px 16px', padding: '12px 16px',
    borderRadius: 10, border: '1px solid',
    display: 'flex', alignItems: 'center', gap: 12,
    animation: 'fadeInScale 0.3s ease',
    flexShrink: 0,
  },
  overrideIcon: { fontSize: 28, flexShrink: 0 },

  // Action banner
  actionBanner: {
    margin: '4px 16px', padding: '8px 12px',
    borderRadius: 6, background: '#3b82f610',
    border: '1px solid #3b82f630',
    fontSize: 11, color: '#3b82f6', fontWeight: 600,
    display: 'flex', alignItems: 'center', gap: 8,
    flexShrink: 0,
  },
  actionDot: {
    width: 6, height: 6, borderRadius: '50%',
    background: '#3b82f6', flexShrink: 0,
    animation: 'pulse 1s infinite',
  },

  // Block map
  blockMapContainer: {
    flex: 1, position: 'relative',
    margin: '0 8px', minHeight: 0,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  blockSvg: {
    width: '100%', maxHeight: '100%',
    borderRadius: 8, background: '#0c0c0f',
    border: '1px solid #ffffff08',
  },
  emptyMap: {
    fontSize: 13, color: '#52525b', textAlign: 'center',
    padding: 40,
  },
  tapHint: {
    position: 'absolute', bottom: 12, left: '50%',
    transform: 'translateX(-50%)',
    padding: '6px 16px', borderRadius: 20,
    background: '#3b82f620', border: '1px solid #3b82f640',
    fontSize: 10, fontWeight: 700, color: '#3b82f6',
    letterSpacing: '0.1em',
    animation: 'pulse 2s infinite',
  },

  // Tilt
  tiltSection: {
    padding: '8px 16px',
    flexShrink: 0,
  },
  tiltButton: {
    width: '100%', padding: '10px',
    border: '1px solid #27272a', borderRadius: 8,
    background: '#111113', color: '#71717a',
    fontSize: 11, fontWeight: 600, fontFamily: 'inherit',
    textTransform: 'uppercase', letterSpacing: '0.05em',
    cursor: 'pointer',
  },
  tiltBar: {
    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12,
  },
  tiltDot: {
    width: 44, height: 44, borderRadius: '50%',
    border: '1px solid #27272a', background: '#111113',
    position: 'relative', display: 'flex',
    alignItems: 'center', justifyContent: 'center',
  },
  tiltIndicator: {
    width: 10, height: 10, borderRadius: '50%',
    background: '#3b82f6', boxShadow: '0 0 8px #3b82f680',
    transition: 'transform 0.1s',
  },
  tiltLabel: {
    fontSize: 10, fontWeight: 600, color: '#3b82f6',
    letterSpacing: '0.1em',
  },

  // Reactions
  reactionBar: {
    display: 'flex', justifyContent: 'center', gap: 4,
    padding: '10px 16px',
    borderTop: '1px solid #ffffff06',
    flexShrink: 0,
  },
  reactionButton: {
    width: 44, height: 44, borderRadius: 10,
    border: '1px solid #ffffff0a', background: '#111113',
    fontSize: 20, cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    transition: 'transform 0.1s, background 0.1s',
    WebkitTapHighlightColor: 'transparent',
  },

  // Preset voting
  presetSection: {
    padding: '8px 16px',
    flexShrink: 0,
  },
  presetTitle: {
    fontSize: 10, fontWeight: 700, color: '#7c5cff',
    textTransform: 'uppercase', letterSpacing: '0.1em',
    textAlign: 'center', marginBottom: 8,
  },
  presetGrid: {
    display: 'grid', gridTemplateColumns: '1fr 1fr',
    gap: 8,
  },
  presetButton: {
    display: 'flex', flexDirection: 'column',
    alignItems: 'center', gap: 4,
    padding: '12px 8px', borderRadius: 10,
    border: '1px solid #ffffff0a', background: '#111116',
    color: '#a1a1aa', cursor: 'pointer',
    fontFamily: 'inherit',
    transition: 'all 0.15s ease',
    position: 'relative',
  },
  presetButtonActive: {
    borderColor: '#7c5cff40',
    background: 'rgba(124, 92, 255, 0.1)',
    color: '#e4e4e7',
    boxShadow: '0 0 12px rgba(124, 92, 255, 0.2)',
  },
  presetVoteCount: {
    position: 'absolute', top: 4, right: 6,
    background: '#7c5cff', color: '#fff',
    fontSize: 9, fontWeight: 800,
    width: 18, height: 18, borderRadius: '50%',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  presetResultBanner: {
    margin: '8px 0', padding: '8px 12px',
    borderRadius: 8, border: '1px solid',
    fontSize: 11, fontWeight: 600,
    textAlign: 'center',
    animation: 'fadeInScale 0.3s ease',
  },

  // Floating reactions
  floatingReaction: {
    position: 'absolute', bottom: 80,
    fontSize: 28, pointerEvents: 'none',
    animation: 'floatUp 2s ease-out forwards',
    zIndex: 100,
  },
};
