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
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("ObjectInteraction")

# Label aliases: maps common names to COCO YOLO labels
LABEL_ALIASES: Dict[str, List[str]] = {
    "marker": ["pen", "pencil"],
    "pen": ["marker", "pencil"],
    "pencil": ["pen", "marker"],
    "mug": ["cup"],
    "cup": ["mug"],
    "tissue": ["book"],
    "tissues": ["book"],
    "notebook": ["book"],
    "phone": ["cell phone"],
    "cell phone": ["phone"],
    "wrapper": ["tissue", "napkin"],
    "napkin": ["tissue"],
}

# Objects ALICE considers trash — she'll auto-clean these when in the mood
TRASH_ELIGIBLE: set = {
    "tissue", "tissues", "napkin", "wrapper",
}

# How often ALICE can auto-clean (seconds)
AUTO_CLEANUP_COOLDOWN = 60.0


@dataclass
class HandoffZone:
    """Where ALICE holds objects out for the user to take."""
    pixel_x: int = 320          # center-front of workspace
    pixel_y: int = 400          # front edge (close to user)
    hold_height_z: float = 60.0 # lifted up so user can grab
    timeout_s: float = 8.0      # how long she holds before giving up


@dataclass
class TrashZone:
    """Where ALICE discards objects — a physical bin or desk region."""
    pixel_x: int = 50           # center of trash zone
    pixel_y: int = 50           # top-left corner of desk (away from user)
    enabled: bool = False
    detect_label: Optional[str] = None  # YOLO label for auto-detecting a bin


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
        trash_zone: Optional[TrashZone] = None,
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
        self._trash = trash_zone or TrashZone()
        self._busy = asyncio.Lock()

        # Last successful move — for undo
        self._last_move: Optional[Dict] = None  # {"pick": (x,y), "place": (x,y), "label": str}

        # Custom object store — for objects YOLO can't recognize
        self._custom_objects = None

    async def _pick_and_place(self, pick_px, place_px, label: str,
                              config=None) -> bool:
        """Run pick_and_place and record the move for undo."""
        from logic.arm_routines import pick_and_place
        success = await pick_and_place(
            self._arm, self._gripper, self._calibration,
            pick_px=pick_px, place_px=place_px, config=config,
        )
        if success:
            self._last_move = {
                "pick": pick_px,
                "place": place_px,
                "label": label,
            }
        return success

    async def undo(self) -> InteractionResult:
        """Reverse the last successful move — swap pick and place."""
        if self._last_move is None:
            return InteractionResult(
                success=False, action="undo", object_label="",
                message="nothing to undo",
            )
        pick = self._last_move["place"]   # object is now at the place position
        place = self._last_move["pick"]   # move it back to where it was
        label = self._last_move["label"]

        from logic.arm_routines import pick_and_place
        success = await pick_and_place(
            self._arm, self._gripper, self._calibration,
            pick_px=pick, place_px=place,
        )
        if success:
            self._last_move = None  # can't undo an undo
        return InteractionResult(
            success=success, action="undo", object_label=label,
            message=f"moved {label} back" if success else f"undo failed",
        )

    def _detect_all(self, frame) -> list:
        """Run YOLO once and return all detections."""
        if frame is None or self._yolo is None:
            return []
        return self._yolo.detect(frame)

    def _match_label(self, label: str, detections: list):
        """Find a detection matching label (with alias support).

        Returns the Detection object, or None.
        """
        # Exact match
        for det in detections:
            if det.label == label:
                return det

        # Alias match
        aliases = LABEL_ALIASES.get(label, [])
        for det in detections:
            if det.label in aliases:
                return det

        return None

    def set_custom_objects(self, store) -> None:
        """Attach the custom object store for registered objects."""
        self._custom_objects = store

    def _find_object(self, label: str, frame) -> Optional[Tuple[int, int]]:
        """Run YOLO on a frame and find an object by label.

        Falls back to custom object store if YOLO doesn't recognize it.
        Returns (center_x, center_y) in pixels, or None if not found.
        """
        # Try YOLO first
        detections = self._detect_all(frame)
        det = self._match_label(label, detections)
        if det:
            return (det.center_x, det.center_y)

        # Fall back to custom registered objects
        if self._custom_objects is not None and frame is not None:
            match = self._custom_objects.find(label, frame)
            if match:
                cx, cy, conf = match
                logger.debug(f"Custom object '{label}' found at ({cx}, {cy}) conf={conf:.2f}")
                return (cx, cy)

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
        from logic.arm_routines import PickPlaceConfig
        config = PickPlaceConfig(z_lift=self._handoff.hold_height_z)

        success = await self._pick_and_place(obj_pos, target, label, config=config)

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

        success = await self._pick_and_place(obj_pos, target, label)

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

        success = await self._pick_and_place(obj_pos, target, label)

        if success and self._memory:
            obj_id = f"{label}_0"
            self._memory.record_placement(
                obj_id, (target[0] * 0.05, target[1] * 0.05, 0)
            )

        return InteractionResult(
            success=success, action="put_away", object_label=label,
            duration_s=time.time() - start,
        )

    async def move_near(
        self,
        source_label: str,
        target_label: str,
        camera_getter: Callable,
        offset_px: int = 80,
    ) -> InteractionResult:
        """Move source object near target object.

        Finds both objects in one YOLO frame, computes a smart placement
        position near the target (on the side with most free space), and
        executes pick-and-place.

        "Move the cup near my laptop" → move_near("cup", "laptop")
        """
        start = time.time()
        logger.info(f"Moving '{source_label}' near '{target_label}'")

        frame = camera_getter()
        detections = self._detect_all(frame)

        source = self._match_label(source_label, detections)
        target = self._match_label(target_label, detections)

        if source is None:
            return InteractionResult(
                success=False, action="move_near",
                object_label=f"{source_label} near {target_label}",
                message=f"can't find the {source_label}",
            )
        if target is None:
            return InteractionResult(
                success=False, action="move_near",
                object_label=f"{source_label} near {target_label}",
                message=f"can't find the {target_label}",
            )

        # Smart placement: pick the side of target with most free space
        place_pos = self._compute_placement_near(target, detections, source, offset_px)

        success = await self._pick_and_place(
            (source.center_x, source.center_y), place_pos, source_label,
        )

        if success and self._memory:
            obj_id = f"{source_label}_0"
            self._memory.observe(
                obj_id, source_label,
                (place_pos[0] * 0.05, place_pos[1] * 0.05, 0),
            )

        return InteractionResult(
            success=success, action="move_near",
            object_label=f"{source_label} near {target_label}",
            duration_s=time.time() - start,
        )

    def _compute_placement_near(self, target_det, all_detections: list,
                                 source_det, offset_px: int) -> Tuple[int, int]:
        """Find the best position near target_det with most free space.

        Evaluates 4 candidates (right, left, below, above the target bbox edge)
        and picks the one farthest from other objects.
        """
        tx, ty = target_det.center_x, target_det.center_y
        # Use bbox half-dimensions for edge offset
        hw = target_det.width // 2 if hasattr(target_det, 'width') else 40
        hh = target_det.height // 2 if hasattr(target_det, 'height') else 40

        candidates = [
            (tx + hw + offset_px, ty),          # right
            (tx - hw - offset_px, ty),          # left
            (tx, ty + hh + offset_px),          # below
            (tx, ty - hh - offset_px),          # above
        ]

        # Exclude source from obstacle list
        obstacles = [
            (d.center_x, d.center_y)
            for d in all_detections
            if d is not source_det and d is not target_det
        ]

        best = candidates[0]
        best_score = -1

        for cx, cy in candidates:
            # Penalize out-of-frame (assume 640x480)
            if cx < 30 or cx > 610 or cy < 30 or cy > 450:
                continue

            # Score = minimum distance to any obstacle (higher = more free space)
            if obstacles:
                min_dist = min(
                    ((cx - ox) ** 2 + (cy - oy) ** 2) ** 0.5
                    for ox, oy in obstacles
                )
            else:
                min_dist = 999

            if min_dist > best_score:
                best_score = min_dist
                best = (cx, cy)

        return (int(best[0]), int(best[1]))

    async def throw_away(
        self,
        label: str,
        camera_getter: Callable,
    ) -> InteractionResult:
        """Pick up an object and place it in the trash zone.

        "Throw away the wrapper" → find it, pick it up, place in trash zone.
        If a trash bin is detected by YOLO, targets it. Otherwise uses the
        configured pixel region.
        """
        start = time.time()
        logger.info(f"Throwing away '{label}'")

        if not self._trash.enabled:
            return InteractionResult(
                success=False, action="throw_away", object_label=label,
                message="trash zone not configured",
            )

        frame = camera_getter()
        obj_pos = self._find_object(label, frame)

        if obj_pos is None:
            return InteractionResult(
                success=False, action="throw_away", object_label=label,
                message=f"can't find the {label}",
            )

        # Determine trash target
        trash_target = (self._trash.pixel_x, self._trash.pixel_y)

        # If a bin label is configured, try to find it via YOLO
        if self._trash.detect_label:
            detections = self._detect_all(frame)
            bin_det = self._match_label(self._trash.detect_label, detections)
            if bin_det:
                trash_target = (bin_det.center_x, bin_det.center_y)

        success = await self._pick_and_place(obj_pos, trash_target, label)

        # Forget from memory — it's been discarded
        if success and self._memory:
            obj_id = f"{label}_0"
            self._memory.forget(obj_id)

        return InteractionResult(
            success=success, action="throw_away", object_label=label,
            duration_s=time.time() - start,
        )

    # --- Autonomous cleanup ---

    def scan_for_trash(self, camera_getter: Callable) -> List[str]:
        """Look at the desk and return labels of trash-eligible objects.

        ALICE glances at the desk and notices things that don't belong.
        Returns a list of YOLO labels that match TRASH_ELIGIBLE.
        """
        frame = camera_getter() if camera_getter else None
        if frame is None:
            return []
        detections = self._detect_all(frame)
        found = []
        for det in detections:
            if det.label in TRASH_ELIGIBLE:
                found.append(det.label)
            else:
                # Check aliases
                for trash_label in TRASH_ELIGIBLE:
                    aliases = LABEL_ALIASES.get(trash_label, [])
                    if det.label in aliases:
                        found.append(det.label)
                        break
        return found

    def should_auto_cleanup(self, personality=None,
                             last_cleanup_time: float = 0.0) -> bool:
        """Decide whether ALICE should autonomously clean up right now.

        She cleans when:
        - Trash zone is enabled
        - She's not on cleanup cooldown
        - Her mood is decent (> 0.4) — she won't clean when annoyed
        - She's been idle for a bit (> 5s) — she's not mid-task
        - She's not in flow state (Tetris)
        - Random chance weighted by mood — higher mood = more proactive

        She's more likely to clean:
        - When she's CONTENT or SATISFIED (she likes things tidy)
        - After someone leaves (desk is "hers" again)
        - When mood is high (she has the energy)
        """
        import random

        if not self._trash.enabled:
            return False

        if time.time() - last_cleanup_time < AUTO_CLEANUP_COOLDOWN:
            return False

        if personality is None:
            return False

        from logic.personality import EmotionalState

        # Don't clean when upset or focused
        if personality.emotional_state in (
            EmotionalState.ANNOYED, EmotionalState.RELUCTANT,
        ):
            return False

        if personality._state.is_in_flow:
            return False

        # Need some idle time — she's not mid-task
        idle_time = time.time() - personality._last_action_time
        if idle_time < 5.0:
            return False

        mood = personality._state.overall_mood

        # Don't bother if mood is too low
        if mood < 0.4:
            return False

        # Higher mood = higher chance. At mood 0.7, ~5% per tick.
        # At 100ms ticks, that's roughly once per 2 seconds.
        chance = (mood - 0.3) * 0.12
        return random.random() < chance

    async def auto_cleanup(
        self,
        camera_getter: Callable,
        personality=None,
        narration=None,
    ) -> InteractionResult:
        """Autonomously scan for and throw away trash-eligible objects.

        ALICE looks at the desk, finds things that don't belong, and
        throws them away one at a time. This is a self-initiated action —
        she moves faster and with more confidence than when told to clean.

        Personality effects:
        - She moves at SELF_INITIATED speed (1.3x — she wants to do this)
        - After cleaning: mood boost, SATISFIED state
        - If trash keeps reappearing: she may comment ("again?")
        - She gets a small mood boost per item cleaned
        """
        start = time.time()
        trash_labels = self.scan_for_trash(camera_getter)

        if not trash_labels:
            return InteractionResult(
                success=True, action="auto_cleanup", object_label="",
                message="desk is clean",
            )

        logger.info(f"Auto-cleanup: found {len(trash_labels)} item(s) to toss: {trash_labels}")

        # Personality: she's taking initiative
        if personality:
            from logic.personality import ActionOrigin, EmotionalState
            personality.on_task_start(ActionOrigin.SELF_INITIATED)

        cleaned = 0
        for label in trash_labels:
            result = await self.throw_away(label, camera_getter)
            if result.success:
                cleaned += 1

                # Small mood boost per item
                if personality:
                    personality._state.overall_mood = min(
                        1.0, personality._state.overall_mood + 0.05,
                    )

        # Post-cleanup personality
        if personality and cleaned > 0:
            from logic.personality import EmotionalState
            personality._state.emotional_state = EmotionalState.SATISFIED
            personality._last_action_time = time.time()

        # She might comment
        if narration and personality and cleaned > 0:
            if personality.should_speak(topic="auto_cleanup"):
                if cleaned >= 3:
                    await narration.speak("this desk was a mess.")
                    personality.record_speech("auto_cleanup")
                elif cleaned >= 1:
                    await narration.speak("better.")
                    personality.record_speech("auto_cleanup")

        return InteractionResult(
            success=cleaned > 0, action="auto_cleanup",
            object_label=f"{cleaned} items",
            message=f"cleaned {cleaned}/{len(trash_labels)}",
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
