"""Centralized state manager with observable state and JSON serialization."""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional, Any

logger = logging.getLogger("AliceState")


@dataclass
class AliceState:
    mode: str = "tetris"
    arm_position: tuple = (90.0, 90.0, 90.0, 90.0, 90.0)
    arm_state: str = "idle"
    gripper_position: float = 0.0
    cameras: Dict[str, str] = field(default_factory=lambda: {
        "overhead": "unknown",
        "front": "unknown"
    })
    sort_state: str = "idle"
    tetris_score: int = 0
    puppeteer_state: str = "idle"
    detected_blocks: List[Dict] = field(default_factory=list)
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "arm_position": list(self.arm_position),
            "arm_state": self.arm_state,
            "gripper_position": self.gripper_position,
            "cameras": self.cameras,
            "sort_state": self.sort_state,
            "tetris_score": self.tetris_score,
            "puppeteer_state": self.puppeteer_state,
            "detected_blocks": self.detected_blocks,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class AliceStateManager:
    """Observable state with change listeners and JSON snapshot."""

    def __init__(self):
        self._state = AliceState()
        self._listeners: List[Callable[[AliceState], None]] = []

    @property
    def state(self) -> AliceState:
        return self._state

    def on_change(self, callback: Callable[[AliceState], None]) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        self._state.timestamp = time.time()
        for cb in self._listeners:
            try:
                cb(self._state)
            except Exception as e:
                logger.error(f"State listener error: {e}")

    def update_mode(self, mode: str) -> None:
        self._state.mode = mode
        self._notify()

    def update_arm(self, position: tuple, state: str) -> None:
        self._state.arm_position = position
        self._state.arm_state = state
        self._notify()

    def update_gripper(self, position: float) -> None:
        self._state.gripper_position = position
        self._notify()

    def update_cameras(self, health: Dict[str, str]) -> None:
        self._state.cameras = health
        self._notify()

    def update_sort_state(self, sort_state: str) -> None:
        self._state.sort_state = sort_state
        self._notify()

    def update_tetris_score(self, score: int) -> None:
        self._state.tetris_score = score
        self._notify()

    def update_puppeteer_state(self, state: str) -> None:
        self._state.puppeteer_state = state
        self._notify()

    def update_blocks(self, blocks: List[Dict]) -> None:
        self._state.detected_blocks = blocks
        self._notify()

    def get_snapshot(self) -> dict:
        """Return JSON-serializable state snapshot."""
        self._state.timestamp = time.time()
        return self._state.to_dict()

    def get_state_sync_message(self) -> str:
        """Return state_sync WebSocket message."""
        return json.dumps({
            "type": "state_sync",
            "state": self.get_snapshot()
        })

    @staticmethod
    def heartbeat_message() -> str:
        """Return heartbeat WebSocket message."""
        return json.dumps({
            "type": "heartbeat",
            "timestamp": time.time()
        })
