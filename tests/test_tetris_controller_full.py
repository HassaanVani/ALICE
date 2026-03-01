"""Deeper tests for logic/tetris_controller.py — controller lifecycle and run_loop."""

import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest

from logic.tetris_controller import TetrisController


@pytest.fixture
def mock_screen_reader():
    reader = MagicMock()
    reader.capture_board = MagicMock(return_value=None)
    return reader


@pytest.fixture
def mock_keyboard_player():
    player = MagicMock()
    player.execute_sequence = AsyncMock(return_value=2)
    return player


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.reset = MagicMock()
    agent.state = None
    agent.compute_best_move = MagicMock(return_value=[])
    return agent


class TestControllerInit:
    def test_controller_init(self, mock_screen_reader, mock_keyboard_player, mock_agent):
        ctrl = TetrisController(mock_screen_reader, mock_keyboard_player, mock_agent)
        assert ctrl.screen_reader is mock_screen_reader
        assert ctrl.keyboard_player is mock_keyboard_player
        assert ctrl.agent is mock_agent
        assert ctrl.cycles == 0
        assert ctrl.total_keys_pressed == 0
        assert ctrl._running is False

    def test_controller_default_agent(self, mock_screen_reader, mock_keyboard_player):
        ctrl = TetrisController(mock_screen_reader, mock_keyboard_player)
        assert ctrl.agent is not None

    def test_controller_custom_delay(self, mock_screen_reader, mock_keyboard_player, mock_agent):
        ctrl = TetrisController(mock_screen_reader, mock_keyboard_player, mock_agent, loop_delay=0.5)
        assert ctrl.loop_delay == 0.5


class TestRunLoop:
    @pytest.mark.asyncio
    async def test_run_loop_stops_on_running_check(self, mock_screen_reader, mock_keyboard_player, mock_agent):
        ctrl = TetrisController(mock_screen_reader, mock_keyboard_player, mock_agent, loop_delay=0.0)
        await ctrl.run_loop(running_check=lambda: False)
        assert ctrl.cycles == 0

    @pytest.mark.asyncio
    async def test_run_loop_increments_cycles(self, mock_screen_reader, mock_keyboard_player, mock_agent):
        import numpy as np

        # Make capture_board return a valid board_state
        board_state = MagicMock()
        board_state.grid = np.zeros((20, 10), dtype=np.uint8)
        mock_screen_reader.capture_board = MagicMock(return_value=board_state)

        # Agent returns one action, then empty on second call
        from logic.tetris_agent import TetrisAction
        call_count = 0

        def compute():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [TetrisAction.LEFT]
            return []

        mock_agent.compute_best_move = compute
        mock_agent.state = MagicMock()
        mock_agent.state.game_over = False
        mock_agent.state.board = np.zeros((20, 10), dtype=np.int8)

        iteration = 0

        def running_check():
            nonlocal iteration
            iteration += 1
            return iteration <= 3

        ctrl = TetrisController(mock_screen_reader, mock_keyboard_player, mock_agent, loop_delay=0.0)
        await ctrl.run_loop(running_check=running_check)
        assert ctrl.cycles >= 1
        assert ctrl.total_keys_pressed >= 1


class TestStop:
    def test_stop_sets_running_false(self, mock_screen_reader, mock_keyboard_player, mock_agent):
        ctrl = TetrisController(mock_screen_reader, mock_keyboard_player, mock_agent)
        ctrl._running = True
        ctrl.stop()
        assert ctrl._running is False
