"""Base types for mode runners."""

from __future__ import annotations

import abc
import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from config import AliceConfig
    from hardware import ArmController, CalibrationManager, KinestheticTeacher
    from hardware.dynamics import MovementDynamics
    from vision import ArucoDetector, BlockTracker, CameraManager
    from brain import InferencePipeline
    from logic import ChimpSortFSM, TetrisAgent
    from logic.personality import PersonalityEngine
    from state import AliceStateManager
    from recording import SessionRecorder
    from audience_server import AudienceServer
    from narration import NarrationService
    from puppet_server import PuppetServer
    from server import TensorStreamServer


@dataclass
class ModeContext:
    """Snapshot of all dependencies a mode runner might need."""

    config: AliceConfig
    arm: ArmController
    gripper: Any
    calibration: CalibrationManager
    cameras: CameraManager
    detector: ArucoDetector
    tracker: BlockTracker
    inference: InferencePipeline
    sort_fsm: Optional[ChimpSortFSM]
    tetris: Optional[TetrisAgent]
    kinesthetic: Optional[KinestheticTeacher]
    state_manager: AliceStateManager
    recorder: SessionRecorder
    audience_server: AudienceServer
    narration: NarrationService
    puppet_server: PuppetServer
    ws_server: TensorStreamServer
    rl_agent: Any

    is_running: Callable[[], bool] = field(repr=False)
    is_current_mode: Callable[[], bool] = field(repr=False)

    personality: Optional[PersonalityEngine] = None
    dynamics: Optional[MovementDynamics] = None

    def running(self) -> bool:
        """True while the system is running AND still in this mode."""
        return self.is_running() and self.is_current_mode()


@dataclass
class DemoState:
    """Persistent demo progression — survives mode switches."""

    sort_act: int = 0
    human_session: Any = None


class ModeRunner(abc.ABC):
    """Abstract base for all mode runners."""

    def __init__(self, ctx: ModeContext) -> None:
        self.ctx = ctx

    @abc.abstractmethod
    async def run(self) -> None: ...
