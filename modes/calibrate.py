"""Calibration mode — ArUco detection with interactive calibration point capture."""

from __future__ import annotations

import asyncio
import logging

from vision import CameraRole

from ._base import ModeRunner

logger = logging.getLogger("ALICE")


class CalibrateRunner(ModeRunner):
    async def run(self) -> None:
        import cv2

        logger.info("Calibration mode - press 'q' to quit")
        try:
            while self.ctx.running():
                frame = self.ctx.cameras.get_frame(CameraRole.OVERHEAD)
                if frame is None:
                    await asyncio.sleep(self.ctx.config.timing.camera_poll_s)
                    continue

                blocks = self.ctx.detector.detect_blocks(frame)
                display = self.ctx.detector.draw_detections(frame, blocks)

                cv2.imshow("Calibration", display)
                key = cv2.waitKey(1) & 0xFF

                if key == ord('q'):
                    break
                elif key == ord('c') and blocks:
                    block = blocks[0]
                    angles = self.ctx.arm.position.as_tuple()
                    self.ctx.calibration.add_calibration_point(
                        block.center_x, block.center_y, angles,
                    )
                    logger.info(f"Added calibration point: ({block.center_x}, {block.center_y})")
                elif key == ord('s'):
                    self.ctx.calibration.save()
                    logger.info("Calibration saved")
        finally:
            cv2.destroyAllWindows()
