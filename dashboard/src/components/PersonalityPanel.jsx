import React from 'react';

const EMOTION_LABELS = {
  content: 'Content',
  curious: 'Curious',
  annoyed: 'Annoyed',
  focused: 'Focused',
  reluctant: 'Reluctant',
  satisfied: 'Satisfied',
};

function moodColor(mood) {
  if (mood > 0.7) return '#34d399';
  if (mood > 0.4) return '#7c5cff';
  return '#f87171';
}

export default function PersonalityPanel({ state }) {
  const mood = state.personality_mood ?? 0.5;
  const emotion = state.personality_emotion ?? 'content';
  const streak = state.personality_override_streak ?? 0;
  const inFlow = state.personality_is_in_flow ?? false;
  const idleBehavior = state.personality_idle_behavior ?? 'watch';

  const voiceGateOpen = mood < 0.35 || streak >= 3;

  return (
    <div className="personality-panel">
      {/* Emotional State */}
      <div className="personality-row">
        <span className="label">Emotion</span>
        <span className={`emotion-badge ${emotion}`}>
          {EMOTION_LABELS[emotion] || emotion}
        </span>
      </div>

      {/* Mood Meter */}
      <div className="personality-row">
        <span className="label">Mood</span>
        <span className="value" style={{ fontSize: 9, color: moodColor(mood) }}>
          {(mood * 100).toFixed(0)}%
        </span>
      </div>
      <div className="mood-meter">
        <div
          className="mood-meter-fill"
          style={{ width: `${mood * 100}%`, background: moodColor(mood) }}
        />
      </div>

      {/* Override Streak */}
      {streak > 0 && (
        <div className="personality-row">
          <span className="label">Overrides</span>
          <span className="value" style={{ color: streak >= 3 ? 'var(--danger)' : 'var(--warning)' }}>
            {streak}x
          </span>
        </div>
      )}

      {/* Voice Gate */}
      <div className="voice-gate">
        <div className={`gate-dot ${voiceGateOpen ? 'open' : ''}`} />
        <span>voice gate {voiceGateOpen ? 'open' : 'closed'}</span>
      </div>

      {/* Idle Behavior / Flow */}
      <div className="personality-row">
        <span className="label">Activity</span>
        <span className="value" style={{ fontSize: 9 }}>
          {inFlow ? 'in flow' : idleBehavior}
        </span>
      </div>
    </div>
  );
}
