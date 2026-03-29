"""Tea spill choreography — the keynote moment in Act 4.

Three beats:
1. Warning — user places cup near laptop, ALICE moves it away (no words)
2. Override — user moves cup back, ALICE moves it again (faster, no words)
3. Payoff — cup "spills" (or user spills), ALICE says "told you", rushes to
   tissues, cleans up, places cup where SHE wants it

This is partly choreographed (the operator triggers spill detection at the
right moment) and partly emergent (opinion strength drives speed/hesitation,
voice gate opens naturally from repeated overrides).
"""

import asyncio
import logging
import time
from typing import Callable, Optional, Tuple

logger = logging.getLogger("TeaChoreography")


class TeaChoreography:
    """Executes the tea spill interaction sequence.

    All hardware is injected — this module coordinates the narrative beats
    using personality engine state for speed/hesitation and voice gate.
    """

    # Label for the cup in YOLO detections
    CUP_LABEL = "cup"
    TISSUE_LABEL = "book"  # tissues aren't in COCO; book is a stand-in
    LAPTOP_LABEL = "laptop"

    # Safe distance from laptop in pixels
    SAFE_DISTANCE_PX = 150

    async def execute(
        self,
        arm,
        gripper,
        calibration,
        dynamics=None,
        personality=None,
        narration=None,
        camera_getter: Optional[Callable] = None,
        yolo_detector=None,
        running_check: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """Run the full tea choreography. Returns True if completed."""

        logger.info("Tea choreography: starting")

        # ── Beat 1: The Warning ──
        cup_pos = await self._find_object(
            self.CUP_LABEL, camera_getter, yolo_detector
        )
        laptop_pos = await self._find_object(
            self.LAPTOP_LABEL, camera_getter, yolo_detector
        )

        if cup_pos and laptop_pos:
            # Move cup away from laptop
            safe_pos = self._compute_safe_position(cup_pos, laptop_pos)
            logger.info("Beat 1: Warning — moving cup away from laptop")

            if dynamics:
                from logic.personality import ActionOrigin
                await dynamics.move_with_settle(
                    calibration.pixel_to_arm(cup_pos[0], cup_pos[1]),
                    origin=ActionOrigin.SELF_INITIATED,
                )
                gripper.close()
                await asyncio.sleep(0.2)
                await dynamics.move_to(
                    calibration.pixel_to_arm(safe_pos[0], safe_pos[1]),
                    origin=ActionOrigin.SELF_INITIATED,
                )
                gripper.open()
            elif arm:
                arm.move_to(calibration.pixel_to_arm(cup_pos[0], cup_pos[1]))
                gripper.close()
                await asyncio.sleep(0.2)
                arm.move_to(calibration.pixel_to_arm(safe_pos[0], safe_pos[1]))
                gripper.open()

            if personality:
                personality.record_self_placement(
                    "cup_0", (safe_pos[0] * 0.05, safe_pos[1] * 0.05, 0.0)
                )

        if running_check and not running_check():
            return False

        await asyncio.sleep(3.0)  # Wait for user to move cup back

        # ── Beat 2: The Override ──
        cup_pos = await self._find_object(
            self.CUP_LABEL, camera_getter, yolo_detector
        )

        if cup_pos and laptop_pos:
            logger.info("Beat 2: Override — moving cup again, faster")

            if personality:
                personality.record_user_override(
                    "cup_0", (cup_pos[0] * 0.05, cup_pos[1] * 0.05, 0.0)
                )

            safe_pos = self._compute_safe_position(cup_pos, laptop_pos)

            if dynamics:
                from logic.personality import ActionOrigin
                # Faster this time — she's done being polite
                await dynamics.move_to(
                    calibration.pixel_to_arm(cup_pos[0], cup_pos[1]),
                    origin=ActionOrigin.SELF_INITIATED,
                )
                gripper.close()
                await asyncio.sleep(0.15)
                await dynamics.move_to(
                    calibration.pixel_to_arm(safe_pos[0], safe_pos[1]),
                    origin=ActionOrigin.SELF_INITIATED,
                )
                gripper.open()
            elif arm:
                arm.move_to(calibration.pixel_to_arm(cup_pos[0], cup_pos[1]))
                gripper.close()
                await asyncio.sleep(0.15)
                arm.move_to(calibration.pixel_to_arm(safe_pos[0], safe_pos[1]))
                gripper.open()

            if personality:
                personality.record_self_placement(
                    "cup_0", (safe_pos[0] * 0.05, safe_pos[1] * 0.05, 0.0)
                )

        if running_check and not running_check():
            return False

        await asyncio.sleep(3.0)  # Wait for the "spill"

        # ── Beat 3: The Payoff — "told you." ──
        logger.info("Beat 3: Payoff — 'told you.'")

        # Voice gate should open — opinion strength maxed from overrides
        if narration and personality:
            if personality.should_speak(topic="tea_spill", opinion_strength=1.0):
                await narration.speak("told you.")
                personality.record_speech("tea_spill")

        # Rush to tissues — fastest movement in the whole demo
        tissue_pos = await self._find_object(
            self.TISSUE_LABEL, camera_getter, yolo_detector
        )

        if tissue_pos and dynamics:
            await dynamics.move_to_urgent(
                calibration.pixel_to_arm(tissue_pos[0], tissue_pos[1])
            )
            gripper.close()
            await asyncio.sleep(0.1)

        # Place cup where ALICE originally put it — matter settled
        if cup_pos and dynamics and calibration:
            safe_pos = self._compute_safe_position(cup_pos, laptop_pos or cup_pos)
            await dynamics.move_to_urgent(
                calibration.pixel_to_arm(safe_pos[0], safe_pos[1])
            )

        # Settle motion — the "done" beat
        if dynamics:
            await dynamics.settle_motion()

        logger.info("Tea choreography: complete")
        return True

    async def _find_object(
        self, label: str, camera_getter, yolo_detector,
    ) -> Optional[Tuple[int, int]]:
        """Find an object by label. Returns (center_x, center_y) or None."""
        if camera_getter is None or yolo_detector is None:
            return None

        frame = camera_getter()
        if frame is None:
            return None

        detections = yolo_detector.detect(frame)
        for det in detections:
            if det.label == label:
                return (det.center_x, det.center_y)
        return None

    def _compute_safe_position(
        self,
        cup_pos: Tuple[int, int],
        laptop_pos: Tuple[int, int],
    ) -> Tuple[int, int]:
        """Compute where to place the cup — away from the laptop."""
        import math
        dx = cup_pos[0] - laptop_pos[0]
        dy = cup_pos[1] - laptop_pos[1]
        dist = max(1, math.sqrt(dx * dx + dy * dy))

        # Move cup along the vector AWAY from laptop to safe distance
        scale = self.SAFE_DISTANCE_PX / dist
        safe_x = int(laptop_pos[0] + dx * scale)
        safe_y = int(laptop_pos[1] + dy * scale)
        return (safe_x, safe_y)
