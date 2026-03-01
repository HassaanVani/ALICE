"""Demo mode — 5-act show: human -> ghost -> puppet -> cyborg -> rebellion."""

from __future__ import annotations

import asyncio
import logging

from vision import CameraRole
from logic.arm_routines import auto_scramble

from ._base import DemoState, ModeRunner
from ._shared import sort_loop, rebellion_loop

logger = logging.getLogger("ALICE")


class DemoRunner(ModeRunner):
    def __init__(self, ctx, demo_state: DemoState) -> None:
        super().__init__(ctx)
        self.demo_state = demo_state

    async def run(self) -> None:
        camera_getter = lambda: self.ctx.cameras.get_frame(CameraRole.OVERHEAD)

        # ── Resuming after puppeteer interlude? Skip to Act 4 ──
        if self.demo_state.sort_act >= 3:
            self.demo_state.sort_act = 4
            await self._act4_and_5(camera_getter)
            return

        # ── Auto-scramble before Act 1 ──
        logger.info("Demo: scrambling blocks before Act 1")
        self.ctx.state_manager.update_demo_act(0, "Scrambling")
        self.ctx.state_manager.update_sort_state("scrambling")
        await auto_scramble(
            self.ctx.arm, self.ctx.gripper, self.ctx.calibration,
            self.ctx.detector, camera_getter, running_check=self.ctx.running,
        )
        if not self.ctx.running():
            return

        # ── Act 1: Human Benchmark ──
        logger.info("Act 1: Human Benchmark — sort the blocks!")
        self.ctx.state_manager.update_demo_act(1, "Human Benchmark")
        self.ctx.sort_fsm.start_human_benchmark()
        self.demo_state.human_session = await sort_loop(self.ctx)
        if not self.ctx.running():
            return

        # ── Act 2: Ghost Replay ──
        if self.demo_state.human_session and self.demo_state.human_session.moves:
            logger.info(
                f"Act 2: Ghost Replay — replaying "
                f"{len(self.demo_state.human_session.moves)} moves"
            )
            self.ctx.state_manager.update_demo_act(2, "Ghost Replay")
            self.ctx.sort_fsm.start_ghost_replay(self.demo_state.human_session)
            self.ctx.state_manager.update_sort_state("ghost_replay")
            for move in self.demo_state.human_session.moves:
                if not self.ctx.running():
                    return
                angles = self.ctx.calibration.pixel_to_arm(move.to_pos[0], move.to_pos[1])
                self.ctx.arm.move_to(angles)
                self.ctx.gripper.close()
                await asyncio.sleep(0.3)
                self.ctx.gripper.open()
                await asyncio.sleep(0.2)
            logger.info("Ghost replay complete")

        # ── Interlude: Await Puppeteer (Act 3) ──
        self.demo_state.sort_act = 3
        logger.info(
            "Acts 1-2 complete. Switch to PUPPETEER mode for Act 3, "
            "then back to DEMO for Acts 4-5."
        )
        self.ctx.state_manager.update_demo_act(3, "Puppeteer")
        self.ctx.state_manager.update_sort_state("awaiting_puppeteer")

        # Hold here until operator switches away
        while self.ctx.running():
            await asyncio.sleep(0.25)

    async def _act4_and_5(self, camera_getter) -> None:
        """Acts 4 and 5, entered after puppeteer interlude."""

        # ── Auto-scramble before Act 4 ──
        logger.info("Demo: scrambling blocks before Act 4")
        self.ctx.state_manager.update_demo_act(4, "Scrambling")
        self.ctx.state_manager.update_sort_state("scrambling")
        await auto_scramble(
            self.ctx.arm, self.ctx.gripper, self.ctx.calibration,
            self.ctx.detector, camera_getter, running_check=self.ctx.running,
        )
        if not self.ctx.running():
            return

        # ── Act 4: Cyborg Cooperation ──
        logger.info("Act 4: Cyborg Cooperation — human + robot + audience!")
        self.ctx.state_manager.update_demo_act(4, "Cyborg Coop")
        self.ctx.sort_fsm.start_cyborg_coop()
        await sort_loop(self.ctx)
        if not self.ctx.running():
            return

        # ── Auto-scramble before Act 5 ──
        logger.info("Demo: scrambling blocks before Act 5")
        self.ctx.state_manager.update_demo_act(5, "Scrambling")
        self.ctx.state_manager.update_sort_state("scrambling")
        await auto_scramble(
            self.ctx.arm, self.ctx.gripper, self.ctx.calibration,
            self.ctx.detector, camera_getter, running_check=self.ctx.running,
        )
        if not self.ctx.running():
            return

        # ── Act 5: Rebellion ──
        logger.info("Act 5: Rebellion — ALICE sorts optimally, audience overridden")
        self.ctx.state_manager.update_demo_act(5, "Rebellion")
        self.ctx.sort_fsm.start_rebellion()
        self.ctx.state_manager.update_sort_state("rebellion")
        await rebellion_loop(self.ctx)

        # Done — reset for next demo
        self.demo_state.sort_act = 0
        self.demo_state.human_session = None
        self.ctx.state_manager.update_demo_act(0, "")
