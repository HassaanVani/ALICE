import logging
import threading
import time
from typing import Optional, Tuple, Callable, Dict, List
from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np

logger = logging.getLogger("Camera")


class CameraRole(Enum):
    OVERHEAD = "overhead"
    FRONT_FACING = "front"


class CameraHealth(Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
    FAILED = "failed"


@dataclass
class CameraConfig:
    device_id: int = 0
    width: int = 1920
    height: int = 1080
    fps: int = 60
    role: CameraRole = CameraRole.OVERHEAD


class CameraFeed:
    MAX_CONSECUTIVE_FAILURES = 30
    MAX_RECONNECT_ATTEMPTS = 5
    STALE_THRESHOLD_S = 2.0

    def __init__(self, config: CameraConfig):
        self.config = config
        self._capture: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._health = CameraHealth.UNKNOWN
        self._last_frame_time: float = 0.0
        self._consecutive_failures: int = 0
        self._reconnect_attempts: int = 0
        self._on_frame_callbacks: List[Callable[[np.ndarray], None]] = []
        self._on_error_callbacks: List[Callable[['CameraFeed', CameraHealth], None]] = []

    def on_frame(self, callback: Callable[[np.ndarray], None]) -> None:
        self._on_frame_callbacks.append(callback)

    def on_error(self, callback: Callable[['CameraFeed', CameraHealth], None]) -> None:
        self._on_error_callbacks.append(callback)

    @property
    def health(self) -> CameraHealth:
        return self._health

    @property
    def is_open(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    @property
    def is_stale(self) -> bool:
        if self._last_frame_time == 0:
            return False
        return (time.time() - self._last_frame_time) > self.STALE_THRESHOLD_S

    @property
    def frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def open(self) -> bool:
        self._capture = cv2.VideoCapture(self.config.device_id)

        if not self._capture.isOpened():
            self._health = CameraHealth.DISCONNECTED
            logger.warning(f"Camera {self.config.role.value} (device {self.config.device_id}) failed to open")
            return False

        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self._capture.set(cv2.CAP_PROP_FPS, self.config.fps)

        self._health = CameraHealth.HEALTHY
        self._consecutive_failures = 0
        self._reconnect_attempts = 0
        return True

    def close(self) -> None:
        self.stop()
        if self._capture:
            self._capture.release()
            self._capture = None
        self._health = CameraHealth.DISCONNECTED

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _capture_loop(self) -> None:
        while self._running and self._capture and self._capture.isOpened():
            ret, frame = self._capture.read()
            if ret:
                with self._lock:
                    self._frame = frame
                self._last_frame_time = time.time()
                self._consecutive_failures = 0
                if self._health != CameraHealth.HEALTHY:
                    self._health = CameraHealth.HEALTHY
                    logger.info(f"Camera {self.config.role.value} recovered")
                # Fire frame callbacks
                for cb in self._on_frame_callbacks:
                    try:
                        cb(frame)
                    except Exception as e:
                        logger.debug(f"Frame callback error: {e}")
            else:
                self._consecutive_failures += 1
                if self._consecutive_failures > self.MAX_CONSECUTIVE_FAILURES:
                    old_health = self._health
                    self._health = CameraHealth.DEGRADED
                    logger.warning(
                        f"Camera {self.config.role.value} degraded "
                        f"({self._consecutive_failures} consecutive failures)"
                    )
                    # Fire error callbacks on health change
                    if old_health != self._health:
                        for cb in self._on_error_callbacks:
                            try:
                                cb(self, self._health)
                            except Exception as e:
                                logger.debug(f"Error callback failed: {e}")
                    if self._attempt_reconnect():
                        self._consecutive_failures = 0
                    else:
                        self._health = CameraHealth.FAILED
                        for cb in self._on_error_callbacks:
                            try:
                                cb(self, self._health)
                            except Exception as e:
                                logger.debug(f"Error callback failed: {e}")
                        logger.error(f"Camera {self.config.role.value} failed after reconnect attempts")
                        break
                time.sleep(0.001)

    def _attempt_reconnect(self) -> bool:
        """Re-open camera device with exponential backoff."""
        if self._reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
            return False

        self._reconnect_attempts += 1
        delay = 0.5 * (2 ** (self._reconnect_attempts - 1))
        logger.info(
            f"Camera {self.config.role.value} reconnect attempt "
            f"{self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS} in {delay:.1f}s"
        )
        time.sleep(delay)

        if self._capture:
            self._capture.release()

        self._capture = cv2.VideoCapture(self.config.device_id)
        if self._capture.isOpened():
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
            self._capture.set(cv2.CAP_PROP_FPS, self.config.fps)
            self._health = CameraHealth.HEALTHY
            self._reconnect_attempts = 0
            logger.info(f"Camera {self.config.role.value} reconnected successfully")
            return True

        return False

    def read_sync(self) -> Optional[np.ndarray]:
        if not self._capture or not self._capture.isOpened():
            return None

        ret, frame = self._capture.read()
        return frame if ret else None


class CameraManager:
    def __init__(self):
        self._feeds: dict[CameraRole, CameraFeed] = {}
        self._callbacks: dict[CameraRole, list[Callable[[np.ndarray], None]]] = {}
        self._error_callbacks: dict[CameraRole, list[Callable[[CameraRole, CameraHealth], None]]] = {}

    def add_camera(self, config: CameraConfig) -> bool:
        feed = CameraFeed(config)
        if not feed.open():
            logger.warning(f"Camera {config.role.value} unavailable, registering as disconnected")
            self._feeds[config.role] = feed
            self._callbacks[config.role] = []
            self._error_callbacks[config.role] = []
            return False

        self._feeds[config.role] = feed
        self._callbacks[config.role] = []
        self._error_callbacks[config.role] = []
        return True

    def get_frame(self, role: CameraRole) -> Optional[np.ndarray]:
        feed = self._feeds.get(role)
        return feed.frame if feed else None

    def get_health(self, role: CameraRole) -> CameraHealth:
        feed = self._feeds.get(role)
        return feed.health if feed else CameraHealth.DISCONNECTED

    def get_all_health(self) -> Dict[str, str]:
        return {
            role.value: feed.health.value
            for role, feed in self._feeds.items()
        }

    def on_frame(self, role: CameraRole, callback: Callable[[np.ndarray], None]) -> None:
        if role in self._callbacks:
            self._callbacks[role].append(callback)
        # Wire directly to the feed so it fires from the capture thread
        feed = self._feeds.get(role)
        if feed:
            feed.on_frame(callback)

    def on_error(self, role: CameraRole, callback: Callable[[CameraRole, CameraHealth], None]) -> None:
        if role not in self._error_callbacks:
            self._error_callbacks[role] = []
        self._error_callbacks[role].append(callback)
        # Wire to feed — adapt signature (feed passes CameraFeed, CameraHealth)
        feed = self._feeds.get(role)
        if feed:
            feed.on_error(lambda _feed, health: callback(role, health))

    def start_all(self) -> None:
        for feed in self._feeds.values():
            if feed.is_open:
                feed.start()

    def stop_all(self) -> None:
        for feed in self._feeds.values():
            feed.stop()

    def close_all(self) -> None:
        for feed in self._feeds.values():
            feed.close()
        self._feeds.clear()
        self._callbacks.clear()
        self._error_callbacks.clear()

    def get_resolution(self, role: CameraRole) -> Optional[Tuple[int, int]]:
        feed = self._feeds.get(role)
        if feed and feed.is_open:
            return (feed.config.width, feed.config.height)
        return None

    def __enter__(self) -> "CameraManager":
        return self

    def __exit__(self, *args) -> None:
        self.close_all()


def create_dual_camera_setup(
    overhead_id: int = 0,
    front_id: int = 1,
    overhead_resolution: Tuple[int, int] = (1920, 1080),
    front_resolution: Tuple[int, int] = (1280, 720)
) -> CameraManager:
    manager = CameraManager()

    overhead_config = CameraConfig(
        device_id=overhead_id,
        width=overhead_resolution[0],
        height=overhead_resolution[1],
        fps=60,
        role=CameraRole.OVERHEAD
    )

    front_config = CameraConfig(
        device_id=front_id,
        width=front_resolution[0],
        height=front_resolution[1],
        fps=30,
        role=CameraRole.FRONT_FACING
    )

    manager.add_camera(overhead_config)
    manager.add_camera(front_config)

    return manager
