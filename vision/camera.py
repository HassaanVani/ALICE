import threading
import time
from typing import Optional, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np


class CameraRole(Enum):
    OVERHEAD = "overhead"
    FRONT_FACING = "front"


@dataclass
class CameraConfig:
    device_id: int = 0
    width: int = 1920
    height: int = 1080
    fps: int = 60
    role: CameraRole = CameraRole.OVERHEAD


class CameraFeed:
    def __init__(self, config: CameraConfig):
        self.config = config
        self._capture: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    @property
    def is_open(self) -> bool:
        return self._capture is not None and self._capture.isOpened()
    
    @property
    def frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._frame.copy() if self._frame is not None else None
    
    def open(self) -> bool:
        self._capture = cv2.VideoCapture(self.config.device_id)
        
        if not self._capture.isOpened():
            return False
        
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self._capture.set(cv2.CAP_PROP_FPS, self.config.fps)
        
        return True
    
    def close(self) -> None:
        self.stop()
        if self._capture:
            self._capture.release()
            self._capture = None
    
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
            else:
                time.sleep(0.001)
    
    def read_sync(self) -> Optional[np.ndarray]:
        if not self._capture or not self._capture.isOpened():
            return None
        
        ret, frame = self._capture.read()
        return frame if ret else None


class CameraManager:
    def __init__(self):
        self._feeds: dict[CameraRole, CameraFeed] = {}
        self._callbacks: dict[CameraRole, list[Callable[[np.ndarray], None]]] = {}
    
    def add_camera(self, config: CameraConfig) -> bool:
        feed = CameraFeed(config)
        if not feed.open():
            return False
        
        self._feeds[config.role] = feed
        self._callbacks[config.role] = []
        return True
    
    def get_frame(self, role: CameraRole) -> Optional[np.ndarray]:
        feed = self._feeds.get(role)
        return feed.frame if feed else None
    
    def on_frame(self, role: CameraRole, callback: Callable[[np.ndarray], None]) -> None:
        if role in self._callbacks:
            self._callbacks[role].append(callback)
    
    def start_all(self) -> None:
        for feed in self._feeds.values():
            feed.start()
    
    def stop_all(self) -> None:
        for feed in self._feeds.values():
            feed.stop()
    
    def close_all(self) -> None:
        for feed in self._feeds.values():
            feed.close()
        self._feeds.clear()
        self._callbacks.clear()
    
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
