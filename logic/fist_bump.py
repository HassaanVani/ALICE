"""Fist bump interaction — ALICE responds to a fist bump gesture.

When presence detection sees a fist-shaped gesture close to the arm camera,
ALICE extends her arm to meet it. A fun personality beat that shows she's
approachable and aware.
"""

import asyncio
import logging
from typing import Optional, Tuple

logger = logging.getLogger("FistBump")

# Arm angles for the "fist bump" extension position
FIST_BUMP_ANGLES = (90, 50, 110, 90)  # arm extended forward, mid-height
RETRACT_ANGLES = (90, 80, 80, 90)      # default rest position


class FistBumpInteraction:
    """Detects and responds to a fist bump gesture.

    The gesture is detected as a person's hand close to the arm camera
    (large bounding box in YOLO with "person" class, or a specific hand
    region in the front camera).

    For now, this is trigger-based: call `trigger()` from a mode runner
    when conditions are met.
    """

    def __init__(self, cooldown_s: float = 10.0):
        self._cooldown = cooldown_s
        self._last_bump_time: float = 0.0

    async def trigger(
        self,
        arm,
        dynamics=None,
        personality=None,
        bump_angles: Tuple[float, ...] = FIST_BUMP_ANGLES,
        retract_angles: Tuple[float, ...] = RETRACT_ANGLES,
    ) -> bool:
        """Execute the fist bump: extend → hold → retract.

        Returns True if the bump was performed (not on cooldown).
        """
        import time
        now = time.time()
        if now - self._last_bump_time < self._cooldown:
            return False

        self._last_bump_time = now
        logger.info("Fist bump!")

        if dynamics:
            from logic.personality import ActionOrigin
            # Quick, enthusiastic movement — she wants to do this
            await dynamics.move_to(bump_angles, origin=ActionOrigin.SELF_INITIATED)
        elif arm:
            arm.move_to(bump_angles, speed=70)

        # Hold for the bump moment
        await asyncio.sleep(0.8)

        # Retract with a little settle
        if dynamics:
            await dynamics.settle_motion()
            await dynamics.move_to(retract_angles, origin=ActionOrigin.SELF_INITIATED)
        elif arm:
            arm.move_to(retract_angles, speed=40)

        if personality:
            from logic.personality import EmotionalState
            personality._state.emotional_state = EmotionalState.SATISFIED
            personality._state.overall_mood = min(1.0, personality._state.overall_mood + 0.1)

        return True

    def should_trigger(self, presence_info=None) -> bool:
        """Heuristic: should we attempt a fist bump?

        Returns True if someone is very close and looking at the desk.
        """
        import time
        if time.time() - self._last_bump_time < self._cooldown:
            return False

        if presence_info is None:
            return False

        return (
            presence_info.detected
            and presence_info.closest_distance < 40.0  # very close
            and presence_info.looking_at_desk
        )
