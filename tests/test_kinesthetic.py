"""Tests for hardware/kinesthetic.py — kinesthetic teaching recorder."""

import time
from unittest.mock import MagicMock, PropertyMock

import pytest

from hardware.kinesthetic import KinestheticTeacher
from hardware.puppet_ik import TeachingFrame, LearnedMotion


@pytest.fixture
def mock_arm():
    arm = MagicMock()
    position = MagicMock()
    position.as_tuple.return_value = (10.0, 20.0, 30.0, 40.0)
    type(arm).position = PropertyMock(return_value=position)
    return arm


class TestStartStop:
    def test_start_enables_compliant(self, mock_arm):
        teacher = KinestheticTeacher(mock_arm)
        teacher.start("test_motion")
        mock_arm.set_compliant.assert_called_once_with(True)

    def test_stop_disables_compliant(self, mock_arm):
        teacher = KinestheticTeacher(mock_arm)
        teacher.start("test_motion")
        mock_arm.set_compliant.reset_mock()
        teacher.stop()
        mock_arm.set_compliant.assert_called_once_with(False)

    def test_recording_flag(self, mock_arm):
        teacher = KinestheticTeacher(mock_arm)
        assert teacher.is_recording is False
        teacher.start("test_motion")
        assert teacher.is_recording is True
        teacher.stop()
        assert teacher.is_recording is False


class TestUpdate:
    def test_update_records_frame(self, mock_arm):
        teacher = KinestheticTeacher(mock_arm)
        teacher.start("test_motion")
        # Force the interval to have elapsed
        teacher._last_record_time = 0.0
        frame = teacher.update()
        assert frame is not None
        assert isinstance(frame, TeachingFrame)
        assert frame.joint_angles == (10.0, 20.0, 30.0, 40.0)

    def test_update_respects_interval(self, mock_arm):
        teacher = KinestheticTeacher(mock_arm)
        teacher.start("test_motion")
        teacher._last_record_time = 0.0
        frame1 = teacher.update()
        assert frame1 is not None
        # Immediately call again — interval not elapsed
        frame2 = teacher.update()
        assert frame2 is None

    def test_stop_returns_motion(self, mock_arm):
        teacher = KinestheticTeacher(mock_arm)
        teacher.start("my_motion")
        teacher._last_record_time = 0.0
        teacher.update()
        motion = teacher.stop()
        assert motion is not None
        assert isinstance(motion, LearnedMotion)
        assert motion.name == "my_motion"
        assert len(motion.frames) == 1

    def test_stop_returns_none_without_frames(self, mock_arm):
        teacher = KinestheticTeacher(mock_arm)
        teacher.start("empty")
        motion = teacher.stop()
        assert motion is None

    def test_max_frames_stops_recording(self, mock_arm):
        teacher = KinestheticTeacher(mock_arm)
        teacher.start("big_motion")
        # Fill to MAX_FRAMES
        teacher._current_motion.frames = [
            TeachingFrame(
                timestamp=i * 0.05,
                world_pos=(0.0, 0.0, 0.0),
                joint_angles=(0.0, 0.0, 0.0, 0.0),
                gripper_state=False,
            )
            for i in range(KinestheticTeacher.MAX_FRAMES)
        ]
        teacher._last_record_time = 0.0
        frame = teacher.update()
        # Should return None because max frames reached
        assert frame is None
