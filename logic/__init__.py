from .sort_logic import ChimpSortFSM, SortState, SortingSession
from .tetris_agent import TetrisAgent
from .rl_models import SortQNetwork, SortDuelingQNetwork
from .arm_routines import pick_and_place, auto_scramble, auto_solve, PickPlaceConfig
from .tetris_controller import TetrisController
from .personality import (
    PersonalityEngine, PersonalityState, EmotionalState,
    ActionOrigin, ObjectPreference,
)
from .object_memory import ObjectMemory, ObjectRecord, DeskSnapshot
from .desk_presets import (
    DeskPreset, ObjectSlot, PRESETS,
    get_preset, list_presets, register_preset,
)
from .desk_organizer import DeskOrganizer, OrgState, OrgPlan, MoveCommand
from .wake_scan import WakeScanRoutine, ScanWaypoint, ScanResult
from .tea_choreography import TeaChoreography
from .fist_bump import FistBumpInteraction
from .teaching import TeachingSession
from .fallbacks import retry_async, retry_sync, CameraFallback, GripperFallback, ArmFallback
from .adaptive_tetris import AdaptiveTetris, TetrisStats

try:
    from .sort_env import ChimpSortEnv
except ImportError:
    ChimpSortEnv = None
