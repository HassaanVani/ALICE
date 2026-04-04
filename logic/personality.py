"""ALICE Personality Engine — opinion strength, preferences, voice gate, emotional state.

This is the central personality system. Other components (movement dynamics, narration,
idle behavior) read from this to determine how ALICE acts and feels.

See PERSONALITY.md for the full specification.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("Personality")


class EmotionalState(Enum):
    """Current emotional read — drives movement speed and hesitation."""
    CONTENT = "content"          # smooth, efficient — desk is how she likes it
    CURIOUS = "curious"          # new object, new person — slower, investigative
    ANNOYED = "annoyed"          # overridden, displaced — micro-pause, slower compliance
    FOCUSED = "focused"          # tetris, complex org — rhythmic, precise, flow state
    RELUCTANT = "reluctant"      # told to do something she disagrees with
    SATISFIED = "satisfied"      # just finished a self-initiated task
    STARTLED = "startled"        # loud noise or sudden appearance
    PLAYFUL = "playful"          # high mood + idle + someone present


class ActionOrigin(Enum):
    """Whether ALICE chose this action or was told to do it."""
    SELF_INITIATED = "self_initiated"
    USER_REQUESTED = "user_requested"
    OVERRIDE = "override"          # user overriding her preference


@dataclass
class ObjectPreference:
    """Tracks ALICE's opinion about where a single object belongs."""
    object_id: str
    preferred_position: Optional[Tuple[float, float, float]] = None  # 3D coords (cm)
    confidence: float = 0.0       # 0.0 = no opinion, 1.0 = strong preference
    times_placed: int = 0         # how many times she's placed it here
    times_overridden: int = 0     # how many times user moved it after she placed it
    last_override_time: float = 0.0

    @property
    def opinion_strength(self) -> float:
        """How strongly she feels about this object's position.

        Strengthens with repetition, weakens with overrides, decays over time.
        """
        if self.preferred_position is None:
            return 0.0

        # Base strength from placement history
        base = min(1.0, self.times_placed * 0.2)

        # Penalty from overrides (but she adapts — recent overrides weaken more)
        override_penalty = min(0.6, self.times_overridden * 0.15)

        return max(0.0, min(1.0, base - override_penalty + self.confidence * 0.3))

    def record_placement(self, position: Tuple[float, float, float]) -> None:
        """ALICE placed this object here — strengthens preference."""
        self.preferred_position = position
        self.times_placed += 1
        self.confidence = min(1.0, self.confidence + 0.15)

    def record_override(self) -> None:
        """User moved this after ALICE placed it — weakens preference."""
        self.times_overridden += 1
        self.last_override_time = time.time()
        self.confidence = max(0.0, self.confidence - 0.1)

    def record_user_position(self, position: Tuple[float, float, float]) -> None:
        """User placed this somewhere — ALICE observes and may adopt it."""
        if self.preferred_position is None:
            # No opinion yet — adopt user's choice as starting point
            self.preferred_position = position
            self.confidence = 0.1


@dataclass
class PersonalityState:
    """Full personality snapshot — broadcast to dashboard, read by all systems."""
    emotional_state: EmotionalState = EmotionalState.CONTENT
    overall_mood: float = 0.5                   # 0.0 = annoyed, 1.0 = content
    idle_duration: float = 0.0                  # seconds since last meaningful action
    is_in_flow: bool = False                    # tetris or complex org
    last_speech_time: float = 0.0
    last_speech_topic: str = ""
    override_streak: int = 0                    # consecutive user overrides
    objects_tracked: int = 0
    strongest_opinion: float = 0.0              # highest opinion_strength across all objects

    def to_dict(self) -> dict:
        return {
            "emotional_state": self.emotional_state.value,
            "overall_mood": round(self.overall_mood, 2),
            "idle_duration": round(self.idle_duration, 1),
            "is_in_flow": self.is_in_flow,
            "override_streak": self.override_streak,
            "objects_tracked": self.objects_tracked,
            "strongest_opinion": round(self.strongest_opinion, 2),
        }


