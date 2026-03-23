"""Centralized state manager with observable state and JSON serialization."""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional, Any

logger = logging.getLogger("AliceState")


@dataclass
class AliceState:
    mode: str = "idle"
    arm_position: tuple = (90.0, 90.0, 90.0, 90.0, 90.0)
    arm_state: str = "idle"
    gripper_position: float = 0.0
    cameras: Dict[str, str] = field(default_factory=lambda: {
        "overhead": "unknown",
        "front": "unknown"
    })
    sort_state: str = "idle"
    sort_move_count: int = 0
    sort_start_time: float = 0.0
    tetris_score: int = 0
    tetris_lines: int = 0
    tetris_level: int = 1
    tetris_game_over: bool = False
    tetris_board: List[List[int]] = field(default_factory=list)
    puppeteer_state: str = "idle"
    puppeteer_recording: bool = False
    calibration_points: int = 0
    calibration_ready: bool = False
    rebellion_crowd_choice: Optional[int] = None
    rebellion_robot_choice: Optional[int] = None
    auto_sort_phase: str = "idle"
    auto_sort_cycle: int = 0
    demo_act: int = 0
    demo_act_label: str = ""
    detected_blocks: List[Dict] = field(default_factory=list)
    timestamp: float = 0.0
    # Personality state
    personality_mood: float = 0.5            # 0.0 = annoyed, 1.0 = content
    personality_emotion: str = "content"     # current emotional state
    personality_idle_behavior: str = "watch" # watch, micro_motion, or tetris
    personality_override_streak: int = 0
    personality_is_in_flow: bool = False

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "arm_position": list(self.arm_position),
            "arm_state": self.arm_state,
            "gripper_position": self.gripper_position,
            "cameras": self.cameras,
            "sort_state": self.sort_state,
            "sort_move_count": self.sort_move_count,
            "sort_start_time": self.sort_start_time,
            "tetris_score": self.tetris_score,
            "tetris_lines": self.tetris_lines,
            "tetris_level": self.tetris_level,
            "tetris_game_over": self.tetris_game_over,
            "tetris_board": self.tetris_board,
            "puppeteer_state": self.puppeteer_state,
            "puppeteer_recording": self.puppeteer_recording,
            "calibration_points": self.calibration_points,
            "calibration_ready": self.calibration_ready,
            "rebellion_crowd_choice": self.rebellion_crowd_choice,
            "rebellion_robot_choice": self.rebellion_robot_choice,
            "auto_sort_phase": self.auto_sort_phase,
            "auto_sort_cycle": self.auto_sort_cycle,
            "demo_act": self.demo_act,
            "demo_act_label": self.demo_act_label,
            "detected_blocks": self.detected_blocks,
            "timestamp": self.timestamp,
            "personality_mood": self.personality_mood,
            "personality_emotion": self.personality_emotion,
            "personality_idle_behavior": self.personality_idle_behavior,
            "personality_override_streak": self.personality_override_streak,
            "personality_is_in_flow": self.personality_is_in_flow,
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

    def update_tetris_state(self, lines_cleared: int = 0, level: int = 1,
                             game_over: bool = False, board: list = None) -> None:
        self._state.tetris_lines = lines_cleared
        self._state.tetris_level = level
        self._state.tetris_game_over = game_over
        if board is not None:
            self._state.tetris_board = board
        self._notify()

    def update_sort_progress(self, move_count: int = 0, start_time: float = 0.0) -> None:
        self._state.sort_move_count = move_count
        self._state.sort_start_time = start_time
        self._notify()

    def update_puppeteer_recording(self, recording: bool) -> None:
        self._state.puppeteer_recording = recording
        self._notify()

    def update_rebellion(self, crowd_choice: Optional[int], robot_choice: Optional[int]) -> None:
        self._state.rebellion_crowd_choice = crowd_choice
        self._state.rebellion_robot_choice = robot_choice
        self._notify()

    def update_calibration(self, points: int = 0, ready: bool = False) -> None:
        self._state.calibration_points = points
        self._state.calibration_ready = ready
        self._notify()

    def update_auto_sort(self, phase: str, cycle: int = 0) -> None:
        self._state.auto_sort_phase = phase
        self._state.auto_sort_cycle = cycle
        self._notify()

    def update_demo_act(self, act: int, label: str = "") -> None:
        self._state.demo_act = act
        self._state.demo_act_label = label
        self._notify()

    def update_blocks(self, blocks: List[Dict]) -> None:
        self._state.detected_blocks = blocks
        self._notify()

    def update_personality(self, mood: float = 0.5, emotion: str = "content",
                           idle_behavior: str = "watch", override_streak: int = 0,
                           is_in_flow: bool = False) -> None:
        self._state.personality_mood = mood
        self._state.personality_emotion = emotion
        self._state.personality_idle_behavior = idle_behavior
        self._state.personality_override_streak = override_streak
        self._state.personality_is_in_flow = is_in_flow
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
