"""Idle mode — ALICE watches, scans, and drifts to Tetris when bored.

She's never fully still when awake. Subtle scanning movements show awareness.
After enough idle time, she drifts to the keyboard and plays Tetris — not as
a demo, but because she wants to. She finishes her current piece before
responding to interrupts.

See PERSONALITY.md § The Tetris Quirk for the full spec.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from vision import CameraRole

from ._base import ModeRunner

logger = logging.getLogger("ALICE")


class IdleRunner(ModeRunner):
    async def run(self) -> None:
        tetris_active = False
        tetris_controller = None

        # Fist bump detector — activated when someone is close
        from logic.fist_bump import FistBumpInteraction
        fist_bump = FistBumpInteraction()

        # Auto-cleanup state
        last_cleanup_time: float = 0.0

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

            # --- Fist bump (reactive + initiated) ---
            front_frame = self.ctx.cameras.get_frame(CameraRole.FRONT_FACING)
            bump_happened = False

            if front_frame is not None and not fist_bump.on_cooldown:
                # Reactive: check if someone is offering a fist bump
                bump_happened = await fist_bump.check_and_respond(
                    front_frame,
                    arm=self.ctx.arm,
                    dynamics=self.ctx.dynamics,
                    personality=self.ctx.personality,
                    narration=self.ctx.narration,
                    state_manager=self.ctx.state_manager,
                )

            if not bump_happened and not fist_bump.initiate_on_cooldown:
                # Initiated: maybe ALICE offers a fist bump
                from vision.presence import PresenceDetector, PresenceInfo
                # Build a quick presence check from front camera availability
                presence = PresenceInfo(
                    detected=front_frame is not None,
                    closest_distance=50.0 if front_frame is not None else float("inf"),
                    looking_at_desk=True,
                )
                if fist_bump.should_initiate(
                    personality=self.ctx.personality,
                    presence_info=presence,
                ):
                    front_getter = lambda: self.ctx.cameras.get_frame(CameraRole.FRONT_FACING)
                    bump_happened = await fist_bump.initiate_bump(
                        camera_getter=front_getter,
                        arm=self.ctx.arm,
                        dynamics=self.ctx.dynamics,
                        personality=self.ctx.personality,
                        narration=self.ctx.narration,
                        state_manager=self.ctx.state_manager,
                    )

            if bump_happened:
                # After a fist bump, pause Tetris if active — she's socializing
                if tetris_active:
                    await self._stop_tetris(tetris_controller)
                    tetris_active = False
                    tetris_controller = None
                    if self.ctx.personality is not None:
                        self.ctx.personality.on_interrupt_from_tetris()
                # Skip the rest of this tick
                await asyncio.sleep(self.ctx.config.timing.idle_loop_s)
                continue

            # Idle behaviors
            if behavior == "tetris" and not tetris_active:
                # Drift to Tetris — she decided to play
                tetris_controller = self._try_start_tetris()
                if tetris_controller is not None:
                    tetris_active = True
                    if self.ctx.personality is not None:
                        self.ctx.personality.enter_flow_state()
                    logger.info("Idle: drifting to Tetris")

            elif behavior == "micro_motion" and not tetris_active:
                # Subtle scanning — she's watching
                if self.ctx.dynamics is not None:
                    await self.ctx.dynamics.idle_micro_motion()

            elif behavior == "watch":
                # Just watching. Camera + inference running above.
                if tetris_active:
                    # Was playing Tetris but something changed (presence?)
                    # Finish current piece, then stop
                    await self._stop_tetris(tetris_controller)
                    tetris_active = False
                    tetris_controller = None
                    if self.ctx.personality is not None:
                        self.ctx.personality.on_interrupt_from_tetris()

                # --- Auto-cleanup: ALICE notices trash and tidies up ---
                if hasattr(self.ctx, 'config') and self.ctx.config.trash_zone.enabled:
                    from logic.object_interaction import ObjectInteraction
                    # Build an interaction instance if we have the pieces
                    if (self.ctx.arm and self.ctx.gripper and self.ctx.calibration
                            and hasattr(self.ctx.inference, 'yolo')):
                        from logic.object_interaction import TrashZone
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
                            # She decided to clean
                            result = await interaction.auto_cleanup(
                                camera_getter,
                                personality=self.ctx.personality,
                                narration=self.ctx.narration,
                            )
                            if result.success:
                                import time as _time
                                last_cleanup_time = _time.time()

            # If Tetris is active, run one cycle
            if tetris_active and tetris_controller is not None:
                try:
                    await tetris_controller.run_one_cycle()
                except Exception as e:
                    logger.debug(f"Tetris cycle error: {e}")
                    tetris_active = False
                    tetris_controller = None
                    if self.ctx.personality is not None:
                        self.ctx.personality.exit_flow_state()

            await asyncio.sleep(self.ctx.config.timing.idle_loop_s)

        # Clean shutdown
        fist_bump.shutdown()
        if tetris_active and tetris_controller is not None:
            await self._stop_tetris(tetris_controller)
            if self.ctx.personality is not None:
                self.ctx.personality.exit_flow_state()

    def _try_start_tetris(self) -> Optional[object]:
        """Try to create a Tetris controller for idle play.

        Returns the controller if successful, None if Tetris isn't available.
        """
        if self.ctx.tetris is None:
            return None

        try:
            from logic import TetrisController
            from vision.screen_reader import ScreenReader, ScreenRegion
            from hardware.keyboard_player import KeyboardPlayer

            ts = self.ctx.config.tetris_screen
            region = ScreenRegion(
                left=ts.board_left, top=ts.board_top,
                width=ts.board_width, height=ts.board_height,
            )
            reader = ScreenReader(region)
            player = KeyboardPlayer(self.ctx.arm, Path(ts.key_calibration_path))
            return TetrisController(reader, player, self.ctx.tetris)
        except Exception as e:
            logger.debug(f"Tetris setup failed (idle): {e}")
            return None

    async def _stop_tetris(self, controller) -> None:
        """Stop Tetris gracefully — she finishes her current piece first."""
        if controller is not None:
            try:
                # Give her a moment to finish the current piece
                await asyncio.sleep(0.5)
                controller.stop()
            except Exception:
                pass
