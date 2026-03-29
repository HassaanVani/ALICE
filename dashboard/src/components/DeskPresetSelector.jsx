import React from 'react';

const PRESETS = [
  { name: 'studying', display: 'Study', desc: 'Books center, phone aside' },
  { name: 'drawing', display: 'Draw', desc: 'Sketchbook center, tools out' },
  { name: 'working', display: 'Work', desc: 'Laptop center, phone left' },
  { name: 'clean', display: 'Clean', desc: 'Everything to edges' },
];

export default function DeskPresetSelector({ activePreset, presetVotes, onSelectPreset }) {
  const votes = presetVotes || {};

  return (
    <div className="preset-grid">
      {PRESETS.map((p) => (
        <div
          key={p.name}
          className={`preset-card ${activePreset === p.name ? 'active' : ''}`}
          onClick={() => onSelectPreset && onSelectPreset(p.name)}
        >
          <div className="preset-name">{p.display}</div>
          <div className="preset-votes">
            {votes[p.name] ? `${votes[p.name]} vote${votes[p.name] !== 1 ? 's' : ''}` : p.desc}
          </div>
        </div>
      ))}
    </div>
  );
}
