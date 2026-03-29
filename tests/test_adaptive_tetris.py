"""Tests for logic/adaptive_tetris.py and logic/fallbacks.py."""

import asyncio
import time

import pytest

from logic.adaptive_tetris import AdaptiveTetris, TetrisStats
from logic.fallbacks import retry_sync, CameraFallback


class TestTetrisStats:
    def test_initial_skill_zero(self):
        stats = TetrisStats()
        assert stats.skill_level == 0.0

    def test_skill_increases_with_games(self):
        stats = TetrisStats(games_played=25, total_lines_cleared=250)
        assert 0.3 < stats.skill_level < 0.7

    def test_skill_caps_at_one(self):
        stats = TetrisStats(games_played=100, total_lines_cleared=1000)
        assert stats.skill_level == 1.0

    def test_roundtrip(self):
        stats = TetrisStats(games_played=10, total_lines_cleared=80, max_score=5000)
        d = stats.to_dict()
        stats2 = TetrisStats.from_dict(d)
        assert stats2.games_played == 10
        assert stats2.total_lines_cleared == 80


class TestAdaptiveTetris:
    def test_beginner_weights(self):
        at = AdaptiveTetris()
        weights = at.get_agent_weights()
        # Beginner should have less aggressive weights
        assert weights["height"] > -0.5
        assert weights["lines"] < 1.0

    def test_expert_weights(self, tmp_path):
        at = AdaptiveTetris(path=tmp_path / "stats.json")
        at._stats = TetrisStats(games_played=100, total_lines_cleared=1000)
        weights = at.get_agent_weights()
        assert weights["height"] < -0.5
        assert weights["lines"] > 1.0

    def test_record_game(self):
        at = AdaptiveTetris()
        at.record_game(lines=10, score=3000, duration=60)
        assert at.stats.games_played == 1
        assert at.stats.total_lines_cleared == 10
        assert at.stats.max_score == 3000

    def test_decision_delay_decreases(self):
        at = AdaptiveTetris()
        beginner_delay = at.get_decision_delay()
        at._stats = TetrisStats(games_played=100, total_lines_cleared=1000)
        expert_delay = at.get_decision_delay()
        assert expert_delay < beginner_delay

    def test_save_and_load(self, tmp_path):
        path = tmp_path / "tetris.json"
        at = AdaptiveTetris(path=path)
        at.record_game(lines=20, score=8000, duration=120)
        at.save()

        at2 = AdaptiveTetris(path=path)
        at2.load()
        assert at2.stats.games_played == 1
        assert at2.stats.total_lines_cleared == 20

    def test_apply_to_agent(self):
        from unittest.mock import MagicMock
        at = AdaptiveTetris()
        at._stats = TetrisStats(games_played=50, total_lines_cleared=400)
        agent = MagicMock()
        agent._weights = {"height": 0, "holes": 0, "bumpiness": 0, "lines": 0}
        at.apply_to_agent(agent)
        assert agent._weights["height"] != 0


class TestCameraFallback:
    def test_returns_frame_on_success(self):
        import numpy as np
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        fb = CameraFallback()
        result = fb.get_frame(lambda: frame)
        assert result is frame
        assert not fb.is_degraded

    def test_returns_cached_on_failure(self):
        import numpy as np
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        fb = CameraFallback()
        fb.get_frame(lambda: frame)  # cache it
        result = fb.get_frame(lambda: None)  # camera fails
        assert result is frame
        assert fb.is_degraded

    def test_returns_none_after_too_many_misses(self):
        fb = CameraFallback()
        fb._max_misses = 2
        fb.get_frame(lambda: None)
        fb.get_frame(lambda: None)
        result = fb.get_frame(lambda: None)
        assert result is None


class TestRetrySyncFn:
    def test_succeeds_first_try(self):
        result = retry_sync(lambda: 42, label="test")
        assert result == 42

    def test_succeeds_on_retry(self):
        calls = [0]
        def flaky():
            calls[0] += 1
            if calls[0] < 2:
                raise RuntimeError("fail")
            return "ok"
        result = retry_sync(flaky, max_retries=2, delay=0.01, label="flaky")
        assert result == "ok"

    def test_returns_fallback_on_exhaust(self):
        def always_fail():
            raise RuntimeError("nope")
        result = retry_sync(always_fail, max_retries=1, delay=0.01,
                            fallback="default", label="fail")
        assert result == "default"
