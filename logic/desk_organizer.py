"""Desk Organization FSM — ALICE tidies the desk according to presets.

State machine for autonomous desk organization:
1. IDLE — waiting for trigger (user command or self-initiated)
2. SCANNING — running YOLO + depth to assess current desk state
3. PLANNING — comparing current state to target preset, generating move list
4. EXECUTING — picking and placing objects to match the target layout
5. EVALUATING — re-scanning to verify placement, adjusting if needed
6. COMPLETE — done, return to idle

The organizer works with the personality engine: self-initiated tidying is
faster and more confident, and if ALICE disagrees with a requested layout
she hesitates before complying.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("DeskOrganizer")


class OrgState(Enum):
    IDLE = "idle"
    SCANNING = "scanning"
    PLANNING = "planning"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    COMPLETE = "complete"


@dataclass
class MoveCommand:
    """A single pick-and-place command for the arm."""
    object_label: str
    object_id: str
    from_position: Tuple[float, float]   # (x, y) pixel coords of current position
    to_position: Tuple[float, float]     # (x, y) pixel coords of target position
    priority: int = 1
    completed: bool = False

    def to_dict(self) -> dict:
        return {
            "object_label": self.object_label,
            "object_id": self.object_id,
            "from": list(self.from_position),
            "to": list(self.to_position),
            "priority": self.priority,
            "completed": self.completed,
        }


@dataclass
class OrgPlan:
    """A complete plan for organizing the desk."""
    preset_name: str
    moves: List[MoveCommand] = field(default_factory=list)
    created_at: float = 0.0
    completed_at: float = 0.0

    @property
    def total_moves(self) -> int:
        return len(self.moves)

    @property
    def completed_moves(self) -> int:
        return sum(1 for m in self.moves if m.completed)

    @property
    def progress(self) -> float:
        if not self.moves:
            return 1.0
        return self.completed_moves / self.total_moves

    @property
    def is_complete(self) -> bool:
        return all(m.completed for m in self.moves)

    def next_move(self) -> Optional[MoveCommand]:
        """Get the next uncompleted move, sorted by priority."""
        pending = [m for m in self.moves if not m.completed]
        if not pending:
            return None
        return min(pending, key=lambda m: m.priority)


class DeskOrganizer:
    """State machine for desk organization.

    Drives the full cycle: scan → plan → execute → verify.

    Args:
        displacement_threshold_px: Minimum pixel distance to consider an
            object "out of place" and worth moving.
    """

    # Pixel-to-cm conversion for preset slot positions (approximate)
    # Desk presets use cm relative to center; detections are in pixels
    # This scaling factor converts preset cm to rough pixel offsets
    CM_TO_PX = 10.0  # ~10 pixels per cm at typical arm camera distance

    def __init__(self, displacement_threshold_px: float = 50.0):
        self._state = OrgState.IDLE
        self._plan: Optional[OrgPlan] = None
        self._displacement_threshold = displacement_threshold_px
        self._listeners: List[Callable[[OrgState], None]] = []

    @property
    def state(self) -> OrgState:
        return self._state

    @property
    def plan(self) -> Optional[OrgPlan]:
        return self._plan

    def on_state_change(self, callback: Callable[[OrgState], None]) -> None:
        self._listeners.append(callback)

    def _set_state(self, state: OrgState) -> None:
        old = self._state
        self._state = state
        if old != state:
            logger.info(f"Organizer: {old.value} → {state.value}")
            for cb in self._listeners:
                try:
                    cb(state)
                except Exception as e:
                    logger.error(f"State listener error: {e}")

    def create_plan(
        self,
        preset,
        current_detections: list,
        desk_center_px: Tuple[int, int] = (320, 240),
    ) -> OrgPlan:
        """Generate a move plan by comparing current object positions to a preset.

        Args:
            preset: DeskPreset with target slots.
            current_detections: List of Detection objects from YOLO.
            desk_center_px: Pixel coordinates of the desk center.

        Returns:
            OrgPlan with commands to move objects into place.
        """
        self._set_state(OrgState.PLANNING)

        plan = OrgPlan(
            preset_name=preset.name,
            created_at=time.time(),
        )

        cx, cy = desk_center_px

        for slot in preset.slots:
            # Find a detection matching this slot's label
            matching = [
                d for d in current_detections
                if hasattr(d, 'label') and d.label == slot.label
            ]
            if not matching:
                continue

            # Use the first match (highest confidence if YOLO sorted)
            det = matching[0]

            # Target position in pixels (preset cm → pixel offset from center)
            target_x = cx + int(slot.position[0] * self.CM_TO_PX)
            target_y = cy + int(slot.position[1] * self.CM_TO_PX)

            # Current position
            current_x = det.center_x
            current_y = det.center_y

            # Only move if significantly displaced
            dist = ((current_x - target_x) ** 2 + (current_y - target_y) ** 2) ** 0.5
            if dist < self._displacement_threshold:
                continue

            # Check if this object is grabbable
            if hasattr(det, 'is_grabbable') and not det.is_grabbable:
                continue

            move = MoveCommand(
                object_label=slot.label,
                object_id=f"{slot.label}_0",
                from_position=(current_x, current_y),
                to_position=(target_x, target_y),
                priority=slot.priority,
            )
            plan.moves.append(move)

        # Sort by priority
        plan.moves.sort(key=lambda m: m.priority)

        self._plan = plan
        logger.info(f"Plan created: {plan.total_moves} moves for '{preset.name}'")
        return plan

    async def execute_plan(
        self,
        arm,
        gripper,
        calibration,
        dynamics=None,
        personality=None,
        running_check: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """Execute the current plan's moves.

        Uses arm_routines.pick_and_place for each move. If dynamics and
        personality are provided, movement speed reflects ALICE's opinion
        about the task.

        Returns True if all moves completed.
        """
        if self._plan is None:
            return False

        self._set_state(OrgState.EXECUTING)

        from logic.arm_routines import pick_and_place

        for move in self._plan.moves:
            if running_check and not running_check():
                break
            if move.completed:
                continue

            logger.debug(
                f"Moving {move.object_label}: "
                f"({move.from_position[0]},{move.from_position[1]}) → "
                f"({move.to_position[0]},{move.to_position[1]})"
            )

            success = await pick_and_place(
                arm, gripper, calibration,
                pick_px=(int(move.from_position[0]), int(move.from_position[1])),
                place_px=(int(move.to_position[0]), int(move.to_position[1])),
            )

            if success:
                move.completed = True

            await asyncio.sleep(0.1)

        is_done = self._plan.is_complete
        self._set_state(OrgState.COMPLETE if is_done else OrgState.IDLE)
        self._plan.completed_at = time.time()
        return is_done

    def start_organizing(self, preset, detections, desk_center_px=(320, 240)) -> OrgPlan:
        """Convenience: create plan and set state to PLANNING."""
        return self.create_plan(preset, detections, desk_center_px)

    def abort(self) -> None:
        """Cancel current organization."""
        self._set_state(OrgState.IDLE)
        self._plan = None

    def get_status(self) -> dict:
        """JSON-serializable status for dashboard."""
        d = {
            "state": self._state.value,
        }
        if self._plan:
            d["preset"] = self._plan.preset_name
            d["total_moves"] = self._plan.total_moves
            d["completed_moves"] = self._plan.completed_moves
            d["progress"] = round(self._plan.progress, 2)
            d["moves"] = [m.to_dict() for m in self._plan.moves]
        return d
