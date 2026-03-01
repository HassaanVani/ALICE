"""Idle mode — streams camera + activations while waiting for a mode switch."""

from __future__ import annotations

import asyncio

from vision import CameraRole

from ._base import ModeRunner


class IdleRunner(ModeRunner):
    async def run(self) -> None:
        while self.ctx.running():
            frame = self.ctx.cameras.get_frame(CameraRole.OVERHEAD)
            if frame is not None and not self.ctx.inference.is_frozen:
                self.ctx.inference.predict(frame)
            await asyncio.sleep(self.ctx.config.timing.idle_loop_s)
