"""Tests for move_near() and throw_away() in logic/object_interaction.py."""

import asyncio
from unittest.mock import MagicMock

import numpy as np
import pytest

from logic.object_interaction import ObjectInteraction, TrashZone, LABEL_ALIASES
from vision.yolo_detector import YoloDetector, Detection


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
def interaction(mock_arm, mock_gripper, mock_cal, sim_yolo):
    return ObjectInteraction(
        arm=mock_arm, gripper=mock_gripper,
        calibration=mock_cal, yolo_detector=sim_yolo,
    )


# --- move_near ---

class TestMoveNear:
    @pytest.mark.asyncio
    async def test_move_near_success(self, interaction, frame):
        # Sim YOLO has cup and laptop — move cup near laptop
        result = await interaction.move_near("cup", "laptop", lambda: frame)
        assert result.success is True
        assert result.action == "move_near"
        assert "cup" in result.object_label
        assert "laptop" in result.object_label

    @pytest.mark.asyncio
    async def test_move_near_source_not_found(self, interaction, frame):
        result = await interaction.move_near("banana", "laptop", lambda: frame)
        assert result.success is False
        assert "banana" in result.message

    @pytest.mark.asyncio
    async def test_move_near_target_not_found(self, interaction, frame):
        result = await interaction.move_near("cup", "banana", lambda: frame)
        assert result.success is False
        assert "banana" in result.message

    @pytest.mark.asyncio
    async def test_move_near_no_frame(self, interaction):
        result = await interaction.move_near("cup", "laptop", lambda: None)
        assert result.success is False

    def test_compute_placement_near_avoids_obstacles(self, interaction):
        """Smart placement should pick the side with most free space."""
        target = Detection(label="laptop", confidence=0.9, bbox=(300, 200, 500, 350))
        source = Detection(label="cup", confidence=0.9, bbox=(100, 100, 160, 200))
        # Obstacle on the right side
        obstacle = Detection(label="phone", confidence=0.8, bbox=(550, 200, 610, 320))

        pos = interaction._compute_placement_near(
            target, [target, source, obstacle], source, offset_px=80,
        )
        # Should NOT place on the right (where obstacle is)
        assert pos[0] < target.center_x  # placed on left side


# --- throw_away ---

class TestThrowAway:
    @pytest.mark.asyncio
    async def test_throw_away_disabled(self, interaction, frame):
        # Trash zone disabled by default
        result = await interaction.throw_away("cup", lambda: frame)
        assert result.success is False
        assert "not configured" in result.message

    @pytest.mark.asyncio
    async def test_throw_away_enabled(self, mock_arm, mock_gripper, mock_cal, sim_yolo, frame):
        trash = TrashZone(pixel_x=50, pixel_y=50, enabled=True)
        inter = ObjectInteraction(
            arm=mock_arm, gripper=mock_gripper,
            calibration=mock_cal, yolo_detector=sim_yolo,
            trash_zone=trash,
        )
        result = await inter.throw_away("cup", lambda: frame)
        assert result.success is True
        assert result.action == "throw_away"

    @pytest.mark.asyncio
    async def test_throw_away_not_found(self, mock_arm, mock_gripper, mock_cal, sim_yolo, frame):
        trash = TrashZone(pixel_x=50, pixel_y=50, enabled=True)
        inter = ObjectInteraction(
            arm=mock_arm, gripper=mock_gripper,
            calibration=mock_cal, yolo_detector=sim_yolo,
            trash_zone=trash,
        )
        result = await inter.throw_away("banana", lambda: frame)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_throw_away_forgets_from_memory(self, mock_arm, mock_gripper, mock_cal, sim_yolo, frame, tmp_path):
        from logic.object_memory import ObjectMemory
        memory = ObjectMemory(path=tmp_path / "mem.json")
        memory.observe("cup_0", "cup", (10, 20, 0))

        trash = TrashZone(pixel_x=50, pixel_y=50, enabled=True)
        inter = ObjectInteraction(
            arm=mock_arm, gripper=mock_gripper,
            calibration=mock_cal, yolo_detector=sim_yolo,
            object_memory=memory, trash_zone=trash,
        )
        await inter.throw_away("cup", lambda: frame)
        assert memory.get_object("cup_0") is None


# --- LABEL_ALIASES ---

class TestLabelAliases:
    def test_marker_aliases(self):
        assert "pen" in LABEL_ALIASES["marker"]

    def test_phone_aliases(self):
        assert "cell phone" in LABEL_ALIASES["phone"]

    def test_mug_cup_bidirectional(self):
        assert "cup" in LABEL_ALIASES["mug"]
        assert "mug" in LABEL_ALIASES["cup"]
