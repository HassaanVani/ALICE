"""Hardware fallback behaviors — graceful degradation for live demo.

When hardware fails during a performance, ALICE should recover silently
rather than crash. Each subsystem has its own fallback strategy:

- Camera disconnect → switch to last cached frame, log warning
- Arm timeout → retry once, then skip move and continue
- Gripper failure → retry with backoff, then leave object
- YOLO model error → fall back to simulation detections
"""

import asyncio
import logging
import time
from typing import Callable, Optional, TypeVar, Any

logger = logging.getLogger("Fallbacks")

T = TypeVar("T")

# Retry configuration
MAX_RETRIES = 2
RETRY_DELAY_S = 0.3


async def retry_async(func: Callable, *args,
                       max_retries: int = MAX_RETRIES,
                       delay: float = RETRY_DELAY_S,
                       fallback: Any = None,
                       label: str = "operation") -> Any:
    """Retry an async callable with exponential backoff.

    Returns the result on success, or fallback on exhausted retries.
    """
    for attempt in range(max_retries + 1):
        try:
            return await func(*args)
        except Exception as e:
            if attempt < max_retries:
                wait = delay * (2 ** attempt)
                logger.warning(f"{label} failed (attempt {attempt + 1}): {e}, retrying in {wait:.1f}s")
                await asyncio.sleep(wait)
            else:
                logger.error(f"{label} failed after {max_retries + 1} attempts: {e}")
                return fallback


def retry_sync(func: Callable, *args,
               max_retries: int = MAX_RETRIES,
               delay: float = RETRY_DELAY_S,
               fallback: Any = None,
               label: str = "operation") -> Any:
    """Retry a sync callable with exponential backoff."""
    for attempt in range(max_retries + 1):
        try:
            return func(*args)
        except Exception as e:
            if attempt < max_retries:
                wait = delay * (2 ** attempt)
                logger.warning(f"{label} failed (attempt {attempt + 1}): {e}, retrying in {wait:.1f}s")
                time.sleep(wait)
            else:
                logger.error(f"{label} failed after {max_retries + 1} attempts: {e}")
                return fallback


class CameraFallback:
    """Caches the last good frame and returns it when camera disconnects."""

    def __init__(self):
        self._last_frame = None
        self._miss_count = 0
        self._max_misses = 30  # ~1 second at 30fps

    def get_frame(self, camera_getter: Callable) -> Optional[Any]:
        """Get a frame, falling back to cache on failure."""
        frame = camera_getter()
        if frame is not None:
            self._last_frame = frame
            self._miss_count = 0
            return frame

        self._miss_count += 1
        if self._miss_count <= self._max_misses and self._last_frame is not None:
            return self._last_frame

        return None

    @property
    def is_degraded(self) -> bool:
        return self._miss_count > 0


class GripperFallback:
    """Wraps gripper with retry logic."""

    def __init__(self, gripper):
        self._gripper = gripper

    def close(self) -> bool:
        return retry_sync(
            self._gripper.close, label="gripper.close", fallback=False
        )

    def open(self) -> bool:
        return retry_sync(
            self._gripper.open, label="gripper.open", fallback=False
        )

    def get_position(self) -> float:
        try:
            return self._gripper.get_position()
        except Exception:
            return 0.0


class ArmFallback:
    """Wraps arm controller with timeout and retry."""

    def __init__(self, arm, timeout_s: float = 5.0):
        self._arm = arm
        self._timeout = timeout_s

    def move_to(self, angles, speed=50) -> bool:
        return retry_sync(
            lambda: self._arm.move_to(angles, speed=speed),
            label="arm.move_to", fallback=False,
        )

    def home(self) -> bool:
        return retry_sync(
            self._arm.home, label="arm.home", fallback=False,
        )

    @property
    def position(self):
        return self._arm.position
