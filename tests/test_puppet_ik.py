"""Tests for hardware/puppet_ik.py — HandToArmMapper, GestureToGripper, TeachingRecorder."""

import math
import time

import pytest

from hardware.puppet_ik import (
    HandToArmMapper, GestureToGripper, TeachingRecorder,
    LearnedMotion, TeachingFrame, WorkspaceBounds, ArmGeometry,
)


@pytest.fixture
def mapper():
    return HandToArmMapper()


@pytest.fixture
def gesture():
    return GestureToGripper()


class TestHandToArmMapper:
    def test_hand_to_world_center(self, mapper):
        x, y, z = mapper.hand_to_world(0.5, 0.5, 0.5)
        assert isinstance(x, float)
        assert isinstance(y, float)
        assert isinstance(z, float)

    def test_hand_to_world_out_of_margin_returns_last(self, mapper):
        # First call within margin to set last position
        mapper.hand_to_world(0.5, 0.5, 0.5)
        # Then call outside margin
        x, y, z = mapper.hand_to_world(0.01, 0.01, 0.5)
        # Should return cached position
        assert isinstance(x, float)

    def test_solve_ik_returns_4_angles(self, mapper):
        angles = mapper.solve_ik(0, 150, 50)
        assert len(angles) == 4
        # Verify each angle is within its joint limits
        limits = ((-162, 162), (-2, 90), (-92, 60), (-180, 180))
        for a, (lo, hi) in zip(angles, limits):
            assert lo <= a <= hi

    def test_hand_to_angles_end_to_end(self, mapper):
        angles = mapper.hand_to_angles(0.5, 0.5, 0.5)
        assert len(angles) == 4

    def test_reset_clears_last_position(self, mapper):
        mapper.hand_to_world(0.5, 0.5, 0.5)
        mapper.reset()
        assert mapper._last_hand_pos is None

    def test_smoothing_setter(self, mapper):
        mapper.set_smoothing(0.5)
        assert mapper._smoothing == 0.5
        mapper.set_smoothing(2.0)  # clamp
        assert mapper._smoothing == 0.9


class TestGestureToGripper:
    def _make_landmarks(self, pinch_dist):
        """Create 21 fake landmarks with thumb and index at given distance."""
        landmarks = [{"x": 0.5, "y": 0.5, "z": 0.0} for _ in range(21)]
        landmarks[4] = {"x": 0.5, "y": 0.5, "z": 0.0}  # thumb
        landmarks[8] = {"x": 0.5 + pinch_dist, "y": 0.5, "z": 0.0}  # index
        return landmarks

    def test_initial_state_not_gripping(self, gesture):
        assert gesture.is_gripping is False

    def test_pinch_triggers_grip(self, gesture):
        landmarks = self._make_landmarks(0.02)
        # Need to bypass debounce
        gesture._last_change = 0
        result = gesture.update(landmarks)
        assert result is True

    def test_open_hand_releases(self, gesture):
        # First grip
        gesture._gripper_state = True
        gesture._last_change = 0
        landmarks = self._make_landmarks(0.2)
        result = gesture.update(landmarks)
        assert result is False

    def test_empty_landmarks_keeps_state(self, gesture):
        result = gesture.update([])
        assert result is False

    def test_is_fist(self, gesture):
        # All fingertips close to palm
        landmarks = [{"x": 0.5, "y": 0.5} for _ in range(21)]
        assert gesture.is_fist(landmarks) is True


class TestLearnedMotion:
    def test_duration_with_frames(self):
        frames = [
            TeachingFrame(timestamp=1.0, world_pos=(0, 0, 0), joint_angles=(90,)*5, gripper_state=False),
            TeachingFrame(timestamp=3.5, world_pos=(0, 0, 0), joint_angles=(90,)*5, gripper_state=False),
        ]
        motion = LearnedMotion(name="test", frames=frames)
        assert motion.duration == 2.5

    def test_duration_no_frames(self):
        motion = LearnedMotion(name="test")
        assert motion.duration == 0.0


class TestTeachingRecorder:
    def test_start_stop_recording(self, mapper):
        recorder = TeachingRecorder(mapper)
        recorder.start_recording("test")
        assert recorder.is_recording is True
        motion = recorder.stop_recording()
        assert recorder.is_recording is False

    def test_record_frame(self, mapper):
        recorder = TeachingRecorder(mapper)
        recorder.start_recording("test")
        recorder._last_record_time = 0  # Force record
        frame = recorder.record_frame(0.5, 0.5, 0.5, False)
        assert frame is not None
        motion = recorder.stop_recording()
        assert len(motion.frames) == 1

    def test_list_motions(self, mapper):
        recorder = TeachingRecorder(mapper)
        recorder.start_recording("motion1")
        recorder._last_record_time = 0
        recorder.record_frame(0.5, 0.5, 0.5, False)
        recorder.stop_recording()
        assert "motion1" in recorder.list_motions()
