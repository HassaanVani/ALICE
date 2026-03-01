"""Tests for async functions in logic/arm_routines.py — pick_and_place, auto_scramble, auto_solve."""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from logic.arm_routines import pick_and_place, auto_scramble, auto_solve, PickPlaceConfig


@pytest.fixture
def mock_arm():
    arm = MagicMock()
    arm.move_to = MagicMock(return_value=True)
    return arm


@pytest.fixture
def mock_gripper():
    gripper = MagicMock()
    gripper.open = MagicMock(return_value=True)
    gripper.close = MagicMock(return_value=True)
    return gripper


@pytest.fixture
def mock_calibration():
    cal = MagicMock()
    # pixel_to_arm returns distinct tuple per z so we can verify the sequence
    cal.pixel_to_arm = MagicMock(side_effect=lambda x, y, z: (x, y, z))
    return cal


@pytest.fixture
def fast_config():
    return PickPlaceConfig(
        z_safe=70.0, z_pick=0.0, z_lift=50.0,
        grab_delay=0.0, release_delay=0.0, move_delay=0.0,
    )


def make_block(block_id, cx, cy):
    block = MagicMock()
    block.block_id = block_id
    block.center_x = cx
    block.center_y = cy
    return block


class TestPickAndPlace:
    @pytest.mark.asyncio
    async def test_pick_and_place_sequence(self, mock_arm, mock_gripper, mock_calibration, fast_config):
        result = await pick_and_place(
            mock_arm, mock_gripper, mock_calibration,
            pick_px=(100, 200), place_px=(300, 400),
            config=fast_config,
        )
        assert result is True

        # 6 arm move_to calls (gripper close/open are separate)
        assert mock_arm.move_to.call_count == 6

        calls = [c.args[0] for c in mock_arm.move_to.call_args_list]
        # Step 1: above pick at safe height
        assert calls[0] == (100, 200, 70.0)
        # Step 2: at pick height
        assert calls[1] == (100, 200, 0.0)
        # Step 3: lift after grab
        assert calls[2] == (100, 200, 50.0)
        # Step 4: above place at safe height
        assert calls[3] == (300, 400, 70.0)
        # Step 5: at place height
        assert calls[4] == (300, 400, 0.0)
        # Step 6: retract
        assert calls[5] == (300, 400, 70.0)

        # Gripper calls
        mock_gripper.close.assert_called_once()
        mock_gripper.open.assert_called_once()

    @pytest.mark.asyncio
    async def test_pick_and_place_failure_opens_gripper(self, mock_gripper, mock_calibration, fast_config):
        arm = MagicMock()
        arm.move_to = MagicMock(side_effect=RuntimeError("arm error"))

        result = await pick_and_place(
            arm, mock_gripper, mock_calibration,
            pick_px=(10, 20), place_px=(30, 40),
            config=fast_config,
        )
        assert result is False
        # On exception, gripper.open() called for safety
        mock_gripper.open.assert_called()


class TestAutoScramble:
    @pytest.mark.asyncio
    async def test_auto_scramble_moves_all_blocks(self, mock_arm, mock_gripper, mock_calibration, fast_config):
        blocks = [make_block(i, i * 10, i * 20) for i in range(3)]
        detector = MagicMock()
        detector.detect_blocks = MagicMock(return_value=blocks)
        camera_getter = MagicMock(return_value="fake_frame")

        count = await auto_scramble(
            mock_arm, mock_gripper, mock_calibration,
            detector, camera_getter,
            config=fast_config,
        )
        assert count == 3

    @pytest.mark.asyncio
    async def test_auto_scramble_no_frame_returns_zero(self, mock_arm, mock_gripper, mock_calibration):
        camera_getter = MagicMock(return_value=None)
        detector = MagicMock()
        count = await auto_scramble(
            mock_arm, mock_gripper, mock_calibration,
            detector, camera_getter,
        )
        assert count == 0
        detector.detect_blocks.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_scramble_no_blocks_returns_zero(self, mock_arm, mock_gripper, mock_calibration):
        camera_getter = MagicMock(return_value="frame")
        detector = MagicMock()
        detector.detect_blocks = MagicMock(return_value=[])
        count = await auto_scramble(
            mock_arm, mock_gripper, mock_calibration,
            detector, camera_getter,
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_auto_scramble_respects_running_check(self, mock_arm, mock_gripper, mock_calibration, fast_config):
        blocks = [make_block(i, i * 10, i * 20) for i in range(5)]
        detector = MagicMock()
        detector.detect_blocks = MagicMock(return_value=blocks)
        camera_getter = MagicMock(return_value="frame")

        call_count = 0

        def running_check():
            nonlocal call_count
            call_count += 1
            return call_count <= 1  # Stop after first block

        count = await auto_scramble(
            mock_arm, mock_gripper, mock_calibration,
            detector, camera_getter,
            config=fast_config,
            running_check=running_check,
        )
        assert count < 5


class TestAutoSolve:
    @pytest.mark.asyncio
    async def test_auto_solve_completes_on_sort_complete(self, mock_arm, mock_gripper, mock_calibration, fast_config):
        from logic.sort_logic import SortState

        sort_fsm = MagicMock()
        sort_fsm.state = SortState.COMPLETE
        sort_fsm.update = MagicMock()

        camera_getter = MagicMock(return_value="frame")
        detector = MagicMock()
        detector.detect_blocks = MagicMock(return_value=[])

        moves = await auto_solve(
            mock_arm, mock_gripper, mock_calibration,
            detector, camera_getter, sort_fsm,
            config=fast_config,
        )
        assert moves == 0

    @pytest.mark.asyncio
    async def test_auto_solve_no_target_returns(self, mock_arm, mock_gripper, mock_calibration, fast_config):
        from logic.sort_logic import SortState

        sort_fsm = MagicMock()
        sort_fsm.state = SortState.REBELLION  # not COMPLETE
        sort_fsm.update = MagicMock()
        sort_fsm.get_optimal_next_target = MagicMock(return_value=None)

        camera_getter = MagicMock(return_value="frame")
        detector = MagicMock()
        detector.detect_blocks = MagicMock(return_value=[])

        moves = await auto_solve(
            mock_arm, mock_gripper, mock_calibration,
            detector, camera_getter, sort_fsm,
            config=fast_config,
        )
        assert moves == 0
