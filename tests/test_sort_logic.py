"""Tests for logic/sort_logic.py — ChimpSortFSM."""

import numpy as np
import pytest

from logic.sort_logic import ChimpSortFSM, SortState, NUM_BLOCKS
from vision.aruco_detector import BlockData


def _make_block(block_id, cx, cy):
    """Helper to create a BlockData with minimal required fields."""
    return BlockData(
        block_id=block_id,
        marker_id=block_id - 1,
        center_x=cx,
        center_y=cy,
        corners=np.array([[cx-10, cy-10], [cx+10, cy-10],
                          [cx+10, cy+10], [cx-10, cy+10]], dtype=np.float32),
        rotation=0.0,
        confidence=1.0,
    )


@pytest.fixture
def fsm():
    return ChimpSortFSM()


class TestChimpSortFSM:
    def test_initial_state_is_idle(self, fsm):
        assert fsm.state == SortState.IDLE

    def test_start_human_benchmark(self, fsm):
        fsm.start_human_benchmark()
        assert fsm.state == SortState.HUMAN_BENCHMARK

    def test_start_rebellion_clears_positions(self, fsm):
        fsm._block_positions = {1: (100, 100)}
        fsm.start_rebellion()
        assert fsm.state == SortState.REBELLION
        assert len(fsm._block_positions) == 0

    def test_stop_returns_session_resets_idle(self, fsm):
        fsm.start_human_benchmark()
        session = fsm.stop()
        assert session is not None
        assert fsm.state == SortState.IDLE

    def test_state_change_callback(self, fsm):
        states = []
        fsm.on_state_change(lambda s: states.append(s))
        fsm.start_human_benchmark()
        assert states == [SortState.HUMAN_BENCHMARK]

    def test_is_in_drop_zone(self, fsm):
        # Default drop zone: (800, 0, 200, 300)
        assert fsm.is_in_drop_zone(850, 150) is True
        assert fsm.is_in_drop_zone(799, 150) is False
        assert fsm.is_in_drop_zone(1000, 150) is False  # x=1000 is at x+w boundary (exclusive)
        assert fsm.is_in_drop_zone(800, 0) is True  # exact corner

    def test_is_in_sorted_zone(self, fsm):
        # Default sorted zone: (0, 0, 800, 100)
        assert fsm.is_in_sorted_zone(400, 50) is True
        assert fsm.is_in_sorted_zone(400, 150) is False
        assert fsm.is_in_sorted_zone(0, 0) is True  # exact corner
        assert fsm.is_in_sorted_zone(800, 50) is False  # x=800 is at boundary (exclusive)

    def test_get_state_vector_shape(self, fsm):
        vec = fsm.get_state_vector()
        assert vec.shape == (64,)
        assert vec.dtype == np.float32

    def test_apply_action_returns_target(self, fsm):
        fsm._block_positions[1] = (500, 200)
        result = fsm.apply_action(1)
        assert result is not None
        block_id, (tx, ty) = result
        assert block_id == 1
        assert isinstance(tx, int)
        assert isinstance(ty, int)

    def test_apply_action_unknown_block_returns_none(self, fsm):
        result = fsm.apply_action(99)
        assert result is None

    def test_compute_optimal_sort(self, fsm):
        blocks = [_make_block(i, 500, 200) for i in range(1, 17)]
        moves = fsm.compute_optimal_sort(blocks)
        assert isinstance(moves, list)
        assert all(isinstance(m, tuple) and len(m) == 3 for m in moves)

    def test_check_sorted_detects_correct_order(self, fsm):
        # 16 blocks in sorted left-to-right order
        blocks = [_make_block(i, i * 50, 50) for i in range(1, 17)]
        assert fsm._check_sorted(blocks) is True

    def test_check_sorted_detects_wrong_order(self, fsm):
        # Swap blocks 1 and 2
        blocks = [_make_block(i, i * 50, 50) for i in range(1, 17)]
        blocks[0], blocks[1] = blocks[1], blocks[0]
        blocks[0] = _make_block(2, 50, 50)
        blocks[1] = _make_block(1, 100, 50)
        assert fsm._check_sorted(blocks) is False
