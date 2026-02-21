"""Tests for logic/tetris_agent.py — TetrisAgent."""

import numpy as np
import pytest

from logic.tetris_agent import TetrisAgent, TetrisAction, TetrisState, PIECES


@pytest.fixture
def agent():
    a = TetrisAgent()
    a.reset()
    return a


class TestPieces:
    def test_all_7_pieces_defined(self):
        assert len(PIECES) == 7
        for i in range(7):
            assert i in PIECES
            assert isinstance(PIECES[i], np.ndarray)


class TestTetrisAgent:
    def test_reset_board_shape(self, agent):
        assert agent.state.board.shape == (20, 10)

    def test_reset_board_all_zeros(self, agent):
        assert np.all(agent.state.board == 0)

    def test_evaluate_empty_board(self, agent):
        score = agent._evaluate_board(agent.state.board, 0)
        assert isinstance(score, float)

    def test_taller_stacks_lower_score(self, agent):
        empty = np.zeros((20, 10), dtype=np.int8)
        tall = np.zeros((20, 10), dtype=np.int8)
        tall[10:, 0] = 1  # column 0 has height 10

        score_empty = agent._evaluate_board(empty, 0)
        score_tall = agent._evaluate_board(tall, 0)
        assert score_tall < score_empty

    def test_holes_lower_score(self, agent):
        no_holes = np.zeros((20, 10), dtype=np.int8)
        no_holes[19, 0] = 1
        no_holes[18, 0] = 1

        with_holes = np.zeros((20, 10), dtype=np.int8)
        with_holes[18, 0] = 1  # block at row 18
        # row 19 is empty = hole under block

        score_no_holes = agent._evaluate_board(no_holes, 0)
        score_with_holes = agent._evaluate_board(with_holes, 0)
        assert score_with_holes < score_no_holes

    def test_line_clearing_higher_score(self, agent):
        no_lines = np.zeros((20, 10), dtype=np.int8)
        with_lines = np.zeros((20, 10), dtype=np.int8)

        score_no_lines = agent._evaluate_board(no_lines, 0)
        score_with_lines = agent._evaluate_board(with_lines, 1)
        assert score_with_lines > score_no_lines

    def test_compute_best_move_returns_actions(self, agent):
        actions = agent.compute_best_move()
        assert isinstance(actions, list)
        assert all(isinstance(a, TetrisAction) for a in actions)

    def test_compute_best_move_ends_with_hard_drop(self, agent):
        actions = agent.compute_best_move()
        assert len(actions) > 0
        assert actions[-1] == TetrisAction.HARD_DROP

    def test_step_places_piece(self, agent):
        initial_board = agent.state.board.copy()
        agent.step()
        # Board should have changed (piece placed)
        assert not np.array_equal(agent.state.board, initial_board) or agent.state.game_over
