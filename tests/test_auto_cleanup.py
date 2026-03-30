"""Tests for autonomous cleanup in logic/object_interaction.py."""

import time
from unittest.mock import MagicMock

import numpy as np
import pytest

from logic.object_interaction import (
    ObjectInteraction, TrashZone, TRASH_ELIGIBLE, AUTO_CLEANUP_COOLDOWN,
)
from vision.yolo_detector import YoloDetector


@pytest.fixture
def sim_yolo():
    y = YoloDetector()
    y._simulate = True
    return y


@pytest.fixture
def mock_arm():
    arm = MagicMock()
    arm.move_to = MagicMock(return_value=True)
    return arm


@pytest.fixture
def mock_gripper():
    g = MagicMock()
    g.close = MagicMock()
    g.open = MagicMock()
    return g


@pytest.fixture
def mock_cal():
    c = MagicMock()
    c.pixel_to_arm = MagicMock(return_value=(90, 70, 90, 90))
    return c


@pytest.fixture
def frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def interaction_with_trash(mock_arm, mock_gripper, mock_cal, sim_yolo):
    trash = TrashZone(pixel_x=50, pixel_y=50, enabled=True)
    return ObjectInteraction(
        arm=mock_arm, gripper=mock_gripper,
        calibration=mock_cal, yolo_detector=sim_yolo,
        trash_zone=trash,
    )


class TestScanForTrash:
    def test_finds_nothing_in_sim(self, interaction_with_trash, frame):
        # Sim YOLO returns cup, laptop, cell phone — none are trash
        found = interaction_with_trash.scan_for_trash(lambda: frame)
        assert len(found) == 0

    def test_no_frame(self, interaction_with_trash):
        found = interaction_with_trash.scan_for_trash(lambda: None)
        assert found == []


class TestShouldAutoCleanup:
    def test_not_when_trash_disabled(self, mock_arm, mock_gripper, mock_cal, sim_yolo):
        trash = TrashZone(enabled=False)
        inter = ObjectInteraction(
            arm=mock_arm, gripper=mock_gripper,
            calibration=mock_cal, yolo_detector=sim_yolo,
            trash_zone=trash,
        )
        from logic.personality import PersonalityEngine
        personality = PersonalityEngine()
        personality._state.overall_mood = 0.9
        assert inter.should_auto_cleanup(personality=personality) is False

    def test_not_on_cooldown(self, interaction_with_trash):
        from logic.personality import PersonalityEngine
        personality = PersonalityEngine()
        personality._state.overall_mood = 0.9
        personality._last_action_time = time.time() - 10
        # Just cleaned
        assert interaction_with_trash.should_auto_cleanup(
            personality=personality, last_cleanup_time=time.time(),
        ) is False

    def test_not_when_annoyed(self, interaction_with_trash):
        from logic.personality import PersonalityEngine, EmotionalState
        personality = PersonalityEngine()
        personality._state.overall_mood = 0.9
        personality._state.emotional_state = EmotionalState.ANNOYED
        personality._last_action_time = time.time() - 10
        assert interaction_with_trash.should_auto_cleanup(
            personality=personality, last_cleanup_time=0,
        ) is False

    def test_not_in_flow(self, interaction_with_trash):
        from logic.personality import PersonalityEngine
        personality = PersonalityEngine()
        personality._state.overall_mood = 0.9
        personality._state.is_in_flow = True
        personality._last_action_time = time.time() - 10
        assert interaction_with_trash.should_auto_cleanup(
            personality=personality, last_cleanup_time=0,
        ) is False

    def test_not_when_low_mood(self, interaction_with_trash):
        from logic.personality import PersonalityEngine
        personality = PersonalityEngine()
        personality._state.overall_mood = 0.2
        personality._last_action_time = time.time() - 10
        results = [
            interaction_with_trash.should_auto_cleanup(
                personality=personality, last_cleanup_time=0,
            )
            for _ in range(50)
        ]
        assert not any(results)

    def test_triggers_with_good_mood(self, interaction_with_trash):
        from logic.personality import PersonalityEngine, EmotionalState
        personality = PersonalityEngine()
        personality._state.overall_mood = 0.85
        personality._state.emotional_state = EmotionalState.CONTENT
        personality._last_action_time = time.time() - 10
        # High mood = high chance — should trigger at least once in 100 tries
        results = [
            interaction_with_trash.should_auto_cleanup(
                personality=personality, last_cleanup_time=0,
            )
            for _ in range(100)
        ]
        assert any(results)


class TestAutoCleanup:
    @pytest.mark.asyncio
    async def test_desk_is_clean(self, interaction_with_trash, frame):
        # Sim YOLO has no trash items
        result = await interaction_with_trash.auto_cleanup(lambda: frame)
        assert result.success is True
        assert "desk is clean" in result.message

    @pytest.mark.asyncio
    async def test_cleanup_with_personality(self, interaction_with_trash, frame):
        from logic.personality import PersonalityEngine, EmotionalState
        personality = PersonalityEngine()
        personality._state.overall_mood = 0.5
        # Even with no trash found, mood shouldn't drop
        result = await interaction_with_trash.auto_cleanup(
            lambda: frame, personality=personality,
        )
        assert personality._state.overall_mood >= 0.5


class TestTrashEligible:
    def test_tissue_is_trash(self):
        assert "tissue" in TRASH_ELIGIBLE

    def test_wrapper_is_trash(self):
        assert "wrapper" in TRASH_ELIGIBLE

    def test_cup_is_not_trash(self):
        assert "cup" not in TRASH_ELIGIBLE

    def test_laptop_is_not_trash(self):
        assert "laptop" not in TRASH_ELIGIBLE


class TestAutoCleanupCooldown:
    def test_cooldown_value(self):
        assert AUTO_CLEANUP_COOLDOWN == 60.0
