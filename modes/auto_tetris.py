"""Auto-Tetris mode — arm plays tetr.io on a physical keyboard via screen capture."""

from __future__ import annotations

import logging
from pathlib import Path

from logic import TetrisController

from ._base import ModeRunner

logger = logging.getLogger("ALICE")


class AutoTetrisRunner(ModeRunner):
    async def run(self) -> None:
        logger.info("Auto-Tetris: arm plays tetr.io on physical keyboard")

        controller = self._create_controller()
        try:
            await controller.run_loop(running_check=self.ctx.running)
        finally:
            logger.info(
                f"Auto-Tetris ended: {controller.cycles} cycles, "
                f"{controller.total_keys_pressed} keys"
            )
            controller.stop()

    def _create_controller(self) -> TetrisController:
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
