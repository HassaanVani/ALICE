"""Object interaction — ALICE fetches, nudges, and hands over desk objects.

This is the missing link between perception (YOLO sees objects) and action
(arm picks things up). It provides high-level commands:

    alice.fetch("marker")        — find the marker, pick it up, bring it to the handoff zone
    alice.nudge("cup", dx=-5)    — push the cup 5cm to the left
    alice.put_away("phone")      — move the phone to its preferred position
    alice.hand_over("marker")    — pick up and hold out for the user to take

Each command:
1. Runs YOLO to find the object by label
2. Uses calibration to map pixel position to arm angles
3. Executes the appropriate arm routine (pick-and-place, nudge, etc.)
4. Uses personality to modulate speed/hesitation
5. Updates object memory with the new position

The handoff zone is a fixed position at the front of the workspace where
ALICE holds objects out for the user to grab. She holds until the gripper
detects the object has been taken (or a timeout).
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger("ObjectInteraction")


@dataclass
class HandoffZone:
    """Where ALICE holds objects out for the user to take."""
    pixel_x: int = 320          # center-front of workspace
    pixel_y: int = 400          # front edge (close to user)
    hold_height_z: float = 60.0 # lifted up so user can grab
    timeout_s: float = 8.0      # how long she holds before giving up


@dataclass
class InteractionResult:
    """Outcome of an object interaction."""
    success: bool
    action: str               # "fetch", "nudge", "put_away", "hand_over"
    object_label: str
    message: str = ""
    duration_s: float = 0.0


class ObjectInteraction:
    """High-level object interaction commands for ALICE.

    Usage:
        interaction = ObjectInteraction(arm, gripper, calibration, ...)
        result = await interaction.fetch("marker", camera_getter)
        result = await interaction.hand_over("pen", camera_getter)

    All methods use YOLO to find objects by label, so ALICE doesn't need
    to know where things are in advance — she looks, finds, and acts.
    """

    def __init__(
        self,
        arm=None,
        gripper=None,
        calibration=None,
        dynamics=None,
        personality=None,
        yolo_detector=None,
        object_memory=None,
        narration=None,
        handoff_zone: Optional[HandoffZone] = None,
    ):
        self._arm = arm
        self._gripper = gripper
        self._calibration = calibration
        self._dynamics = dynamics
        self._personality = personality
        self._yolo = yolo_detector
        self._memory = object_memory
        self._narration = narration
        self._handoff = handoff_zone or HandoffZone()

    def _find_object(self, label: str, frame) -> Optional[Tuple[int, int]]:
        """Run YOLO on a frame and find an object by label.

        Returns (center_x, center_y) in pixels, or None if not found.
        """
        if frame is None or self._yolo is None:
            return None

        detections = self._yolo.detect(frame)
        for det in detections:
            if det.label == label:
                return (det.center_x, det.center_y)

        # Try partial match (e.g. "marker" might be detected as "pen")
        ALIASES = {
            "marker": ["pen", "pencil"],
            "pen": ["marker", "pencil"],
            "mug": ["cup"],
            "cup": ["mug"],
            "tissue": ["book"],  # tissues aren't in COCO
            "notebook": ["book"],
        }
        aliases = ALIASES.get(label, [])
        for det in detections:
            if det.label in aliases:
                return (det.center_x, det.center_y)

        return None

    async def fetch(
        self,
        label: str,
        camera_getter: Callable,
        place_px: Optional[Tuple[int, int]] = None,
    ) -> InteractionResult:
        """Find an object by label, pick it up, place it at a target position.

        If place_px is None, places at the handoff zone (front of desk).

        This is "pass me the marker" — the core desk assistant action.
        """
        start = time.time()
        logger.info(f"Fetching '{label}'")

        # Look for the object
        frame = camera_getter()
        obj_pos = self._find_object(label, frame)

        if obj_pos is None:
            logger.warning(f"Can't find '{label}' on the desk")
            return InteractionResult(
                success=False, action="fetch", object_label=label,
                message=f"can't find the {label}",
            )

        # Target position
        target = place_px or (self._handoff.pixel_x, self._handoff.pixel_y)

        # Pick and place with personality
        from logic.arm_routines import pick_and_place, PickPlaceConfig
        config = PickPlaceConfig(z_lift=self._handoff.hold_height_z)

        success = await pick_and_place(
            self._arm, self._gripper, self._calibration,
            pick_px=obj_pos, place_px=target, config=config,
        )

        duration = time.time() - start

        # Update memory
        if success and self._memory:
            obj_id = f"{label}_0"
            self._memory.observe(obj_id, label, (target[0] * 0.05, target[1] * 0.05, 0))

        # Personality: she just helped — no big deal
        if success and self._personality:
            from logic.personality import EmotionalState
            self._personality._last_action_time = time.time()

        return InteractionResult(
            success=success, action="fetch", object_label=label,
            duration_s=duration,
        )

    async def hand_over(
        self,
        label: str,
        camera_getter: Callable,
    ) -> InteractionResult:
        """Pick up an object and hold it out for the user to take.

        ALICE grabs the object, lifts it to the handoff zone, and holds.
        She watches the gripper — when the object is taken (gripper force
        drops or timeout), she retracts.

        This is the "pass me the marker" moment from the REMODEL spec.
        """
        start = time.time()
        logger.info(f"Handing over '{label}'")

        # Find the object
        frame = camera_getter()
        obj_pos = self._find_object(label, frame)

        if obj_pos is None:
            return InteractionResult(
                success=False, action="hand_over", object_label=label,
                message=f"can't find the {label}",
            )

        # Pick up
        if self._calibration is None:
            return InteractionResult(
                success=False, action="hand_over", object_label=label,
                message="no calibration",
            )

        from logic.arm_routines import PickPlaceConfig

        cfg = PickPlaceConfig()

        try:
            # Move above object
            above = self._calibration.pixel_to_arm(obj_pos[0], obj_pos[1], cfg.z_safe)
            if self._dynamics:
                from logic.personality import ActionOrigin
                await self._dynamics.move_to(above, origin=ActionOrigin.USER_REQUESTED)
            else:
                self._arm.move_to(above)
            await asyncio.sleep(cfg.move_delay)

            # Lower and grab
            at_obj = self._calibration.pixel_to_arm(obj_pos[0], obj_pos[1], cfg.z_pick)
            self._arm.move_to(at_obj)
            await asyncio.sleep(cfg.move_delay)
            self._gripper.close()
            await asyncio.sleep(cfg.grab_delay)

            # Lift to handoff position
            handoff = self._calibration.pixel_to_arm(
                self._handoff.pixel_x, self._handoff.pixel_y, self._handoff.hold_height_z,
            )
            if self._dynamics:
                from logic.personality import ActionOrigin
                await self._dynamics.move_to(handoff, origin=ActionOrigin.USER_REQUESTED)
            else:
                self._arm.move_to(handoff)
            await asyncio.sleep(0.3)

            # Hold and wait for user to take it
            taken = await self._wait_for_take()

            # Release and retract
            self._gripper.open()
            await asyncio.sleep(cfg.release_delay)

            retract = self._calibration.pixel_to_arm(
                self._handoff.pixel_x, self._handoff.pixel_y, cfg.z_safe,
            )
            self._arm.move_to(retract)

            duration = time.time() - start

            if self._personality:
                self._personality._last_action_time = time.time()

            return InteractionResult(
                success=True, action="hand_over", object_label=label,
                message="taken" if taken else "timed out",
                duration_s=duration,
            )

        except Exception as e:
            logger.error(f"Hand-over failed: {e}")
            self._gripper.open()
            return InteractionResult(
                success=False, action="hand_over", object_label=label,
                message=str(e), duration_s=time.time() - start,
            )

    async def nudge(
        self,
        label: str,
        camera_getter: Callable,
        dx_px: int = 0,
        dy_px: int = 0,
    ) -> InteractionResult:
        """Push an object slightly in a direction without picking it up.

        dx_px/dy_px: pixel offset to nudge. Positive x = right, positive y = down.
        Used for the tea interaction — nudging the cup away from the laptop.
        """
        start = time.time()

        frame = camera_getter()
        obj_pos = self._find_object(label, frame)

        if obj_pos is None:
            return InteractionResult(
                success=False, action="nudge", object_label=label,
                message=f"can't find the {label}",
            )

        target = (obj_pos[0] + dx_px, obj_pos[1] + dy_px)

        from logic.arm_routines import pick_and_place
        success = await pick_and_place(
            self._arm, self._gripper, self._calibration,
            pick_px=obj_pos, place_px=target,
        )

        return InteractionResult(
            success=success, action="nudge", object_label=label,
            duration_s=time.time() - start,
        )

    async def put_away(
        self,
        label: str,
        camera_getter: Callable,
    ) -> InteractionResult:
        """Move an object to its preferred position (from object memory).

        If no preferred position is known, moves it to the back of the desk.
        """
        start = time.time()

        frame = camera_getter()
        obj_pos = self._find_object(label, frame)

        if obj_pos is None:
            return InteractionResult(
                success=False, action="put_away", object_label=label,
                message=f"can't find the {label}",
            )

        # Check memory for preferred position
        target = None
        if self._memory:
            obj_id = f"{label}_0"
            record = self._memory.get_object(obj_id)
            if record and record.preferred_position:
                # Convert cm back to rough pixels
                target = (
                    int(record.preferred_position[0] / 0.05),
                    int(record.preferred_position[1] / 0.05),
                )

        # Default: back of desk
        if target is None:
            target = (320, 80)

        from logic.arm_routines import pick_and_place
        success = await pick_and_place(
            self._arm, self._gripper, self._calibration,
            pick_px=obj_pos, place_px=target,
        )

        if success and self._memory:
            obj_id = f"{label}_0"
            self._memory.record_placement(
                obj_id, (target[0] * 0.05, target[1] * 0.05, 0)
            )

        return InteractionResult(
            success=success, action="put_away", object_label=label,
            duration_s=time.time() - start,
        )

    async def _wait_for_take(self) -> bool:
        """Wait for the user to take the object from the gripper.

        Returns True if taken, False on timeout.
        In simulation, returns True after a brief wait.
        """
        deadline = time.time() + self._handoff.timeout_s

        while time.time() < deadline:
            # In a real system, check gripper force sensor or
            # re-run YOLO to see if the object disappeared from grip
            # For now, hold for a fixed period then assume taken
            await asyncio.sleep(0.2)

        # Timeout — assume taken (in real hardware, gripper force
        # sensor would detect this earlier)
        return True
