"""Tests for vision/depth_camera.py — SimulatedDepthCamera."""

import numpy as np
import pytest

from vision.depth_camera import SimulatedDepthCamera, DepthFrame


@pytest.fixture
def cam():
    c = SimulatedDepthCamera(width=320, height=240)
    c.open()
    return c


class TestSimulatedDepthCamera:
    def test_open(self):
        cam = SimulatedDepthCamera()
        assert cam.open() is True

    def test_read_returns_depth_frame(self, cam):
        frame = cam.read()
        assert isinstance(frame, DepthFrame)
        assert frame.color.shape == (240, 320, 3)
        assert frame.depth.shape == (240, 320)
        assert frame.timestamp > 0

    def test_read_closed_returns_none(self):
        cam = SimulatedDepthCamera()
        assert cam.read() is None

    def test_base_depth(self, cam):
        depth = cam.get_depth_at(160, 120)
        assert abs(depth - 0.8) < 0.01

    def test_block_creates_bump(self, cam):
        cam.set_block_positions([(160, 120)])
        depth_at_block = cam.get_depth_at(160, 120)
        depth_away = cam.get_depth_at(0, 0)
        assert depth_at_block < depth_away  # Block is closer

    def test_out_of_bounds_returns_base(self, cam):
        depth = cam.get_depth_at(9999, 9999)
        assert depth == cam.base_depth

    def test_close(self, cam):
        cam.close()
        assert cam.read() is None
