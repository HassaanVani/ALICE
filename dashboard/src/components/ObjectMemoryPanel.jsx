import React from 'react';

const CATEGORY_COLORS = {
  drinkware: 'var(--cat-drinkware)',
  stationery: 'var(--cat-stationery)',
  electronics: 'var(--cat-electronics)',
  personal: 'var(--cat-personal)',
  tool: 'var(--cat-tool)',
  unknown: 'var(--text-dim)',
};

const LABEL_CATEGORY = {
  cup: 'drinkware', bottle: 'drinkware', bowl: 'drinkware',
  book: 'stationery', scissors: 'stationery',
  laptop: 'electronics', mouse: 'electronics', keyboard: 'electronics',
  'cell phone': 'electronics', remote: 'electronics',
  clock: 'personal', vase: 'personal', 'teddy bear': 'personal',
  fork: 'tool', knife: 'tool', spoon: 'tool',
};

function getCategoryColor(label) {
  const cat = LABEL_CATEGORY[label] || 'unknown';
  return CATEGORY_COLORS[cat] || CATEGORY_COLORS.unknown;
}

export default function ObjectMemoryPanel({ objects }) {
  if (!objects || objects.length === 0) {
    return (
      <div style={{ fontSize: 10, color: 'var(--text-dim)', textAlign: 'center', padding: 12 }}>
        No objects in memory
      </div>
    );
  }

  return (
    <div className="object-memory-list">
      {objects.map((obj) => (
        <div key={obj.object_id} className="object-memory-item">
          <div className="obj-dot" style={{ background: getCategoryColor(obj.label) }} />
          <span className="obj-label">{obj.label}</span>
          {obj.is_new && <span className="obj-badge new">new</span>}
          {obj.has_moved && <span className="obj-badge moved">moved</span>}
          <div className="obj-confidence">
            <div
              className="obj-confidence-fill"
              style={{ width: `${(obj.confidence || 0) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
