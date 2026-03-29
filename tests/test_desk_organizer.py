"""Tests for logic/desk_organizer.py — desk organization FSM."""

import asyncio
from unittest.mock import MagicMock, AsyncMock

import numpy as np
import pytest

from logic.desk_organizer import (
    DeskOrganizer, OrgState, OrgPlan, MoveCommand,
)
from logic.desk_presets import PRESET_STUDYING, PRESET_CLEAN
from vision.yolo_detector import Detection


def _det(label, cx, cy, conf=0.9, grabbable=True):
    w, h = 60, 80
    d = Detection(
        label=label, confidence=conf,
        bbox=(cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2),
    )
    if not grabbable:
        d.is_grabbable = False
    return d


class TestMoveCommand:
    def test_to_dict(self):
        m = MoveCommand("cup", "cup_0", (100, 200), (300, 400), priority=1)
        d = m.to_dict()
        assert d["object_label"] == "cup"
        assert d["from"] == [100, 200]
        assert d["to"] == [300, 400]
        assert d["completed"] is False


class TestOrgPlan:
    def test_progress_empty(self):
        plan = OrgPlan(preset_name="test")
        assert plan.progress == 1.0
        assert plan.is_complete is True

    def test_progress_partial(self):
        plan = OrgPlan(preset_name="test", moves=[
            MoveCommand("cup", "cup_0", (0, 0), (100, 100), completed=True),
            MoveCommand("book", "book_0", (0, 0), (200, 200)),
        ])
        assert plan.total_moves == 2
        assert plan.completed_moves == 1
        assert plan.progress == 0.5
        assert plan.is_complete is False

    def test_next_move(self):
        plan = OrgPlan(preset_name="test", moves=[
            MoveCommand("cup", "cup_0", (0, 0), (100, 100), priority=2),
            MoveCommand("book", "book_0", (0, 0), (200, 200), priority=1),
        ])
        nxt = plan.next_move()
        assert nxt.object_label == "book"  # lower priority number = higher priority

    def test_next_move_skips_completed(self):
        plan = OrgPlan(preset_name="test", moves=[
            MoveCommand("book", "book_0", (0, 0), (200, 200), priority=1, completed=True),
            MoveCommand("cup", "cup_0", (0, 0), (100, 100), priority=2),
        ])
        nxt = plan.next_move()
        assert nxt.object_label == "cup"

    def test_next_move_none_when_complete(self):
        plan = OrgPlan(preset_name="test", moves=[
            MoveCommand("cup", "cup_0", (0, 0), (100, 100), completed=True),
        ])
        assert plan.next_move() is None


class TestDeskOrganizer:
    def test_initial_state(self):
        org = DeskOrganizer()
        assert org.state == OrgState.IDLE
        assert org.plan is None

    def test_create_plan_moves_displaced_objects(self):
        org = DeskOrganizer(displacement_threshold_px=30)
        # Cup is at (100, 100), preset wants it at roughly center + offset
        detections = [_det("cup", 100, 100), _det("book", 300, 300)]
        plan = org.create_plan(PRESET_STUDYING, detections, desk_center_px=(320, 240))
        assert plan.preset_name == "studying"
        assert plan.total_moves >= 1
        assert org.state == OrgState.PLANNING

    def test_create_plan_skips_close_objects(self):
        org = DeskOrganizer(displacement_threshold_px=500)
        # Object already near target — shouldn't need to move
        detections = [_det("cup", 320, 240)]
        plan = org.create_plan(PRESET_STUDYING, detections, desk_center_px=(320, 240))
        # With high threshold, most objects are "close enough"
        assert plan.total_moves == 0

    def test_create_plan_skips_non_grabbable(self):
        org = DeskOrganizer(displacement_threshold_px=10)
        detections = [_det("laptop", 100, 100)]
        plan = org.create_plan(PRESET_STUDYING, detections, desk_center_px=(320, 240))
        # Laptop is not grabbable
        laptop_moves = [m for m in plan.moves if m.object_label == "laptop"]
        assert len(laptop_moves) == 0

    def test_on_state_change_callback(self):
        org = DeskOrganizer()
        states = []
        org.on_state_change(lambda s: states.append(s))
        org.create_plan(PRESET_STUDYING, [], desk_center_px=(320, 240))
        assert OrgState.PLANNING in states

    def test_abort(self):
        org = DeskOrganizer()
        org.create_plan(PRESET_STUDYING, [_det("cup", 100, 100)])
        org.abort()
        assert org.state == OrgState.IDLE
        assert org.plan is None

    def test_get_status(self):
        org = DeskOrganizer()
        detections = [_det("cup", 100, 100)]
        org.create_plan(PRESET_STUDYING, detections, desk_center_px=(320, 240))
        status = org.get_status()
        assert status["state"] == "planning"
        assert "preset" in status
        assert "total_moves" in status


@pytest.mark.asyncio
class TestDeskOrganizerExecution:
    async def test_execute_plan(self):
        org = DeskOrganizer(displacement_threshold_px=10)
        detections = [_det("cup", 100, 100)]
        org.create_plan(PRESET_STUDYING, detections, desk_center_px=(320, 240))

        if org.plan.total_moves == 0:
            return  # nothing to execute

        mock_arm = MagicMock()
        mock_arm.move_to = MagicMock(return_value=True)
        mock_gripper = MagicMock()
        mock_calibration = MagicMock()
        mock_calibration.pixel_to_arm = MagicMock(return_value=(90, 90, 90, 90))

        success = await org.execute_plan(
            mock_arm, mock_gripper, mock_calibration,
        )
        assert org.state in (OrgState.COMPLETE, OrgState.IDLE)
