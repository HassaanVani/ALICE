"""Tests for modes/_shared.py — sort_loop and rebellion_loop."""

import asyncio
from unittest.mock import MagicMock, PropertyMock, AsyncMock, patch
from dataclasses import dataclass

import pytest

from logic import SortState


def make_mock_context(*, sort_state=SortState.COMPLETE, running_calls=1):
    """Build a mock ModeContext for shared loop tests."""
    ctx = MagicMock()

    # running() returns True for `running_calls` iterations, then False
    call_count = 0

    def running():
        nonlocal call_count
        call_count += 1
        return call_count <= running_calls

    ctx.running = running

    # Config timing
    ctx.config.timing.camera_poll_s = 0.0
    ctx.config.timing.sort_loop_s = 0.0

    # Camera
    frame = MagicMock()
    ctx.cameras.get_frame = MagicMock(return_value=frame)

    # Detector
    block = MagicMock()
    block.block_id = 1
    block.center_x = 100
    block.center_y = 200
    block.as_dict = MagicMock(return_value={"block_id": 1})
    ctx.detector.detect_blocks = MagicMock(return_value=[block])

    # Tracker
    tracked = MagicMock()
    tracked.block_id = 1
    tracked.track_id = 1
    ctx.tracker.update = MagicMock(return_value=[tracked])

    # Sort FSM
    ctx.sort_fsm.state = sort_state
    ctx.sort_fsm.session = MagicMock()
    ctx.sort_fsm.session.move_count = 5
    ctx.sort_fsm.session.start_time = 100.0
    ctx.sort_fsm.session.duration = 10.0
    ctx.sort_fsm.update = MagicMock()
    ctx.sort_fsm.get_optimal_next_target = MagicMock(return_value=None)
    ctx.sort_fsm.get_next_robot_target = MagicMock(return_value=None)

    # State manager
    ctx.state_manager.update_blocks = MagicMock()
    ctx.state_manager.update_arm = MagicMock()
    ctx.state_manager.update_sort_progress = MagicMock()
    ctx.state_manager.update_rebellion = MagicMock()

    # Arm
    pos = MagicMock()
    pos.as_tuple = MagicMock(return_value=(0.0, 0.0, 0.0, 0.0))
    type(ctx.arm).position = PropertyMock(return_value=pos)
    type(ctx.arm).state = PropertyMock(return_value=MagicMock(value="idle"))

    # Gripper
    ctx.gripper.get_position = MagicMock(return_value=0.0)
    ctx.gripper.close = MagicMock()
    ctx.gripper.open = MagicMock()

    # Recorder
    ctx.recorder.is_recording = False
    ctx.recorder.record_blocks = MagicMock()
    ctx.recorder.record_motor = MagicMock()

    # Audience server
    ctx.audience_server.consume_votes = MagicMock(return_value=None)
    ctx.audience_server.broadcast_winner = AsyncMock()
    ctx.audience_server.broadcast_action = AsyncMock()
    ctx.audience_server.broadcast_override = AsyncMock()

    # Calibration
    ctx.calibration.pixel_to_arm = MagicMock(return_value=(0.0, 0.0, 0.0, 0.0))

    # RL agent
    ctx.rl_agent = None

    return ctx


class TestSortLoop:
    @pytest.mark.asyncio
    async def test_sort_loop_returns_session_on_complete(self):
        from modes._shared import sort_loop

        ctx = make_mock_context(sort_state=SortState.COMPLETE, running_calls=5)
        result = await sort_loop(ctx)
        assert result is not None  # returns the session

    @pytest.mark.asyncio
    async def test_sort_loop_updates_state_manager(self):
        from modes._shared import sort_loop

        ctx = make_mock_context(sort_state=SortState.COMPLETE, running_calls=5)
        await sort_loop(ctx)
        ctx.state_manager.update_blocks.assert_called()
        ctx.state_manager.update_arm.assert_called()

    @pytest.mark.asyncio
    async def test_sort_loop_records_when_recording(self):
        from modes._shared import sort_loop

        ctx = make_mock_context(sort_state=SortState.COMPLETE, running_calls=5)
        ctx.recorder.is_recording = True
        await sort_loop(ctx)
        ctx.recorder.record_blocks.assert_called()
        ctx.recorder.record_motor.assert_called()


class TestRebellionLoop:
    @pytest.mark.asyncio
    async def test_rebellion_loop_ignores_audience(self):
        from modes._shared import rebellion_loop

        # Use REBELLION state so we actually enter the loop body before COMPLETE
        ctx = make_mock_context(sort_state=SortState.REBELLION, running_calls=5)
        # Even with audience votes, rebellion uses get_optimal_next_target (not audience vote)
        ctx.audience_server.consume_votes = MagicMock(
            return_value={"block_id": 99, "voter_count": 5}
        )
        ctx.sort_fsm.get_optimal_next_target = MagicMock(return_value=None)
        await rebellion_loop(ctx)
        ctx.sort_fsm.get_optimal_next_target.assert_called()

    @pytest.mark.asyncio
    async def test_rebellion_loop_broadcasts_override(self):
        from modes._shared import rebellion_loop

        ctx = make_mock_context(sort_state=SortState.REBELLION, running_calls=2)
        ctx.audience_server.consume_votes = MagicMock(
            return_value={"block_id": 3, "voter_count": 2}
        )
        ctx.sort_fsm.get_optimal_next_target = MagicMock(
            return_value=(7, (150, 250))
        )

        await rebellion_loop(ctx)
        ctx.audience_server.broadcast_override.assert_called()
