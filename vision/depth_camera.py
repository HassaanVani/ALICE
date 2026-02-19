"""Depth camera abstraction — ABC + simulated + RealSense stub."""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger("DepthCamera")


@dataclass
class DepthFrame:
    color: np.ndarray          # BGR uint8 image
    depth: np.ndarray          # float32, meters
    timestamp: float


class DepthCamera(ABC):
    @abstractmethod
    def open(self) -> bool:
        ...

    @abstractmethod
    def close(self) -> None:
        ...

    @abstractmethod
    def read(self) -> Optional[DepthFrame]:
        ...

    @abstractmethod
    def get_depth_at(self, x: int, y: int) -> float:
        ...


class SimulatedDepthCamera(DepthCamera):
    """Produces synthetic depth maps — flat plane with bumps at known block positions."""

    def __init__(self, width: int = 640, height: int = 480, base_depth: float = 0.8):
        self.width = width
        self.height = height
        self.base_depth = base_depth
        self._open = False
        self._depth_map: Optional[np.ndarray] = None
        self._block_positions: list[Tuple[int, int]] = []

    def set_block_positions(self, positions: list[Tuple[int, int]]) -> None:
        self._block_positions = positions
        self._regenerate_depth()

    def _regenerate_depth(self) -> None:
        self._depth_map = np.full((self.height, self.width), self.base_depth, dtype=np.float32)
        for bx, by in self._block_positions:
            # Add a bump (block rises above table)
            r = 20
            y_lo = max(0, by - r)
            y_hi = min(self.height, by + r)
            x_lo = max(0, bx - r)
            x_hi = min(self.width, bx + r)
            yy, xx = np.mgrid[y_lo:y_hi, x_lo:x_hi]
            dist = np.sqrt((xx - bx) ** 2 + (yy - by) ** 2)
            mask = dist < r
            bump = 0.05 * (1 - dist[mask] / r)
            self._depth_map[y_lo:y_hi, x_lo:x_hi][mask] -= bump

    def open(self) -> bool:
        self._open = True
        self._regenerate_depth()
        return True

    def close(self) -> None:
        self._open = False

    def read(self) -> Optional[DepthFrame]:
        if not self._open:
            return None
        color = np.random.randint(100, 200, (self.height, self.width, 3), dtype=np.uint8)
        depth = self._depth_map.copy() if self._depth_map is not None else \
            np.full((self.height, self.width), self.base_depth, dtype=np.float32)
        # Add slight noise
        depth += np.random.normal(0, 0.002, depth.shape).astype(np.float32)
        return DepthFrame(color=color, depth=depth, timestamp=time.time())

    def get_depth_at(self, x: int, y: int) -> float:
        if self._depth_map is None:
            return self.base_depth
        if 0 <= y < self.height and 0 <= x < self.width:
            return float(self._depth_map[y, x])
        return self.base_depth


class RealSenseDepthCamera(DepthCamera):
    """Intel RealSense wrapper — requires pyrealsense2."""

    def __init__(self, width: int = 640, height: int = 480, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self._pipeline = None
        self._last_depth: Optional[np.ndarray] = None

    def open(self) -> bool:
        try:
            import pyrealsense2 as rs
            self._pipeline = rs.pipeline()
            config = rs.config()
            config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, self.fps)
            config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps)
            self._pipeline.start(config)
            return True
        except ImportError:
            logger.warning("pyrealsense2 not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to open RealSense: {e}")
            return False

    def close(self) -> None:
        if self._pipeline:
            try:
                self._pipeline.stop()
            except Exception as e:
                logger.debug(f"Error stopping RealSense pipeline: {e}")
            self._pipeline = None

    def read(self) -> Optional[DepthFrame]:
        if not self._pipeline:
            return None
        try:
            import pyrealsense2 as rs
            frames = self._pipeline.wait_for_frames(timeout_ms=1000)
            depth_frame = frames.get_depth_frame()
            color_frame = frames.get_color_frame()
            if not depth_frame or not color_frame:
                return None
            depth = np.asanyarray(depth_frame.get_data()).astype(np.float32) * depth_frame.get_units()
            color = np.asanyarray(color_frame.get_data())
            self._last_depth = depth
            return DepthFrame(color=color, depth=depth, timestamp=time.time())
        except Exception as e:
            logger.debug(f"RealSense read failed: {e}")
            return None

    def get_depth_at(self, x: int, y: int) -> float:
        if self._last_depth is not None:
            h, w = self._last_depth.shape
            if 0 <= y < h and 0 <= x < w:
                return float(self._last_depth[y, x])
        return 0.0
