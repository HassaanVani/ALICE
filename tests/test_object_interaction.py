"""Tests for logic/object_interaction.py — fetch, hand_over, nudge, put_away."""

import asyncio
from unittest.mock import MagicMock

import numpy as np
import pytest

from logic.object_interaction import ObjectInteraction, InteractionResult, HandoffZone


@pytest.fixture
def mock_arm():
    arm = MagicMock()
    arm.move_to = MagicMock(return_value=True)
    return arm


@pytest.fixture
def mock_gripper():
    gripper = MagicMock()
    gripper.close = MagicMock()
    gripper.open = MagicMock()
    return gripper


@pytest.fixture
def mock_calibration():
    cal = MagicMock()
    cal.pixel_to_arm = MagicMock(return_value=(90, 70, 90, 90))
    return cal


@pytest.fixture
def sim_yolo():
    from vision.yolo_detector import YoloDetector
    y = YoloDetector()
    y._simulate = True
    return y


@pytest.fixture
def frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def interaction(mock_arm, mock_gripper, mock_calibration, sim_yolo):
    return ObjectInteraction(
        arm=mock_arm, gripper=mock_gripper,
        calibration=mock_calibration, yolo_detector=sim_yolo,
    )


class TestFindObject:
    def test_find_existing_object(self, interaction, frame):
        # Sim YOLO returns cup, laptop, cell phone
        pos = interaction._find_object("cup", frame)
        assert pos is not None
        assert len(pos) == 2

    def test_find_nonexistent_object(self, interaction, frame):
        pos = interaction._find_object("banana", frame)
        assert pos is None

    def test_alias_matching(self, interaction, frame):
        # "mug" should match "cup" via alias
        pos = interaction._find_object("mug", frame)
        assert pos is not None


class TestFetch:
    @pytest.mark.asyncio
    async def test_fetch_success(self, interaction, mock_arm, mock_gripper, frame):
        result = await interaction.fetch("cup", lambda: frame)
        assert result.success is True
        assert result.action == "fetch"
        assert result.object_label == "cup"
        mock_arm.move_to.assert_called()
        mock_gripper.close.assert_called()

    @pytest.mark.asyncio
    async def test_fetch_not_found(self, interaction, frame):
        result = await interaction.fetch("banana", lambda: frame)
        assert result.success is False
        assert "can't find" in result.message

    @pytest.mark.asyncio
    async def test_fetch_no_frame(self, interaction):
        result = await interaction.fetch("cup", lambda: None)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_fetch_custom_target(self, interaction, mock_calibration, frame):
        result = await interaction.fetch("cup", lambda: frame, place_px=(100, 200))
        assert result.success is True
        # Calibration should be called with the custom target
        calls = mock_calibration.pixel_to_arm.call_args_list
        assert any(c[0][:2] == (100, 200) for c in calls)


class TestHandOver:
    @pytest.mark.asyncio
    async def test_hand_over_success(self, interaction, mock_arm, mock_gripper, frame):
        result = await interaction.hand_over("cup", lambda: frame)
        assert result.success is True
        assert result.action == "hand_over"
        mock_gripper.close.assert_called()
        mock_gripper.open.assert_called()

    @pytest.mark.asyncio
    async def test_hand_over_not_found(self, interaction, frame):
        result = await interaction.hand_over("banana", lambda: frame)
        assert result.success is False


class TestNudge:
    @pytest.mark.asyncio
    async def test_nudge(self, interaction, frame):
        result = await interaction.nudge("cup", lambda: frame, dx_px=50)
        assert result.success is True
        assert result.action == "nudge"


class TestPutAway:
    @pytest.mark.asyncio
    async def test_put_away_default_position(self, interaction, frame):
        result = await interaction.put_away("cup", lambda: frame)
        assert result.success is True
        assert result.action == "put_away"

    @pytest.mark.asyncio
    async def test_put_away_with_memory(self, interaction, frame, tmp_path):
        from logic.object_memory import ObjectMemory
        memory = ObjectMemory(path=tmp_path / "mem.json")
        memory.observe("cup_0", "cup", (10, 20, 0))
        memory.record_placement("cup_0", (10, 20, 0))
        interaction._memory = memory

        result = await interaction.put_away("cup", lambda: frame)
        assert result.success is True


class TestInteractionResult:
    def test_fields(self):
        r = InteractionResult(success=True, action="fetch", object_label="cup",
                              message="done", duration_s=1.5)
        assert r.success
        assert r.action == "fetch"
        assert r.duration_s == 1.5


class TestHandoffZone:
    def test_defaults(self):
        h = HandoffZone()
        assert h.pixel_x == 320
        assert h.pixel_y == 400
        assert h.timeout_s == 8.0
