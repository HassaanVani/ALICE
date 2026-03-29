"""Performance mode — the REMODEL demo arc.

A single continuous 6-act experience that introduces ALICE as a desk assistant
with opinions, memory, and personality. No visible mode switching.

Act 1: "She's Already Here" — ALICE is playing Tetris, notices someone approach
Act 2: "She Knows This Desk" — wake-up scan, object recognition, memory
Act 3: "She Helps" — proactive desk assistance, tidying
Act 4: "She Has Opinions" — tea interaction, preference enforcement, "told you"
Act 5: "She Engages (On Her Terms)" — audience votes on desk layouts, ALICE
        complies (or refuses) based on personality
Act 6: "This Is Her" — dashboard keynote moment, return to idle Tetris

See REMODEL.md for the full narrative spec.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from vision import CameraRole

from ._base import ModeRunner

logger = logging.getLogger("ALICE")


class PerformanceRunner(ModeRunner):
    """Runs the full REMODEL performance arc."""

    async def run(self) -> None:
        logger.info("Performance mode: starting 6-act arc")

        await self._act1_already_here()
        if not self.ctx.running():
            return

        await self._act2_knows_desk()
        if not self.ctx.running():
            return

        await self._act3_helps()
        if not self.ctx.running():
            return

        await self._act4_opinions()
        if not self.ctx.running():
            return

        await self._act5_engages()
        if not self.ctx.running():
            return

        await self._act6_this_is_her()

        logger.info("Performance mode: arc complete")

    # ── Act 1: She's Already Here ─────────────────────────────────

    async def _act1_already_here(self) -> None:
        """ALICE is mid-Tetris. Someone approaches. She finishes her piece, then turns."""
        logger.info("Act 1: She's Already Here")
        self.ctx.state_manager.update_demo_act(1, "She's Already Here")

        # Start idle Tetris behavior
        if self.ctx.personality:
            self.ctx.personality.enter_flow_state()

        # Run Tetris for a bit (or just idle if Tetris isn't available)
        idle_end = asyncio.get_event_loop().time() + 15.0  # 15s of Tetris
        while self.ctx.running() and asyncio.get_event_loop().time() < idle_end:
            frame = self.ctx.cameras.get_frame(CameraRole.OVERHEAD)
            if frame is not None and not self.ctx.inference.is_frozen:
                self.ctx.inference.predict(frame)

            if self.ctx.dynamics:
                await self.ctx.dynamics.idle_micro_motion()

            await asyncio.sleep(0.1)

        # "Notice" the audience (presence detection would trigger this naturally)
        if self.ctx.personality:
            self.ctx.personality.on_interrupt_from_tetris()

        await asyncio.sleep(1.0)  # pause — she's turning to look

    # ── Act 2: She Knows This Desk ────────────────────────────────

    async def _act2_knows_desk(self) -> None:
        """Wake-up scan — ALICE surveys the desk, identifies objects, checks memory."""
        logger.info("Act 2: She Knows This Desk")
        self.ctx.state_manager.update_demo_act(2, "She Knows This Desk")

        from logic.wake_scan import WakeScanRoutine

        routine = WakeScanRoutine()
        camera_getter = lambda: self.ctx.cameras.get_frame(CameraRole.OVERHEAD)

        # Run scan with whatever subsystems are available
        yolo = self.ctx.inference.yolo if hasattr(self.ctx.inference, 'yolo') else None

        result = await routine.execute(
            arm=self.ctx.arm,
            camera_getter=camera_getter,
            yolo_detector=yolo,
            running_check=self.ctx.running,
        )

        logger.info(
            f"Act 2 scan: {len(result.objects_found)} objects, "
            f"{len(result.objects_new)} new, {len(result.objects_moved)} moved"
        )

        await asyncio.sleep(2.0)  # beat — let audience absorb the scan

    # ── Act 3: She Helps ──────────────────────────────────────────

    async def _act3_helps(self) -> None:
        """Proactive assistance — ALICE tidies without being asked."""
        logger.info("Act 3: She Helps")
        self.ctx.state_manager.update_demo_act(3, "She Helps")

        from logic.desk_presets import get_preset
        from logic.desk_organizer import DeskOrganizer

        # Detect current desk state
        camera_getter = lambda: self.ctx.cameras.get_frame(CameraRole.OVERHEAD)
        frame = camera_getter()
        detections = []
        if frame is not None:
            yolo = self.ctx.inference.yolo if hasattr(self.ctx.inference, 'yolo') else None
            if yolo:
                detections = yolo.detect(frame)

        # Tidy toward "clean" preset — self-initiated
        preset = get_preset("clean")
        if preset and detections:
            organizer = DeskOrganizer()
            plan = organizer.create_plan(preset, detections)
            if plan.total_moves > 0:
                await organizer.execute_plan(
                    self.ctx.arm, self.ctx.gripper, self.ctx.calibration,
                    dynamics=self.ctx.dynamics,
                    personality=self.ctx.personality,
                    running_check=self.ctx.running,
                )

        await asyncio.sleep(2.0)

    # ── Act 4: She Has Opinions ───────────────────────────────────

    async def _act4_opinions(self) -> None:
        """The tea interaction and personality assertion.

        This is partly choreographed — the tea-spill sequence is handled
        by the tea_choreography module when available. Otherwise we
        demonstrate opinions through desk organization preferences.
        """
        logger.info("Act 4: She Has Opinions")
        self.ctx.state_manager.update_demo_act(4, "She Has Opinions")

        # Try tea choreography if available
        try:
            from logic.tea_choreography import TeaChoreography
            tea = TeaChoreography()
            await tea.execute(
                arm=self.ctx.arm,
                gripper=self.ctx.gripper,
                calibration=self.ctx.calibration,
                dynamics=self.ctx.dynamics,
                personality=self.ctx.personality,
                narration=self.ctx.narration,
                camera_getter=lambda: self.ctx.cameras.get_frame(CameraRole.OVERHEAD),
                yolo_detector=self.ctx.inference.yolo if hasattr(self.ctx.inference, 'yolo') else None,
                running_check=self.ctx.running,
            )
        except ImportError:
            logger.info("Tea choreography not available — showing basic opinions")
            await asyncio.sleep(5.0)

        await asyncio.sleep(2.0)

    # ── Act 5: She Engages (On Her Terms) ─────────────────────────

    async def _act5_engages(self) -> None:
        """Audience votes on desk layouts. ALICE complies or resists."""
        logger.info("Act 5: She Engages")
        self.ctx.state_manager.update_demo_act(5, "She Engages")

        from logic.desk_presets import get_preset
        from logic.desk_organizer import DeskOrganizer

        # Wait for audience preset votes (up to 30 seconds)
        vote_deadline = asyncio.get_event_loop().time() + 30.0
        chosen_preset = None

        while self.ctx.running() and asyncio.get_event_loop().time() < vote_deadline:
            result = self.ctx.audience_server.consume_preset_votes()
            if result:
                chosen_preset = get_preset(result["preset"])
                if chosen_preset:
                    logger.info(f"Audience chose: {chosen_preset.display_name}")
                    break
            await asyncio.sleep(1.0)

        if chosen_preset and self.ctx.running():
            # Detect and organize
            frame = self.ctx.cameras.get_frame(CameraRole.OVERHEAD)
            detections = []
            if frame is not None:
                yolo = self.ctx.inference.yolo if hasattr(self.ctx.inference, 'yolo') else None
                if yolo:
                    detections = yolo.detect(frame)

            organizer = DeskOrganizer()
            plan = organizer.create_plan(chosen_preset, detections)
            if plan.total_moves > 0:
                await organizer.execute_plan(
                    self.ctx.arm, self.ctx.gripper, self.ctx.calibration,
                    dynamics=self.ctx.dynamics,
                    personality=self.ctx.personality,
                    running_check=self.ctx.running,
                )

        await asyncio.sleep(2.0)

    # ── Act 6: This Is Her ────────────────────────────────────────

    async def _act6_this_is_her(self) -> None:
        """Dashboard keynote moment. Then ALICE returns to Tetris."""
        logger.info("Act 6: This Is Her")
        self.ctx.state_manager.update_demo_act(6, "This Is Her")

        # Hold for the keynote dashboard moment
        await asyncio.sleep(10.0)

        # Return to idle — she drifts back to Tetris
        if self.ctx.personality:
            self.ctx.personality.enter_flow_state()

        self.ctx.state_manager.update_demo_act(0, "")
        logger.info("Performance complete — returning to idle")
