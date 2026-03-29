"""Fist bump interaction — ALICE sees a fist and responds.

Uses the HandGestureDetector to detect a closed fist offered toward the arm.
When confident the gesture is a fist bump offer (stable fist, held for >0.4s,
positioned toward the desk), ALICE extends her arm to meet it.

The response is personality-driven:
- If ALICE is content or satisfied, she responds quickly and enthusiastically
- If she's annoyed (been overridden a lot), she still responds but with a delay
- After a bump, her mood lifts — it's a positive social interaction
- She gets a brief SATISFIED emotional state

The arm aims toward the detected fist position rather than a fixed angle,
so the bump feels like ALICE is actually meeting the person's hand.
"""

import asyncio
import logging
import math
import time
from typing import Callable, Optional, Tuple

logger = logging.getLogger("FistBump")

# Default arm angles for various bump positions
# These are overridden by position-aware targeting when CV is active
BUMP_CENTER = (90, 50, 110, 90)
BUMP_LEFT = (120, 50, 110, 90)
BUMP_RIGHT = (60, 50, 110, 90)
RETRACT_ANGLES = (90, 80, 80, 90)


class FistBumpInteraction:
    """Detects and responds to fist bump gestures using computer vision.

    Integrates with:
    - HandGestureDetector for CV-based fist detection
    - PersonalityEngine for emotional response modulation
    - MovementDynamics for personality-driven arm movement
    - StateManager for dashboard updates

    Args:
        cooldown_s: Minimum seconds between fist bumps.
        offer_confidence_threshold: Minimum FistBumpCandidate.offer_confidence to respond.
        hold_required_s: How long the fist must be held before ALICE responds.
    """

    def __init__(
        self,
        cooldown_s: float = 8.0,
        offer_confidence_threshold: float = 0.7,
        hold_required_s: float = 0.4,
    ):
        self._cooldown = cooldown_s
        self._offer_threshold = offer_confidence_threshold
        self._hold_required = hold_required_s
        self._last_bump_time: float = 0.0
        self._bump_count: int = 0
        self._hand_detector = None

    @property
    def bump_count(self) -> int:
        return self._bump_count

    @property
    def on_cooldown(self) -> bool:
        return time.time() - self._last_bump_time < self._cooldown

    # --- Detection ---

    def get_or_create_detector(self):
        """Lazy-init the hand gesture detector."""
        if self._hand_detector is None:
            from vision.hand_detector import HandGestureDetector
            self._hand_detector = HandGestureDetector(
                max_hands=2,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.5,
            )
            self._hand_detector.start()
        return self._hand_detector

    def check_for_fist_bump(self, frame) -> Optional[dict]:
        """Run CV detection on a camera frame.

        Returns a dict with bump info if a fist bump is detected, None otherwise.
        The dict contains: position (normalized), pixel coords, confidence,
        hold duration, and suggested arm angles.
        """
        if self.on_cooldown:
            return None

        if frame is None:
            return None

        detector = self.get_or_create_detector()
        candidate = detector.detect_fist_bump(frame)

        if candidate is None:
            return None

        if candidate.offer_confidence < self._offer_threshold:
            return None

        if candidate.hold_duration < self._hold_required:
            return None

        if not candidate.is_ready:
            return None

        # Compute arm angles based on hand position in frame
        target_angles = self._compute_target_angles(
            candidate.hand.center_x,
            candidate.hand.center_y,
        )

        return {
            "center_x": candidate.hand.center_x,
            "center_y": candidate.hand.center_y,
            "pixel_x": candidate.hand.pixel_x,
            "pixel_y": candidate.hand.pixel_y,
            "confidence": candidate.offer_confidence,
            "hold_duration": candidate.hold_duration,
            "handedness": candidate.hand.handedness,
            "target_angles": target_angles,
        }

    def _compute_target_angles(self, norm_x: float, norm_y: float) -> Tuple[float, ...]:
        """Convert normalized hand position to arm joint angles.

        Maps the fist's position in the camera frame to arm angles that
        point ALICE's end-effector toward where the fist is.

        norm_x: 0=left, 0.5=center, 1=right in camera frame
        norm_y: 0=top, 1=bottom
        """
        # Map x position to base rotation (j1)
        # Camera left (x=0) → arm rotates right (higher j1), and vice versa
        # Center of frame (x=0.5) → j1=90 (straight ahead)
        j1 = 90 + (0.5 - norm_x) * 80  # range: ~50° to ~130°
        j1 = max(50, min(130, j1))

        # Map y position to shoulder angle (j2) — lower in frame = extend more
        j2 = 65 - (norm_y - 0.5) * 30  # range: ~50° to ~80°
        j2 = max(45, min(80, j2))

        # Elbow stays relatively fixed for bump gesture
        j3 = 110

        # Wrist neutral
        j4 = 90

        return (j1, j2, j3, j4)

    # --- Response ---

    async def respond(
        self,
        bump_info: dict,
        arm=None,
        dynamics=None,
        personality=None,
        narration=None,
        state_manager=None,
    ) -> bool:
        """Execute the fist bump response: orient → extend → hold → retract.

        Uses personality to modulate the response:
        - Speed reflects current emotional state
        - Brief hesitation if ALICE is annoyed (but she still does it)
        - Mood boost after the bump

        Returns True if the bump was performed.
        """
        if self.on_cooldown:
            return False

        now = time.time()
        self._last_bump_time = now
        self._bump_count += 1

        target = bump_info["target_angles"]
        logger.info(
            f"Fist bump #{self._bump_count}! "
            f"conf={bump_info['confidence']:.0%} "
            f"hand={bump_info['handedness']} "
            f"target=({target[0]:.0f}, {target[1]:.0f}, {target[2]:.0f}, {target[3]:.0f})"
        )

        # Personality-driven pre-bump hesitation
        if personality is not None:
            from logic.personality import ActionOrigin, EmotionalState

            # If she's annoyed, brief pause — but she'll still do it
            if personality.emotional_state == EmotionalState.ANNOYED:
                await asyncio.sleep(0.4)
            elif personality.emotional_state == EmotionalState.RELUCTANT:
                await asyncio.sleep(0.2)

            # Shift to curious — someone is engaging with her
            personality._state.emotional_state = EmotionalState.CURIOUS

        # Broadcast state
        if state_manager is not None:
            state_manager.update_arm(target, "fist_bump")

        # Phase 1: Orient toward the fist (quick, eager)
        if dynamics is not None:
            from logic.personality import ActionOrigin
            await dynamics.move_to(
                target, speed=75, origin=ActionOrigin.SELF_INITIATED,
            )
        elif arm is not None:
            arm.move_to(target, speed=75)

        # Phase 2: Hold — the bump moment
        # Slightly longer hold if this is a repeat bump (she's warming up)
        hold_time = 0.6 if self._bump_count <= 1 else 0.8
        await asyncio.sleep(hold_time)

        # Phase 3: Retract with settle — she enjoyed that
        if dynamics is not None:
            await dynamics.settle_motion()
            from logic.personality import ActionOrigin
            await dynamics.move_to(
                RETRACT_ANGLES, origin=ActionOrigin.SELF_INITIATED,
            )
        elif arm is not None:
            arm.move_to(RETRACT_ANGLES, speed=40)

        # Phase 4: Personality update — mood boost
        if personality is not None:
            from logic.personality import EmotionalState
            personality._state.emotional_state = EmotionalState.SATISFIED
            personality._state.overall_mood = min(
                1.0, personality._state.overall_mood + 0.15
            )
            personality._last_action_time = time.time()
            # Reset override streak — positive interaction clears frustration
            if personality._state.override_streak > 0:
                personality._state.override_streak = max(
                    0, personality._state.override_streak - 1
                )
            logger.debug(
                f"Post-bump mood: {personality._state.overall_mood:.2f}, "
                f"state: {personality._state.emotional_state.value}"
            )

        # Rare: if she's bumped 3+ times in a session, she might comment
        if narration is not None and personality is not None and self._bump_count >= 3:
            if personality.should_speak(topic="fist_bump"):
                await narration.speak("okay, we're friends now.")
                personality.record_speech("fist_bump")

        return True

    # --- Convenience: detect + respond in one call ---

    async def check_and_respond(
        self,
        frame,
        arm=None,
        dynamics=None,
        personality=None,
        narration=None,
        state_manager=None,
    ) -> bool:
        """One-shot: check frame for fist bump, respond if detected.

        Designed to be called from the idle loop every tick.
        Returns True if a bump was performed.
        """
        bump_info = self.check_for_fist_bump(frame)
        if bump_info is None:
            return False

        return await self.respond(
            bump_info,
            arm=arm,
            dynamics=dynamics,
            personality=personality,
            narration=narration,
            state_manager=state_manager,
        )

    # --- Legacy compatibility ---

    def should_trigger(self, presence_info=None) -> bool:
        """Quick check if conditions are right for fist bump detection.

        This is a pre-filter before running the expensive CV detection.
        Returns True if someone is close enough to potentially offer a bump.
        """
        if self.on_cooldown:
            return False

        if presence_info is None:
            return False

        return (
            presence_info.detected
            and presence_info.closest_distance < 50.0
            and presence_info.looking_at_desk
        )

    async def trigger(
        self,
        arm,
        dynamics=None,
        personality=None,
        bump_angles: Tuple[float, ...] = BUMP_CENTER,
        retract_angles: Tuple[float, ...] = RETRACT_ANGLES,
    ) -> bool:
        """Legacy trigger: execute a fist bump at fixed angles.

        Use check_and_respond() instead for CV-based detection.
        """
        if self.on_cooldown:
            return False

        bump_info = {
            "center_x": 0.5,
            "center_y": 0.5,
            "pixel_x": 0,
            "pixel_y": 0,
            "confidence": 1.0,
            "hold_duration": 1.0,
            "handedness": "Right",
            "target_angles": bump_angles,
        }

        return await self.respond(
            bump_info, arm=arm, dynamics=dynamics, personality=personality,
        )

    def shutdown(self) -> None:
        """Release hand detector resources."""
        if self._hand_detector is not None:
            self._hand_detector.stop()
            self._hand_detector = None
