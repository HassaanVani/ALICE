"""Arm-based keyboard player — presses physical keys using the robotic arm."""

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("KeyboardPlayer")


@dataclass
class KeyPosition:
    """A keyboard key's hover position (arm angles) and press parameters."""
    name: str
    hover_angles: Tuple[float, ...]


class KeyboardPlayer:
    """Presses physical keyboard keys by moving the robotic arm.

    Loads key positions from a calibration JSON file. Each key has a set of
    hover angles (4-axis). A press is: move to hover -> lower J3 (elbow)
    by press_depth -> wait press_delay -> raise back.
    """

    DEFAULT_CALIBRATION = Path(__file__).parent.parent / "tetris_key_calibration.json"

    def __init__(self, arm, calibration_path: Optional[Path] = None):
        self.arm = arm
        self._keys: Dict[str, KeyPosition] = {}
        self._press_depth: float = 8.0    # degrees to lower wrist_pitch
        self._press_delay: float = 0.04   # seconds to hold key down
        self._travel_delay: float = 0.06  # seconds between key-to-key travel

        path = calibration_path or self.DEFAULT_CALIBRATION
        self._load_calibration(path)

    def _load_calibration(self, path: Path) -> None:
        if not path.exists():
            logger.warning(f"Key calibration not found: {path}")
            return

        try:
            with open(path) as f:
                data = json.load(f)

            self._press_depth = data.get("press_depth", self._press_depth)
            self._press_delay = data.get("press_delay", self._press_delay)
            self._travel_delay = data.get("travel_delay", self._travel_delay)

            for name, info in data.get("keys", {}).items():
                angles = tuple(info["angles"])
                if len(angles) != 4:
                    logger.warning(f"Key '{name}' has {len(angles)} angles, expected 4")
                    continue
                self._keys[name] = KeyPosition(name=name, hover_angles=angles)

            logger.info(f"Loaded {len(self._keys)} key positions from {path}")

        except Exception as e:
            logger.error(f"Failed to load key calibration: {e}")

    @property
    def available_keys(self) -> List[str]:
        return list(self._keys.keys())

    async def press_key(self, name: str) -> bool:
        """Press a single key: move to hover, push down, release.

        Returns True on success.
        """
        key = self._keys.get(name)
        if key is None:
            logger.warning(f"Unknown key: {name}")
            return False

        try:
            # Move to hover position
            self.arm.move_to(key.hover_angles)
            await asyncio.sleep(self._travel_delay)

            # Press: lower J3 (elbow) to push down
            pressed = list(key.hover_angles)
            pressed[2] = pressed[2] - self._press_depth  # J3 elbow index
            self.arm.move_to(tuple(pressed))
            await asyncio.sleep(self._press_delay)

            # Release: back to hover
            self.arm.move_to(key.hover_angles)
            await asyncio.sleep(self._travel_delay)

            return True

        except Exception as e:
            logger.error(f"Key press failed ({name}): {e}")
            return False

    async def execute_sequence(self, keys: List[str]) -> int:
        """Press a sequence of keys in order. Returns number of successful presses."""
        count = 0
        for name in keys:
            if await self.press_key(name):
                count += 1
        return count
