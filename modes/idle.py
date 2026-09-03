"""Idle mode — ALICE watches, wanders, and explores her desk with curiosity.

She's never fully still when awake. Subtle scanning movements show awareness.
When curious about desk items, she leans in, attempts to pick up small objects
to inspect them, nudges larger objects, or organically wanders the workspace.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from vision import CameraRole

from ._base import ModeRunner

logger = logging.getLogger("ALICE")

SMALL_PICKABLE_OBJECTS = {
    "pen", "pencil", "marker", "scissors", "block", "cube", "dice", "small bottle"
}
NUDGE_ELIGIBLE_OBJECTS = {
    "cup", "mug", "bowl", "bottle", "box", "book", "cell phone", "phone"
}


class IdleRunner(ModeRunner):
    async def run(self) -> None:
        # Fist bump — use protocol from registry if available, else direct
        fist_bump_protocol = self.ctx.registry.get("fist_bump") if self.ctx.registry else None
        if fist_bump_protocol is not None:
            fist_bump = fist_bump_protocol.inner  # underlying FistBumpInteraction
        else:
            from logic.fist_bump import FistBumpInteraction
            fist_bump = FistBumpInteraction()

        # Disable unsolicited spontaneous fist bumps during idle
        fist_bump._allow_initiated = False

        # Auto-cleanup state
        last_cleanup_time: float = 0.0
        last_explore_time: float = 0.0

        # Living behaviors — snapshot references (None when disabled)
        gaze = self.ctx.gaze_tracker
        curiosity = self.ctx.curiosity_engine
        habits = self.ctx.habit_engine
        body_lang = self.ctx.body_language
        proactive = self.ctx.proactive
        sfx = self.ctx.sound_effects
        obj_memory = self.ctx.object_memory
        presence_det = self.ctx.presence_detector
        last_habit_snapshot: float = 0.0

        # Peripheral awareness — front camera passively watches for gestures
        from logic.peripheral_awareness import PeripheralAwareness
        peripheral = PeripheralAwareness()
        if hasattr(self.ctx, 'hand_detector') and self.ctx.hand_detector is not None:
            peripheral.set_hand_detector(self.ctx.hand_detector)

        while self.ctx.running():
            # Update personality tick (mood decay, idle timer)
            if self.ctx.personality is not None:
                self.ctx.personality.tick()
                behavior = self.ctx.personality.get_idle_behavior()

                # Sync personality state to state manager for dashboard
                p_state = self.ctx.personality.state
                self.ctx.state_manager.update_personality(
                    mood=p_state.overall_mood,
                    emotion=p_state.emotional_state.value,
                    idle_behavior=behavior,
                    override_streak=p_state.override_streak,
                    is_in_flow=p_state.is_in_flow,
                )
            else:
                behavior = "watch"

            # Run camera + inference regardless of idle behavior
            frame = self.ctx.cameras.get_frame(CameraRole.OVERHEAD)
            if frame is not None and not self.ctx.inference.is_frozen:
                self.ctx.inference.predict(frame)

            # --- Living behaviors tick ---
            front_frame = self.ctx.cameras.get_frame(CameraRole.FRONT_FACING)
            presence = None

            if front_frame is not None and presence_det is not None:
                presence = presence_det.detect(front_frame)
                if presence.detected and self.ctx.personality:
                    self.ctx.personality.set_presence(True)

                # Feed face position to gaze tracker
                if gaze is not None and presence.detected:
                    gaze.update_face({
                        "center_x": presence.face_center_x,
                        "center_y": presence.face_center_y,
                        "distance_cm": presence.closest_distance,
                    })

            # --- Peripheral awareness: front camera watches for gestures ---
            if front_frame is not None:
                peripheral.update(front_frame, presence)

                # Update state for dashboard
                if presence is not None:
                    self.ctx.state_manager.update_presence(
                        detected=presence.detected,
                        count=presence.face_count,
                        distance=presence.closest_distance,
                    )

            if curiosity is not None:
                # Feed YOLO detections to curiosity engine
                if frame is not None and hasattr(self.ctx.inference, 'yolo'):
                    try:
                        detections = self.ctx.inference.yolo.detect(frame)
                        mem_objects = obj_memory.objects if obj_memory else {}
                        curiosity.update(detections, mem_objects)
                    except Exception:
                        pass
                curiosity.tick()

            if habits is not None and obj_memory is not None:
                now = time.time()
                lb_cfg = getattr(self.ctx.config, 'living_behaviors', None)
                snapshot_interval = getattr(lb_cfg, 'habit_snapshot_interval_s', 30.0) if lb_cfg else 30.0
                if now - last_habit_snapshot > snapshot_interval:
                    habits.observe_snapshot(obj_memory.objects)
                    last_habit_snapshot = now
                habits.tick()

            if body_lang is not None:
                body_lang.tick(self.ctx.config.timing.idle_loop_s)

            # Proactive engagement
            if proactive is not None and not proactive.is_executing:
                decision = proactive.decide(presence)
                if decision.action.value != "none":
                    await proactive.execute(
                        decision,
                        self.ctx.dynamics,
                        self.ctx.arm,
                        self.ctx.calibration,
                        lambda: self.ctx.cameras.get_frame(CameraRole.OVERHEAD),
                        self.ctx.narration,
                    )

            # Sync living behavior state to dashboard
            if any(x is not None for x in [gaze, curiosity, habits, body_lang]):
                self.ctx.state_manager.update_living_behaviors(
                    gaze_target=gaze.get_target().label if gaze else "",
                    curiosity_total=curiosity.total_curiosity if curiosity else 0.0,
                    curiosity_most_curious=(curiosity.get_most_curious().object_id
                                            if curiosity and curiosity.get_most_curious() else ""),
                    active_habits=habits.active_habit_count if habits else 0,
                    current_posture=body_lang.current_posture_name if body_lang else "",
                    engagement_action=(proactive.is_executing and "active" or "idle")
                                      if proactive else "none",
                )

            if obj_memory is not None and hasattr(obj_memory, 'objects'):
                self.ctx.state_manager.update_object_memory([
                    o.to_dict() for o in obj_memory.objects.values()
                ])

            # --- Fist bump (reactive ONLY) ---
            # Responds when the user intentionally offers a fist
            bump_happened = False
            if frame is not None and not fist_bump.on_cooldown:
                bump_happened = await fist_bump.check_and_respond(
                    frame,
                    arm=self.ctx.arm,
                    dynamics=self.ctx.dynamics,
                    personality=self.ctx.personality,
                    narration=self.ctx.narration,
                    state_manager=self.ctx.state_manager,
                )

            if bump_happened:
                await asyncio.sleep(self.ctx.config.timing.idle_loop_s)
                continue

            # --- Peripheral glance: sneaking a look at the user ---
            if peripheral.has_pending_glance:
                glance = peripheral.get_pending_glance()
                if glance is not None:
                    confirmed = await self._execute_glance(
                        glance, peripheral, fist_bump,
                    )
                    if confirmed and body_lang is not None:
                        body_lang._trigger("attentive")

            # --- Active Curiosity Interaction (Pick up small things / Nudge) ---
            now = time.time()
            if (curiosity is not None and self.ctx.arm is not None
                    and self.ctx.calibration is not None
                    and now - last_explore_time > 15.0):
                most_curious = curiosity.get_most_curious()
                if most_curious and most_curious.curiosity_level >= 0.4:
                    explored = await self._explore_curious_object(
                        most_curious.object_id,
                        most_curious.label,
                        curiosity,
                    )
                    if explored:
                        last_explore_time = time.time()

            # --- Auto-cleanup: ALICE notices trash and tidies up ---
            if hasattr(self.ctx, 'config') and self.ctx.config.trash_zone.enabled:
                from logic.object_interaction import ObjectInteraction, TrashZone
                if (self.ctx.arm and self.ctx.gripper and self.ctx.calibration
                        and hasattr(self.ctx.inference, 'yolo')):
                    trash = TrashZone(
                        pixel_x=self.ctx.config.trash_zone.pixel_x,
                        pixel_y=self.ctx.config.trash_zone.pixel_y,
                        enabled=True,
                        detect_label=self.ctx.config.trash_zone.detect_label,
                    )
                    interaction = ObjectInteraction(
                        arm=self.ctx.arm,
                        gripper=self.ctx.gripper,
                        calibration=self.ctx.calibration,
                        dynamics=self.ctx.dynamics,
                        personality=self.ctx.personality,
                        yolo_detector=self.ctx.inference.yolo,
                        narration=self.ctx.narration,
                        trash_zone=trash,
                    )
                    camera_getter = lambda: self.ctx.cameras.get_frame(CameraRole.OVERHEAD)
                    if interaction.should_auto_cleanup(
                        personality=self.ctx.personality,
                        last_cleanup_time=last_cleanup_time,
                    ):
                        result = await interaction.auto_cleanup(
                            camera_getter,
                            personality=self.ctx.personality,
                            narration=self.ctx.narration,
                        )
                        if result.success:
                            last_cleanup_time = time.time()

            # --- Idle behaviors ---
            if behavior == "wander":
                # Organic wandering across desk — curious exploration
                if self.ctx.dynamics is not None:
                    await self.ctx.dynamics.idle_wander()

            elif behavior == "micro_motion":
                # Subtle scanning & breathing
                if self.ctx.dynamics is not None:
                    await self.ctx.dynamics.idle_micro_motion()

            elif behavior == "watch":
                # Attentive watch — apply gaze tracking if looking at a target
                if gaze is not None and self.ctx.dynamics is not None:
                    await gaze.apply(self.ctx.dynamics)

            await asyncio.sleep(self.ctx.config.timing.idle_loop_s)

        # Clean shutdown
        if fist_bump_protocol is None:
            fist_bump.shutdown()

    async def _explore_curious_object(
        self,
        object_id: str,
        label: str,
        curiosity,
    ) -> bool:
        """Physical curiosity exploration — pick up small things or nudge objects."""
        record = curiosity.records.get(object_id)
        if not record or not record.last_position:
            return False

        px = (int(record.last_position[0]), int(record.last_position[1]))
        normalized_label = label.lower().strip()

        is_small_pickable = (
            normalized_label in SMALL_PICKABLE_OBJECTS
            or any(k in normalized_label for k in ["pen", "marker", "pencil", "cube", "block", "dice", "clip", "eraser"])
        )

        from logic.arm_routines import pick_and_inspect, nudge_object

        try:
            if is_small_pickable and self.ctx.gripper is not None:
                logger.info(f"Curiosity exploration: attempting to pick up and inspect '{label}'")
                success = await pick_and_inspect(
                    self.ctx.arm,
                    self.ctx.gripper,
                    self.ctx.calibration,
                    pick_px=px,
                    inspect_duration=1.6,
                )
            else:
                logger.info(f"Curiosity exploration: nudging '{label}' to observe movement")
                success = await nudge_object(
                    self.ctx.arm,
                    self.ctx.calibration,
                    obj_px=px,
                    nudge_dx=25,
                )

            if success:
                curiosity.record_examination(object_id)
                if self.ctx.personality:
                    self.ctx.personality._last_action_time = time.time()
                return True
        except Exception as e:
            logger.debug(f"Curiosity exploration failed: {e}")

        return False

    async def _execute_glance(self, glance, peripheral, fist_bump) -> bool:
        """The glance — ALICE sweeps her arm camera toward the user."""
        from logic.peripheral_awareness import PeripheralEvent

        if self.ctx.arm is None:
            return False

        current = self.ctx.arm.position.as_tuple()
        glance_angles = (
            current[0],
            current[1] + 5,
            current[2] - 3,
            current[3],
        )

        speed = 20
        self.ctx.arm.move_to(glance_angles, speed=speed)
        await asyncio.sleep(0.4)

        arm_frame = self.ctx.cameras.get_frame(CameraRole.OVERHEAD)
        confirmed_event = peripheral.execute_glance(glance, arm_frame)

        self.ctx.arm.move_to(current, speed=15)
        await asyncio.sleep(0.3)

        if confirmed_event == PeripheralEvent.FIST_OFFERED:
            if arm_frame is not None:
                await fist_bump.check_and_respond(
                    arm_frame,
                    arm=self.ctx.arm,
                    dynamics=self.ctx.dynamics,
                    personality=self.ctx.personality,
                    narration=self.ctx.narration,
                    state_manager=self.ctx.state_manager,
                )
            return True

        return confirmed_event is not None
