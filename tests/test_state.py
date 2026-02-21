"""Tests for state.py — AliceState and AliceStateManager."""

import json

import pytest

from state import AliceState, AliceStateManager


@pytest.fixture
def manager():
    return AliceStateManager()


class TestAliceStateManager:
    def test_initial_mode_is_idle(self, manager):
        assert manager.state.mode == "idle"

    def test_update_mode(self, manager):
        manager.update_mode("demo")
        assert manager.state.mode == "demo"

    def test_listener_fires_on_update(self, manager):
        received = []
        manager.on_change(lambda s: received.append(s.mode))
        manager.update_mode("auto_sort")
        assert received == ["auto_sort"]

    def test_multiple_listeners_all_fire(self, manager):
        a, b = [], []
        manager.on_change(lambda s: a.append(s.mode))
        manager.on_change(lambda s: b.append(s.mode))
        manager.update_mode("demo")
        assert a == ["demo"]
        assert b == ["demo"]

    def test_listener_exception_doesnt_crash_others(self, manager):
        results = []

        def bad_listener(s):
            raise ValueError("boom")

        def good_listener(s):
            results.append(s.mode)

        manager.on_change(bad_listener)
        manager.on_change(good_listener)
        manager.update_mode("demo")
        assert results == ["demo"]

    def test_to_dict_is_json_serializable(self, manager):
        manager.update_mode("auto_tetris")
        d = manager.state.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)

    def test_to_json_matches_to_dict(self, manager):
        manager.update_mode("calibrate")
        d = manager.state.to_dict()
        j = json.loads(manager.state.to_json())
        assert j == d

    def test_get_snapshot_has_timestamp(self, manager):
        snap = manager.get_snapshot()
        assert snap["timestamp"] > 0
