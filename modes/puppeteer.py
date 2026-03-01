"""Puppeteer mode — hand tracking via Haptix."""

from __future__ import annotations

import asyncio
import logging

from ._base import ModeRunner

logger = logging.getLogger("ALICE")


class PuppeteerRunner(ModeRunner):
    async def run(self) -> None:
        logger.info("Puppeteer mode — hand tracking via Haptix")
        self.ctx.puppet_server.go_live()
        while self.ctx.running():
            await asyncio.sleep(self.ctx.config.timing.idle_loop_s)
        self.ctx.puppet_server.stop_puppet()