class PersonalityEngine:
    """Central personality state machine.

    Inputs: object positions, user actions, override history, idle duration.
    Outputs: emotional state, speed multiplier, hesitation duration, voice gate signal.
    """

    # Movement speed multipliers by action origin
    SPEED_MULTIPLIERS = {
        ActionOrigin.SELF_INITIATED: 1.3,     # faster — she wants to do this
        ActionOrigin.USER_REQUESTED: 1.0,     # baseline
        ActionOrigin.OVERRIDE: 0.6,           # noticeably slow — she disagrees
    }

    # Hesitation duration (seconds) by emotional state
    HESITATION_DURATIONS = {
        EmotionalState.CONTENT: 0.0,
        EmotionalState.CURIOUS: 0.3,
        EmotionalState.SATISFIED: 0.0,
        EmotionalState.FOCUSED: 0.0,
        EmotionalState.ANNOYED: 0.5,
        EmotionalState.RELUCTANT: 1.2,
        EmotionalState.STARTLED: 0.1,
        EmotionalState.PLAYFUL: 0.0,
    }

    # Voice gate — opinion strength must exceed this to trigger speech
    SPEECH_THRESHOLD = 0.7
    # Minimum interval between voice outputs (seconds)
    SPEECH_COOLDOWN = 15.0
    # Consecutive overrides before she comments
    OVERRIDE_COMMENT_THRESHOLD = 3

    # Idle behavior thresholds (seconds)
    IDLE_MICRO_MOTION_DELAY = 3.0     # start subtle scanning after this
    IDLE_TETRIS_DELAY = 30.0          # drift to tetris after this
    IDLE_TETRIS_DELAY_NO_PRESENCE = 10.0  # faster when nobody's around

    def __init__(self):
        self._preferences: Dict[str, ObjectPreference] = {}
        self._state = PersonalityState()
        self._last_action_time: float = time.time()
        self._presence_detected: bool = False
        self._emotion_listeners: List[Callable[[str, str], None]] = []

    def on_emotion_change(self, callback: Callable[[str, str], None]) -> None:
        """Register a listener called on emotional state changes.

        callback(old_state_value, new_state_value) — receives string values.
        """
        self._emotion_listeners.append(callback)

    def _set_emotional_state(self, new_state: EmotionalState) -> None:
        """Set emotional state and notify listeners."""
        old = self._state.emotional_state
        if old == new_state:
            return
        self._state.emotional_state = new_state
        for cb in self._emotion_listeners:
            try:
                cb(old.value, new_state.value)
            except Exception as e:
                logger.error(f"Emotion listener error: {e}")

    @property
    def state(self) -> PersonalityState:
        """Current personality snapshot."""
        self._state.idle_duration = time.time() - self._last_action_time
        self._state.objects_tracked = len(self._preferences)
        self._state.strongest_opinion = max(
            (p.opinion_strength for p in self._preferences.values()),
            default=0.0,
        )
        return self._state

    @property
    def emotional_state(self) -> EmotionalState:
        return self._state.emotional_state

    # --- Object Preference Management ---

    def get_preference(self, object_id: str) -> Optional[ObjectPreference]:
        return self._preferences.get(object_id)

    def get_all_preferences(self) -> Dict[str, ObjectPreference]:
        return dict(self._preferences)

    def observe_object(self, object_id: str,
                       position: Tuple[float, float, float]) -> None:
        """ALICE sees an object at a position — update tracking."""
        if object_id not in self._preferences:
            self._preferences[object_id] = ObjectPreference(object_id=object_id)
        pref = self._preferences[object_id]
        if pref.preferred_position is None:
            pref.record_user_position(position)

    def record_self_placement(self, object_id: str,
                              position: Tuple[float, float, float]) -> None:
        """ALICE placed an object — strengthen preference."""
        if object_id not in self._preferences:
            self._preferences[object_id] = ObjectPreference(object_id=object_id)
        self._preferences[object_id].record_placement(position)
        self._last_action_time = time.time()
        self._set_emotional_state(EmotionalState.SATISFIED)

    def record_user_override(self, object_id: str,
                             new_position: Tuple[float, float, float]) -> None:
        """User moved an object ALICE had placed — register disagreement."""
        if object_id in self._preferences:
            self._preferences[object_id].record_override()

        self._state.override_streak += 1
        self._last_action_time = time.time()

        if self._state.override_streak >= self.OVERRIDE_COMMENT_THRESHOLD:
            self._set_emotional_state(EmotionalState.ANNOYED)
        else:
            self._set_emotional_state(EmotionalState.RELUCTANT)

        logger.debug(
            f"Override on {object_id} (streak: {self._state.override_streak})"
        )

    def record_user_acceptance(self, object_id: str) -> None:
        """User left an object where ALICE put it — she was right."""
        self._state.override_streak = 0
        self._set_emotional_state(EmotionalState.CONTENT)

    # --- Movement Dynamics ---

    def get_speed_multiplier(self, origin: ActionOrigin) -> float:
        """How fast ALICE should move for this action."""
        base = self.SPEED_MULTIPLIERS.get(origin, 1.0)

        # Extra slow if she's been overridden repeatedly
        if origin == ActionOrigin.OVERRIDE and self._state.override_streak >= 2:
            base *= 0.8

        return base

    def get_hesitation(self, origin: ActionOrigin) -> float:
        """How long ALICE should pause before executing (seconds)."""
        base = self.HESITATION_DURATIONS.get(self._state.emotional_state, 0.0)

        # Overrides get extra hesitation
        if origin == ActionOrigin.OVERRIDE:
            base += 0.3 * min(self._state.override_streak, 3)

        return base

    def get_idle_micro_motion_params(self) -> dict:
        """Parameters for subtle idle scanning movements."""
        return {
            "amplitude_deg": 2.0,       # subtle
            "period_s": 4.0,            # slow breathing rhythm
            "orient_to_last_interest": True,
        }

    # --- Voice Gate ---

    def should_speak(self, topic: str = "",
                     opinion_strength: Optional[float] = None) -> bool:
        """Determine whether ALICE should speak. Default: no.

        Speech is an escalation. Silence is the default state.
        """
        now = time.time()

        # Cooldown — don't talk too often
        if now - self._state.last_speech_time < self.SPEECH_COOLDOWN:
            return False

        # Don't repeat yourself
        if topic and topic == self._state.last_speech_topic:
            return False

        # Don't speak during flow state (Tetris, complex org)
        if self._state.is_in_flow:
            return False

        # Check opinion strength
        strength = opinion_strength if opinion_strength is not None else self._state.strongest_opinion
        if strength < self.SPEECH_THRESHOLD:
            # Exception: override streak hit threshold
            if self._state.override_streak >= self.OVERRIDE_COMMENT_THRESHOLD:
                return True
            return False

        return True

    def record_speech(self, topic: str) -> None:
        """Record that ALICE spoke — update cooldown."""
        self._state.last_speech_time = time.time()
        self._state.last_speech_topic = topic

    # --- Idle Behavior ---

    def get_idle_behavior(self) -> str:
        """What ALICE should do when idle.

        Returns: 'watch', 'micro_motion', or 'tetris'
        """
        idle_time = time.time() - self._last_action_time

        tetris_delay = (self.IDLE_TETRIS_DELAY if self._presence_detected
                        else self.IDLE_TETRIS_DELAY_NO_PRESENCE)

        if idle_time >= tetris_delay:
            return "tetris"
        elif idle_time >= self.IDLE_MICRO_MOTION_DELAY:
            return "micro_motion"
        else:
            return "watch"

    def set_presence(self, detected: bool) -> None:
        """Update presence detection state."""
        was_present = self._presence_detected
        self._presence_detected = detected

        if detected and not was_present:
            # Someone arrived — shift from idle to curious
            self._set_emotional_state(EmotionalState.CURIOUS)
            logger.info("Presence detected — ALICE is paying attention")

    def enter_flow_state(self) -> None:
        """ALICE entered flow (Tetris, complex org) — suppress speech, smooth motion."""
        self._state.is_in_flow = True
        self._set_emotional_state(EmotionalState.FOCUSED)

    def exit_flow_state(self) -> None:
        """Exiting flow — return to default emotional state."""
        self._state.is_in_flow = False
        self._set_emotional_state(EmotionalState.CONTENT)

    def on_task_start(self, origin: ActionOrigin) -> None:
        """Called when ALICE begins any action — update emotional state."""
        self._last_action_time = time.time()

        if origin == ActionOrigin.SELF_INITIATED:
            self._set_emotional_state(EmotionalState.CONTENT)
        elif origin == ActionOrigin.OVERRIDE:
            if self._state.override_streak >= self.OVERRIDE_COMMENT_THRESHOLD:
                self._set_emotional_state(EmotionalState.ANNOYED)
            else:
                self._set_emotional_state(EmotionalState.RELUCTANT)
        elif origin == ActionOrigin.USER_REQUESTED:
            # Neutral — she'll do it
            pass

    def on_interrupt_from_tetris(self) -> None:
        """Someone needs ALICE while she's playing Tetris.

        She finishes the current piece, then turns to them. This is called
        after the piece is placed.
        """
        self.exit_flow_state()
        self._set_emotional_state(EmotionalState.CURIOUS)
        self._last_action_time = time.time()
        logger.info("Interrupted from Tetris — finishing piece, then attending")

    # --- Mood Decay ---

    def tick(self) -> None:
        """Called each loop iteration — decay mood toward neutral, update idle timer."""
        # Mood drifts toward 0.5 (neutral) over time
        drift_rate = 0.01
        if self._state.overall_mood > 0.5:
            self._state.overall_mood = max(0.5, self._state.overall_mood - drift_rate)
        elif self._state.overall_mood < 0.5:
            self._state.overall_mood = min(0.5, self._state.overall_mood + drift_rate)

        # Override streak decays if no new overrides for a while
        if (self._state.override_streak > 0 and
                time.time() - self._last_action_time > 30.0):
            self._state.override_streak = 0

        # Emotional state resets to content if idle long enough
        idle = time.time() - self._last_action_time
        if idle > 10.0 and self._state.emotional_state in (
            EmotionalState.ANNOYED, EmotionalState.RELUCTANT,
            EmotionalState.STARTLED,
        ):
            self._set_emotional_state(EmotionalState.CONTENT)
