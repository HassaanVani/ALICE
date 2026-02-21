"""Tests for logic/arm_routines.py — pick-and-place helpers."""

import pytest

from logic.arm_routines import PickPlaceConfig, _random_position


class TestPickPlaceConfig:
    def test_defaults(self):
        cfg = PickPlaceConfig()
        assert cfg.z_safe == 70.0
        assert cfg.z_pick == 0.0
        assert cfg.grab_delay == 0.15

    def test_custom(self):
        cfg = PickPlaceConfig(z_safe=100, grab_delay=0.5)
        assert cfg.z_safe == 100
        assert cfg.grab_delay == 0.5


class TestRandomPosition:
    def test_within_bounds(self):
        bounds = (100, 50, 600, 250)
        pos = _random_position(bounds, [])
        x, y = pos
        assert 100 <= x <= 700
        assert 50 <= y <= 300

    def test_avoids_existing(self):
        bounds = (0, 0, 1000, 1000)
        existing = [(500, 500)]
        for _ in range(20):
            pos = _random_position(bounds, existing, min_spacing=100)
            x, y = pos
            # Should be at least min_spacing away in x or y
            assert abs(x - 500) > 100 or abs(y - 500) > 100

    def test_fallback_returns_center(self):
        # Completely packed — fallback should still return something
        bounds = (0, 0, 60, 60)
        existing = [(x, y) for x in range(0, 60, 10) for y in range(0, 60, 10)]
        pos = _random_position(bounds, existing, min_spacing=100)
        assert len(pos) == 2
