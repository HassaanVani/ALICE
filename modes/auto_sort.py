"""Auto-Sort mode — autonomous scramble/solve/pause cycle."""

from __future__ import annotations

import asyncio
import logging

from vision import CameraRole
from logic.arm_routines import auto_scramble, auto_solve

from ._base import ModeRunner

logger = logging.getLogger("ALICE")


class AutoSortRunner(ModeRunner):
    async def run(self) -> None:
        cycle = 0
        camera_getter = lambda: self.ctx.cameras.get_frame(CameraRole.OVERHEAD)

        while self.ctx.running():
            cycle += 1
            logger.info(f"Auto-sort cycle {cycle}: scrambling...")
            self.ctx.state_manager.update_auto_sort("scrambling", cycle)
            self.ctx.sort_fsm.start_rebellion()
            self.ctx.state_manager.update_sort_state("scrambling")

            await auto_scramble(
                self.ctx.arm, self.ctx.gripper, self.ctx.calibration,
                self.ctx.detector, camera_getter,
                running_check=self.ctx.running,
            )
            if not self.ctx.running():
                break

            logger.info(f"Auto-sort cycle {cycle}: solving...")
            self.ctx.state_manager.update_auto_sort("solving", cycle)
            self.ctx.state_manager.update_sort_state("rebellion")

            await auto_solve(
                self.ctx.arm, self.ctx.gripper, self.ctx.calibration,
                self.ctx.detector, camera_getter, self.ctx.sort_fsm,
                running_check=self.ctx.running,
            )
            if not self.ctx.running():
                break

            logger.info(f"Auto-sort cycle {cycle} complete")
            self.ctx.state_manager.update_auto_sort("complete", cycle)

            # Pause before next cycle
            for _ in range(30):  # ~3 seconds
                if not self.ctx.running():
                    return
                await asyncio.sleep(0.1)
