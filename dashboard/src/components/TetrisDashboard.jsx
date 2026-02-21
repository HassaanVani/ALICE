import React from 'react';

const CELL_SIZE = 16;
const BOARD_COLS = 10;
const BOARD_ROWS = 20;

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
  boardContainer: {
    display: 'flex',
    justifyContent: 'center',
    padding: '8px 0',
  },
  board: {
    display: 'grid',
    gridTemplateColumns: `repeat(${BOARD_COLS}, ${CELL_SIZE}px)`,
    gridTemplateRows: `repeat(${BOARD_ROWS}, ${CELL_SIZE}px)`,
    gap: 1,
    background: '#18181b',
    border: '1px solid #27272a',
    borderRadius: 4,
    padding: 2,
  },
  gameOver: {
    color: '#ef4444',
    fontSize: 12,
    fontWeight: 700,
    textTransform: 'uppercase',
    textAlign: 'center',
    padding: '6px 0',
    background: '#7f1d1d22',
    border: '1px solid #7f1d1d',
    borderRadius: 4,
  },
};

const PIECE_COLORS = {
  1: '#06b6d4',
  2: '#eab308',
  3: '#a855f7',
  4: '#22c55e',
  5: '#ef4444',
  6: '#3b82f6',
  7: '#f97316',
};

function Cell({ value }) {
  const filled = value !== 0;
  const color = PIECE_COLORS[value] || '#06b6d4';
  return (
    <div style={{
      width: CELL_SIZE,
      height: CELL_SIZE,
      background: filled ? color : '#0a0a0c',
      borderRadius: 2,
      boxShadow: filled ? `0 0 4px ${color}55` : 'none',
    }} />
  );
}

export default function TetrisDashboard({ state }) {
  if (state.mode !== 'auto_tetris') return null;

  const board = state.tetris_board || [];
  const score = state.tetris_score || 0;
  const lines = state.tetris_lines || 0;
  const level = state.tetris_level || 1;
  const gameOver = state.tetris_game_over || false;

  return (
    <div style={styles.container}>
      <div style={styles.sectionTitle}>Tetris</div>

      {/* Game Over */}
      {gameOver && (
        <div style={styles.gameOver}>Game Over</div>
      )}

      {/* Stats */}
      <div style={styles.row}>
        <span style={styles.label}>Score</span>
        <span style={{ ...styles.value, color: '#22d3ee' }}>{score.toLocaleString()}</span>
      </div>
      <div style={styles.row}>
        <span style={styles.label}>Lines</span>
        <span style={styles.value}>{lines}</span>
      </div>
      <div style={styles.row}>
        <span style={styles.label}>Level</span>
        <span style={styles.value}>{level}</span>
      </div>

      {/* Board Grid */}
      {board.length > 0 && (
        <div style={styles.boardContainer}>
          <div style={styles.board}>
            {board.flat().map((cell, i) => (
              <Cell key={i} value={cell} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
