"""Tests for puppet_server.py — PuppetServer state transitions and wiring."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from hardware.puppeteer import PuppeteerState
from puppet_server import PuppetServer


@pytest.fixture
def server():
    """Create a PuppetServer with external mock hardware (no initialize needed)."""
    arm = MagicMock()
    magnet = MagicMock()
    gripper = MagicMock()
    s = PuppetServer(host="localhost", port=8766, simulate=True,
                     arm=arm, magnet=magnet, gripper=gripper)
    return s


class TestServerInit:
    def test_server_init(self):
        s = PuppetServer(host="0.0.0.0", port=9000, simulate=True)
        assert s.host == "0.0.0.0"
        assert s.port == 9000
        assert s.simulate is True
        assert s.state == PuppeteerState.IDLE

    def test_server_default_init(self):
        s = PuppetServer()
        assert s.host == "localhost"
        assert s.port == 8766
        assert s.simulate is True


class TestSetters:
    def test_set_state_manager(self, server):
        sm = MagicMock()
        server.set_state_manager(sm)
        assert server._state_manager is sm

    def test_set_tensor_server(self, server):
        ts = MagicMock()
        server.set_tensor_server(ts)
        assert server._tensor_server is ts


class TestStateTransitions:
    def test_go_live_sets_state(self, server):
        server.go_live()
        assert server.state == PuppeteerState.LIVE

    def test_stop_puppet_sets_idle(self, server):
        server.go_live()
        assert server.state == PuppeteerState.LIVE
        server.stop_puppet()
        assert server.state == PuppeteerState.IDLE

    def test_go_live_broadcasts_state(self, server):
        sm = MagicMock()
        server.set_state_manager(sm)
        server.go_live()
        sm.update_puppeteer_state.assert_called_with("live")

    def test_stop_puppet_broadcasts_state(self, server):
        sm = MagicMock()
        server.set_state_manager(sm)
        server.go_live()
        sm.reset_mock()
        server.stop_puppet()
        sm.update_puppeteer_state.assert_called_with("idle")

    def test_start_recording_sets_state(self, server):
        # Need recorder for recording
        server.recorder = MagicMock()
        server.start_recording("test_motion")
        assert server.state == PuppeteerState.RECORDING

    def test_stop_recording_returns_to_live(self, server):
        server.recorder = MagicMock()
        server.recorder.stop_recording.return_value = MagicMock(name="m", frames=[1, 2])
        server.start_recording("test")
        motion = server.stop_recording()
        assert server.state == PuppeteerState.LIVE
