"""Tests for logic/tetris_controller.py — TetrisController action-to-key mapping."""

import pytest

from logic.tetris_agent import TetrisAction
from logic.tetris_controller import TetrisController, ACTION_TO_KEY


class TestActionToKey:
    def test_left_mapped(self):
        assert ACTION_TO_KEY[TetrisAction.LEFT] == "left_arrow"

    def test_right_mapped(self):
        assert ACTION_TO_KEY[TetrisAction.RIGHT] == "right_arrow"

    def test_rotate_cw_mapped(self):
        assert ACTION_TO_KEY[TetrisAction.ROTATE_CW] == "up_arrow"

    def test_hard_drop_mapped(self):
        assert ACTION_TO_KEY[TetrisAction.HARD_DROP] == "space"

    def test_hold_mapped(self):
        assert ACTION_TO_KEY[TetrisAction.HOLD] == "c"

    def test_none_not_mapped(self):
        assert TetrisAction.NONE not in ACTION_TO_KEY


class TestTetrisControllerKeyConversion:
    def test_actions_to_keys(self):
        # Create controller with mock dependencies
        ctrl = TetrisController.__new__(TetrisController)
        ctrl.agent = None
        keys = ctrl._actions_to_keys([
            TetrisAction.ROTATE_CW,
            TetrisAction.LEFT,
            TetrisAction.HARD_DROP,
        ])
        assert keys == ["up_arrow", "left_arrow", "space"]

    def test_actions_to_keys_skips_unmapped(self):
        ctrl = TetrisController.__new__(TetrisController)
        keys = ctrl._actions_to_keys([TetrisAction.NONE, TetrisAction.LEFT])
        assert keys == ["left_arrow"]
