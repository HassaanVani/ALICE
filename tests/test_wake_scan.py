"""Tests for logic/wake_scan.py — wake-up desk scan."""

import asyncio
from unittest.mock import MagicMock

import numpy as np
import pytest

from logic.wake_scan import (
    WakeScanRoutine, ScanWaypoint, ScanResult, DEFAULT_SCAN_WAYPOINTS,
)


@pytest.fixture
def mock_arm():
    arm = MagicMock()
    arm.move_to = MagicMock(return_value=True)
    return arm


@pytest.fixture
def frame_getter():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    return lambda: frame


class TestScanWaypoint:
    def test_defaults(self):
        wp = ScanWaypoint((90, 90, 90, 90))
        assert wp.dwell_time == 0.5
        assert wp.label == ""

    def test_default_waypoints_exist(self):
        assert len(DEFAULT_SCAN_WAYPOINTS) >= 4
        for wp in DEFAULT_SCAN_WAYPOINTS:
            assert len(wp.angles) == 4


class TestScanResult:
    def test_fields(self):
        result = ScanResult(
            objects_found=[{"label": "cup"}],
            objects_moved=["cup_0"],
            objects_new=["laptop_0"],
            frames_captured=10,
            duration_s=5.0,
            waypoints_completed=6,
        )
        assert len(result.objects_found) == 1
        assert result.frames_captured == 10


@pytest.mark.asyncio
class TestWakeScanRoutine:
    async def test_basic_scan(self, mock_arm, frame_getter):
        # Short scan with minimal waypoints
        routine = WakeScanRoutine(
            waypoints=[ScanWaypoint((90, 90, 90, 90), dwell_time=0.1)],
        )
        result = await routine.execute(
            arm=mock_arm,
            camera_getter=frame_getter,
        )
        assert result.waypoints_completed == 1
        assert result.frames_captured >= 1
        assert result.duration_s > 0
        mock_arm.move_to.assert_called()

    async def test_scan_with_yolo(self, mock_arm, frame_getter):
        from vision.yolo_detector import YoloDetector
        yolo = YoloDetector()
        yolo._simulate = True

        routine = WakeScanRoutine(
            waypoints=[ScanWaypoint((90, 90, 90, 90), dwell_time=0.1)],
        )
        result = await routine.execute(
            arm=mock_arm,
            camera_getter=frame_getter,
            yolo_detector=yolo,
        )
        assert len(result.objects_found) >= 1

    async def test_scan_aborts_on_running_check(self, mock_arm, frame_getter):
        call_count = 0

        def stop_after_one():
            nonlocal call_count
            call_count += 1
            return call_count <= 2

        routine = WakeScanRoutine(
            waypoints=[
                ScanWaypoint((90, 90, 90, 90), dwell_time=0.1),
                ScanWaypoint((50, 90, 90, 90), dwell_time=0.1),
                ScanWaypoint((130, 90, 90, 90), dwell_time=0.1),
            ],
        )
        result = await routine.execute(
            arm=mock_arm,
            camera_getter=frame_getter,
            running_check=stop_after_one,
        )
        assert result.waypoints_completed < 3

    async def test_scan_with_object_memory(self, mock_arm, frame_getter, tmp_path):
        from vision.yolo_detector import YoloDetector
        from logic.object_memory import ObjectMemory

        yolo = YoloDetector()
        yolo._simulate = True
        memory = ObjectMemory(path=tmp_path / "mem.json")

        routine = WakeScanRoutine(
            waypoints=[ScanWaypoint((90, 90, 90, 90), dwell_time=0.1)],
        )
        result = await routine.execute(
            arm=mock_arm,
            camera_getter=frame_getter,
            yolo_detector=yolo,
            object_memory=memory,
        )
        assert len(result.objects_new) >= 1
        assert memory.object_count >= 1

    async def test_no_frame_still_completes(self, mock_arm):
        routine = WakeScanRoutine(
            waypoints=[ScanWaypoint((90, 90, 90, 90), dwell_time=0.1)],
        )
        result = await routine.execute(
            arm=mock_arm,
            camera_getter=lambda: None,
        )
        assert result.waypoints_completed == 1
        assert result.frames_captured == 0
