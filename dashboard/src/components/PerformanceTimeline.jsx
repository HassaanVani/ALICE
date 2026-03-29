import React from 'react';

const ACTS = [
  { num: 1, label: "She's Already Here" },
  { num: 2, label: 'She Knows This Desk' },
  { num: 3, label: 'She Helps' },
  { num: 4, label: 'She Has Opinions' },
  { num: 5, label: 'She Engages' },
  { num: 6, label: 'This Is Her' },
];

export default function PerformanceTimeline({ currentAct, visible }) {
  if (!visible) return null;

  return (
    <div className="performance-timeline">
      {ACTS.map((act) => {
        let status = '';
        if (act.num < currentAct) status = 'completed';
        else if (act.num === currentAct) status = 'active';

        return (
          <div key={act.num} className={`timeline-act ${status}`}>
            <div className="act-num">{act.num}</div>
            <span>{act.label}</span>
          </div>
        );
      })}
    </div>
  );
}
