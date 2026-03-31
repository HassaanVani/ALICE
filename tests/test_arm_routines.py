"""Tests for logic/arm_routines.py — pick-and-place primitive."""

import pytest

from logic.arm_routines import PickPlaceConfig


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
