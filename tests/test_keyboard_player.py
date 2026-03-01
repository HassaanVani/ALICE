"""Tests for hardware/keyboard_player.py — arm-based keyboard playing."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hardware.keyboard_player import KeyboardPlayer, KeyPosition


@pytest.fixture
def mock_arm():
    arm = MagicMock()
    arm.move_to = MagicMock()
    return arm


@pytest.fixture
def calibration_data():
    return {
        "press_depth": 10.0,
        "press_delay": 0.01,
        "travel_delay": 0.01,
        "keys": {
            "space": {"angles": [10.0, 20.0, 30.0, 40.0]},
            "left_arrow": {"angles": [15.0, 25.0, 35.0, 45.0]},
            "right_arrow": {"angles": [20.0, 30.0, 40.0, 50.0]},
            "up_arrow": {"angles": [25.0, 35.0, 45.0, 55.0]},
            "z": {"angles": [30.0, 40.0, 50.0, 60.0]},
            "c": {"angles": [35.0, 45.0, 55.0, 65.0]},
        },
    }


@pytest.fixture
def calibration_file(calibration_data):
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(calibration_data, f)
        return Path(f.name)


class TestLoadCalibration:
    def test_load_calibration_from_file(self, mock_arm, calibration_file):
        player = KeyboardPlayer(mock_arm, calibration_path=calibration_file)
        assert len(player.available_keys) == 6

    def test_load_calibration_missing_file(self, mock_arm):
        player = KeyboardPlayer(mock_arm, calibration_path=Path("/nonexistent.json"))
        assert player.available_keys == []

    def test_load_calibration_rejects_wrong_angle_count(self, mock_arm):
        data = {
            "keys": {
                "good": {"angles": [1.0, 2.0, 3.0, 4.0]},
                "bad_3": {"angles": [1.0, 2.0, 3.0]},
                "bad_5": {"angles": [1.0, 2.0, 3.0, 4.0, 5.0]},
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = Path(f.name)
        player = KeyboardPlayer(mock_arm, calibration_path=path)
        assert player.available_keys == ["good"]


class TestAvailableKeys:
    def test_available_keys(self, mock_arm, calibration_file):
        player = KeyboardPlayer(mock_arm, calibration_path=calibration_file)
        keys = player.available_keys
        assert isinstance(keys, list)
        assert "space" in keys
        assert "left_arrow" in keys
        assert len(keys) == 6


class TestPressKey:
    @pytest.mark.asyncio
    async def test_press_key_unknown_returns_false(self, mock_arm, calibration_file):
        player = KeyboardPlayer(mock_arm, calibration_path=calibration_file)
        result = await player.press_key("nonexistent_key")
        assert result is False
        mock_arm.move_to.assert_not_called()

    @pytest.mark.asyncio
    async def test_press_key_moves_arm(self, mock_arm, calibration_file, calibration_data):
        player = KeyboardPlayer(mock_arm, calibration_path=calibration_file)
        result = await player.press_key("space")
        assert result is True

        calls = [c.args[0] for c in mock_arm.move_to.call_args_list]
        hover = tuple(calibration_data["keys"]["space"]["angles"])
        pressed = list(hover)
        pressed[2] = pressed[2] - calibration_data["press_depth"]
        pressed = tuple(pressed)

        # 3 moves: hover, press (J3 lowered), hover again
        assert len(calls) == 3
        assert calls[0] == hover
        assert calls[1] == pressed
        assert calls[2] == hover


class TestExecuteSequence:
    @pytest.mark.asyncio
    async def test_execute_sequence(self, mock_arm, calibration_file):
        player = KeyboardPlayer(mock_arm, calibration_path=calibration_file)
        count = await player.execute_sequence(["space", "left_arrow", "z"])
        assert count == 3
        # 3 keys × 3 move_to calls each = 9
        assert mock_arm.move_to.call_count == 9

    @pytest.mark.asyncio
    async def test_execute_sequence_skips_unknown(self, mock_arm, calibration_file):
        player = KeyboardPlayer(mock_arm, calibration_path=calibration_file)
        count = await player.execute_sequence(["space", "INVALID", "z"])
        assert count == 2
