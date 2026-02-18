"""Screen capture + board parsing for tetr.io — reads the game state from pixels."""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger("ScreenReader")

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False
    logger.warning("mss not installed — screen capture disabled")


@dataclass
class ScreenRegion:
    """Screen region to capture (absolute screen coordinates)."""
    left: int
    top: int
    width: int
    height: int

    def as_dict(self) -> dict:
        return {"left": self.left, "top": self.top,
                "width": self.width, "height": self.height}


@dataclass
class TetrisBoardState:
    """Parsed 20x10 Tetris board grid. 0 = empty, 1-7 = piece color index."""
    grid: np.ndarray  # shape (20, 10), dtype uint8
    raw_frame: Optional[np.ndarray] = None  # the captured screenshot

    @property
    def height(self) -> int:
        return self.grid.shape[0]

    @property
    def width(self) -> int:
        return self.grid.shape[1]

    def to_list(self) -> List[List[int]]:
        return self.grid.tolist()


# tetr.io piece colors (approximate RGB ranges)
_COLOR_MAP = {
    "cyan":    (0, 200, 200),   # I piece
    "yellow":  (200, 200, 0),   # O piece
    "purple":  (150, 0, 200),   # T piece
    "green":   (0, 200, 0),     # S piece
    "red":     (200, 0, 0),     # Z piece
    "blue":    (0, 0, 200),     # J piece
    "orange":  (200, 130, 0),   # L piece
}

# Map color name to piece index (1-7)
_COLOR_INDEX = {
    "cyan": 1, "yellow": 2, "purple": 3, "green": 4,
    "red": 5, "blue": 6, "orange": 7,
}


def _classify_cell(pixel: np.ndarray) -> int:
    """Classify a pixel's RGB into a piece index (0 = empty, 1-7 = piece)."""
    r, g, b = int(pixel[0]), int(pixel[1]), int(pixel[2])

    # Empty cell: very dark
    if (r + g + b) / 3 < 40:
        return 0

    best_name = "empty"
    best_dist = float("inf")

    for name, (cr, cg, cb) in _COLOR_MAP.items():
        dist = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
        if dist < best_dist:
            best_dist = dist
            best_name = name

    # Reject if too far from any known color
    if best_dist > 30000:
        return 0

    return _COLOR_INDEX.get(best_name, 0)


class ScreenReader:
    """Captures a screen region and parses it as a Tetris board."""

    BOARD_ROWS = 20
    BOARD_COLS = 10

    def __init__(self, region: ScreenRegion):
        self.region = region
        self._sct = None

    def _ensure_capture(self):
        if not MSS_AVAILABLE:
            raise RuntimeError("mss is not installed — cannot capture screen")
        if self._sct is None:
            self._sct = mss.mss()

    def capture_raw(self) -> Optional[np.ndarray]:
        """Capture the screen region as an RGB numpy array."""
        self._ensure_capture()
        try:
            shot = self._sct.grab(self.region.as_dict())
            # mss returns BGRA; convert to RGB
            frame = np.array(shot)[:, :, :3][:, :, ::-1].copy()
            return frame
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return None

    def capture_board(self) -> Optional[TetrisBoardState]:
        """Capture screen and parse into a 20x10 Tetris grid."""
        frame = self.capture_raw()
        if frame is None:
            return None

        h, w = frame.shape[:2]
        cell_h = h / self.BOARD_ROWS
        cell_w = w / self.BOARD_COLS

        grid = np.zeros((self.BOARD_ROWS, self.BOARD_COLS), dtype=np.uint8)

        for row in range(self.BOARD_ROWS):
            for col in range(self.BOARD_COLS):
                # Sample center pixel of each cell
                cy = int((row + 0.5) * cell_h)
                cx = int((col + 0.5) * cell_w)
                cy = min(cy, h - 1)
                cx = min(cx, w - 1)
                pixel = frame[cy, cx]
                grid[row, col] = _classify_cell(pixel)

        return TetrisBoardState(grid=grid, raw_frame=frame)

    def close(self):
        if self._sct is not None:
            self._sct.close()
            self._sct = None
