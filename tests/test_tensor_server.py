"""Tests for server.py — TensorStreamServer initialization and wiring."""

from unittest.mock import MagicMock

import pytest

from server import TensorStreamServer


class TestServerInit:
    def test_server_init(self):
        server = TensorStreamServer(host="0.0.0.0", port=9000)
        assert server.host == "0.0.0.0"
        assert server.port == 9000
        assert server.pipeline is None
        assert server._state_manager is None

    def test_server_default_init(self):
        server = TensorStreamServer()
        assert server.host == "localhost"
        assert server.port == 8765


class TestSetters:
    def test_set_pipeline(self):
        server = TensorStreamServer()
        pipeline = MagicMock()
        server.set_pipeline(pipeline)
        assert server.pipeline is pipeline

    def test_set_state_manager(self):
        server = TensorStreamServer()
        sm = MagicMock()
        server.set_state_manager(sm)
        assert server._state_manager is sm

    def test_set_switch_mode_callback(self):
        server = TensorStreamServer()
        cb = MagicMock()
        server.set_switch_mode_callback(cb)
        assert server._switch_mode_callback is cb
        # Verify it's callable
        server._switch_mode_callback("test")
        cb.assert_called_once_with("test")

    def test_set_camera_frame_getter(self):
        server = TensorStreamServer()
        getter = MagicMock(return_value="frame")
        server.set_camera_frame_getter(getter)
        assert server._camera_frame_getter is getter
        assert server._camera_frame_getter() == "frame"

    def test_set_recorder(self):
        server = TensorStreamServer()
        recorder = MagicMock()
        server.set_recorder(recorder)
        assert server._recorder is recorder


class TestServerState:
    def test_initial_clients_empty(self):
        server = TensorStreamServer()
        assert len(server.clients) == 0

    def test_initial_streaming_false(self):
        server = TensorStreamServer()
        assert server._streaming is False

    def test_max_client_queue(self):
        server = TensorStreamServer()
        assert server.MAX_CLIENT_QUEUE == 8
