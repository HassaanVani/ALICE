"""Body language — emotional posture overlays expressed through arm position.

ALICE's internal emotional state becomes visible through small, additive joint
angle offsets. A droop when scolded, a perk when praised, a lean when curious.
These overlays blend smoothly and layer on top of whatever the arm is doing.

The arm IS the face. Every offset is a micro-expression.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("BodyLanguage")


@dataclass
class PostureOverlay:
    """An additive joint angle offset that expresses emotion."""
    name: str = ""
    j1_offset: float = 0.0   # base rotation
    j2_offset: float = 0.0   # shoulder (up = perk, down = droop)
    j3_offset: float = 0.0   # elbow (extend = reach, retract = shrink)
    j4_offset: float = 0.0   # wrist tilt
    blend_in_s: float = 0.5  # seconds to reach full strength
    hold_s: float = 1.0      # seconds at full strength before decay starts
    decay_s: float = 2.0     # seconds to fade out after hold


@dataclass
class _ActiveOverlay:
    """Runtime state for a currently blending overlay."""
    overlay: PostureOverlay
    start_time: float
    strength: float = 0.0    # 0.0 → 1.0 → 0.0 over lifecycle


# Posture definitions — small offsets that read as emotion
POSTURES: Dict[str, PostureOverlay] = {
    "droop": PostureOverlay(
        name="droop",
        j2_offset=-6.0, j3_offset=-3.0,
        blend_in_s=0.8, hold_s=3.0, decay_s=4.0,
    ),
    "perk_up": PostureOverlay(
        name="perk_up",
        j2_offset=5.0, j3_offset=2.0,
        blend_in_s=0.2, hold_s=2.0, decay_s=2.5,
    ),
    "bounce": PostureOverlay(
        name="bounce",
        j2_offset=4.0,
        blend_in_s=0.1, hold_s=0.15, decay_s=0.4,
    ),
    "shrink_back": PostureOverlay(
        name="shrink_back",
        j2_offset=-3.0, j3_offset=-6.0,
        blend_in_s=0.15, hold_s=1.5, decay_s=2.0,
    ),
    "lean_in": PostureOverlay(
        name="lean_in",
        j2_offset=2.0, j3_offset=4.0,
        blend_in_s=0.4, hold_s=2.5, decay_s=2.0,
    ),
    "settle": PostureOverlay(
        name="settle",
        j2_offset=-1.5,
        blend_in_s=0.6, hold_s=0.5, decay_s=1.0,
    ),
    "attentive": PostureOverlay(
        name="attentive",
        j2_offset=3.0, j4_offset=2.0,
        blend_in_s=0.3, hold_s=4.0, decay_s=3.0,
    ),
    "recoil": PostureOverlay(
        name="recoil",
        j1_offset=-3.0, j2_offset=-5.0, j3_offset=-4.0,
        blend_in_s=0.1, hold_s=0.8, decay_s=1.5,
    ),
}

# Emotion → posture mapping
_EMOTION_POSTURE = {
    "content": None,
    "curious": "lean_in",
    "annoyed": "droop",
    "focused": None,
    "reluctant": "shrink_back",
    "satisfied": "settle",
    "startled": "recoil",
    "playful": "bounce",
}

# Voice sentiment → posture mapping
_SENTIMENT_POSTURE = {
    "praise": "perk_up",
    "scold": "droop",
    "question": "attentive",
    "neutral": None,
}


class BodyLanguage:
    """Maps emotional states and voice sentiment to arm posture overlays.

    Overlays are additive offsets blended smoothly over time. Multiple can
    be active simultaneously — they sum together. The result is applied
    by MovementDynamics on top of every arm movement.

    Usage:
        bl = BodyLanguage()
        bl.on_emotion_change("content", "curious")
        offset = bl.get_current_offset()  # (j1, j2, j3, j4) to add to target
    """

    MAX_ACTIVE = 3  # limit simultaneous overlays to prevent jitter

    def __init__(self):
        self._active: List[_ActiveOverlay] = []
        self._enabled = True
        self._llm_interpreter = None

    def set_llm_interpreter(self, interp) -> None:
        """Attach LLM interpreter for dynamic posture strength modulation."""
        self._llm_interpreter = interp

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if not enabled:
            self._active.clear()

    def _trigger(self, posture_name: str) -> None:
        """Activate a named posture overlay."""
        if not self._enabled:
            return

        posture = POSTURES.get(posture_name)
        if posture is None:
            return

        # Don't stack the same posture
        self._active = [a for a in self._active if a.overlay.name != posture_name]

        # Evict oldest if at capacity
        while len(self._active) >= self.MAX_ACTIVE:
            self._active.pop(0)

        self._active.append(_ActiveOverlay(
            overlay=posture,
            start_time=time.time(),
            strength=0.1,  # immediately detectable, tick() will refine
        ))
        logger.debug(f"Posture triggered: {posture_name}")

    def on_emotion_change(self, old_state: str, new_state: str) -> None:
        """Called when personality emotional state changes."""
        posture_name = _EMOTION_POSTURE.get(new_state)
        if posture_name is not None:
            self._trigger(posture_name)

    def on_voice_sentiment(self, sentiment: str, confidence: float = 1.0) -> None:
        """Called when voice input detects praise/scold/question sentiment."""
        if confidence < 0.4:
            return
        posture_name = _SENTIMENT_POSTURE.get(sentiment)
        if posture_name is not None:
            self._trigger(posture_name)

    def on_event(self, event: str) -> None:
        """Trigger posture from discrete events."""
        event_map = {
            "startle": "recoil",
            "new_person": "attentive",
            "task_complete": "settle",
            "bump_reciprocated": "bounce",
            "override": "shrink_back",
            "examination_start": "lean_in",
        }
        posture_name = event_map.get(event)
        if posture_name is not None:
            self._trigger(posture_name)

    def tick(self, dt: float) -> None:
        """Update overlay strengths. Call each loop iteration.

        Args:
            dt: seconds since last tick.
        """
        now = time.time()
        still_active = []

        for active in self._active:
            ov = active.overlay
            elapsed = now - active.start_time
            total = ov.blend_in_s + ov.hold_s + ov.decay_s

            if elapsed >= total:
                continue  # fully decayed, drop it

            # Calculate strength based on lifecycle phase
            if elapsed < ov.blend_in_s:
                # Blending in
                active.strength = elapsed / ov.blend_in_s if ov.blend_in_s > 0 else 1.0
            elif elapsed < ov.blend_in_s + ov.hold_s:
                # Holding at full
                active.strength = 1.0
            else:
                # Decaying
                decay_elapsed = elapsed - ov.blend_in_s - ov.hold_s
                active.strength = 1.0 - (decay_elapsed / ov.decay_s if ov.decay_s > 0 else 1.0)

            active.strength = max(0.0, min(1.0, active.strength))
            still_active.append(active)

        self._active = still_active

    def get_current_offset(self) -> Tuple[float, float, float, float]:
        """Return the blended (j1, j2, j3, j4) offset to add to arm targets."""
        if not self._enabled or not self._active:
            return (0.0, 0.0, 0.0, 0.0)

        j1 = j2 = j3 = j4 = 0.0
        for active in self._active:
            s = active.strength
            j1 += active.overlay.j1_offset * s
            j2 += active.overlay.j2_offset * s
            j3 += active.overlay.j3_offset * s
            j4 += active.overlay.j4_offset * s

        # LLM modulation of posture strength
        if self._llm_interpreter is not None:
            m = self._llm_interpreter.modifiers.pos
            j1, j2, j3, j4 = j1 * m, j2 * m, j3 * m, j4 * m

        # Clamp total offset to prevent wild swings
        max_offset = 10.0
        j1 = max(-max_offset, min(max_offset, j1))
        j2 = max(-max_offset, min(max_offset, j2))
        j3 = max(-max_offset, min(max_offset, j3))
        j4 = max(-max_offset, min(max_offset, j4))

        return (j1, j2, j3, j4)

    @property
    def current_posture_name(self) -> str:
        """Name of the strongest active posture, or empty string."""
        if not self._active:
            return ""
        strongest = max(self._active, key=lambda a: a.strength)
        return strongest.overlay.name if strongest.strength > 0.05 else ""

    @property
    def active_count(self) -> int:
        return len(self._active)
