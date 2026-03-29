"""Tests for logic/fist_bump.py — CV-based fist bump interaction."""

import asyncio
import time
from unittest.mock import MagicMock

import numpy as np
import pytest

from logic.fist_bump import FistBumpInteraction, BUMP_CENTER, RETRACT_ANGLES


@pytest.fixture
def bump():
    return FistBumpInteraction(cooldown_s=0)


@pytest.fixture
def frame():
    return np.zeros((720, 1280, 3), dtype=np.uint8)


class TestFistBumpDetection:
    def test_check_returns_none_on_cooldown(self, frame):
        fb = FistBumpInteraction(cooldown_s=60)
        fb._last_bump_time = time.time()  # just bumped
        assert fb.check_for_fist_bump(frame) is None

    def test_check_returns_none_on_no_frame(self, bump):
        assert bump.check_for_fist_bump(None) is None

    def test_check_detects_simulated_fist(self, bump, frame):
        # Force the hand detector to sim mode and set a hold timer
        detector = bump.get_or_create_detector()
        detector._simulate = True
        detector._fist_hold_start["Right"] = time.time() - 2.0
        result = bump.check_for_fist_bump(frame)
        assert result is not None
        assert result["confidence"] > 0.5
        assert "target_angles" in result
        assert len(result["target_angles"]) == 4

    def test_target_angles_vary_with_position(self, bump):
        # Center → j1 ≈ 90
        center = bump._compute_target_angles(0.5, 0.5)
        assert abs(center[0] - 90) < 5

        # Left in frame (x=0.2) → j1 > 90 (arm rotates right to face left)
        left = bump._compute_target_angles(0.2, 0.5)
        assert left[0] > 100

        # Right in frame (x=0.8) → j1 < 90
        right = bump._compute_target_angles(0.8, 0.5)
        assert right[0] < 80

    def test_target_angles_clamped(self, bump):
        extreme_left = bump._compute_target_angles(0.0, 0.0)
        assert 50 <= extreme_left[0] <= 130
        assert 45 <= extreme_left[1] <= 80

        extreme_right = bump._compute_target_angles(1.0, 1.0)
        assert 50 <= extreme_right[0] <= 130
        assert 45 <= extreme_right[1] <= 80


class TestFistBumpResponse:
    @pytest.mark.asyncio
    async def test_respond_moves_arm(self, bump):
        arm = MagicMock()
        arm.move_to = MagicMock(return_value=True)
        bump_info = {
            "center_x": 0.5, "center_y": 0.5,
            "pixel_x": 640, "pixel_y": 360,
            "confidence": 0.9, "hold_duration": 1.0,
            "handedness": "Right",
            "target_angles": (90, 55, 110, 90),
        }
        result = await bump.respond(bump_info, arm=arm)
        assert result is True
        arm.move_to.assert_called()
        assert bump.bump_count == 1

    @pytest.mark.asyncio
    async def test_respond_updates_personality(self, bump):
        from logic.personality import PersonalityEngine, EmotionalState
        personality = PersonalityEngine()
        personality._state.overall_mood = 0.4
        arm = MagicMock()
        arm.move_to = MagicMock(return_value=True)

        bump_info = {
            "center_x": 0.5, "center_y": 0.5,
            "pixel_x": 640, "pixel_y": 360,
            "confidence": 0.9, "hold_duration": 1.0,
            "handedness": "Right",
            "target_angles": BUMP_CENTER,
        }
        await bump.respond(bump_info, arm=arm, personality=personality)
        assert personality._state.emotional_state == EmotionalState.SATISFIED
        assert personality._state.overall_mood > 0.4  # mood boosted

    @pytest.mark.asyncio
    async def test_respond_reduces_override_streak(self, bump):
        from logic.personality import PersonalityEngine
        personality = PersonalityEngine()
        personality._state.override_streak = 3
        arm = MagicMock()
        arm.move_to = MagicMock(return_value=True)

        bump_info = {
            "center_x": 0.5, "center_y": 0.5,
            "pixel_x": 640, "pixel_y": 360,
            "confidence": 0.9, "hold_duration": 1.0,
            "handedness": "Right",
            "target_angles": BUMP_CENTER,
        }
        await bump.respond(bump_info, arm=arm, personality=personality)
        assert personality._state.override_streak < 3

    @pytest.mark.asyncio
    async def test_cooldown_prevents_double_bump(self):
        fb = FistBumpInteraction(cooldown_s=60)
        arm = MagicMock()
        arm.move_to = MagicMock(return_value=True)
        bump_info = {
            "center_x": 0.5, "center_y": 0.5,
            "pixel_x": 640, "pixel_y": 360,
            "confidence": 0.9, "hold_duration": 1.0,
            "handedness": "Right",
            "target_angles": BUMP_CENTER,
        }
        assert await fb.respond(bump_info, arm=arm) is True
        assert await fb.respond(bump_info, arm=arm) is False

    @pytest.mark.asyncio
    async def test_bump_count_increments(self, bump):
        arm = MagicMock()
        arm.move_to = MagicMock(return_value=True)
        bump_info = {
            "center_x": 0.5, "center_y": 0.5,
            "pixel_x": 640, "pixel_y": 360,
            "confidence": 0.9, "hold_duration": 1.0,
            "handedness": "Right",
            "target_angles": BUMP_CENTER,
        }
        await bump.respond(bump_info, arm=arm)
        await bump.respond(bump_info, arm=arm)
        assert bump.bump_count == 2


class TestFistBumpCheckAndRespond:
    @pytest.mark.asyncio
    async def test_check_and_respond_full_cycle(self, bump, frame):
        arm = MagicMock()
        arm.move_to = MagicMock(return_value=True)
        # Pre-seed the detector for simulation
        detector = bump.get_or_create_detector()
        detector._simulate = True
        detector._fist_hold_start["Right"] = time.time() - 2.0

        result = await bump.check_and_respond(frame, arm=arm)
        assert result is True
        assert bump.bump_count == 1

    @pytest.mark.asyncio
    async def test_check_and_respond_no_frame(self, bump):
        arm = MagicMock()
        result = await bump.check_and_respond(None, arm=arm)
        assert result is False


class TestFistBumpLegacy:
    def test_should_trigger_close_presence(self, bump):
        from vision.presence import PresenceInfo
        info = PresenceInfo(detected=True, closest_distance=30.0, looking_at_desk=True)
        assert bump.should_trigger(info) is True

    def test_should_trigger_far_presence(self, bump):
        from vision.presence import PresenceInfo
        info = PresenceInfo(detected=True, closest_distance=100.0, looking_at_desk=True)
        assert bump.should_trigger(info) is False

    def test_should_trigger_no_presence(self, bump):
        assert bump.should_trigger(None) is False

    @pytest.mark.asyncio
    async def test_legacy_trigger(self, bump):
        arm = MagicMock()
        arm.move_to = MagicMock(return_value=True)
        result = await bump.trigger(arm)
        assert result is True

    def test_shutdown(self, bump):
        bump.get_or_create_detector()
        bump.shutdown()
        assert bump._hand_detector is None


class TestFistBumpProperties:
    def test_on_cooldown(self):
        fb = FistBumpInteraction(cooldown_s=60)
        assert fb.on_cooldown is False
        fb._last_bump_time = time.time()
        assert fb.on_cooldown is True

    def test_bump_count_starts_zero(self):
        fb = FistBumpInteraction()
        assert fb.bump_count == 0
