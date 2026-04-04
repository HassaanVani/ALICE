"""Tests for hardware/gripper.py — Gripper abstraction."""

from unittest.mock import MagicMock, patch

import pytest

from hardware.magnet_driver import MagnetDriver, MagnetState
from hardware.suction_driver import SuctionDriver, PumpState
from hardware.gripper import (MagnetGripperAdapter, SuctionGripperAdapter,
                              ServoGripper, ParallelGripper, GripPreset,
                              GRIP_PRESETS, create_gripper)
from logic.personality import ActionOrigin, PersonalityEngine


@pytest.fixture
def magnet():
    return MagnetDriver(simulate=True)


@pytest.fixture
def magnet_gripper(magnet):
    return MagnetGripperAdapter(magnet)


@pytest.fixture
def suction():
    return SuctionDriver(simulate=True)


@pytest.fixture
def suction_gripper(suction):
    return SuctionGripperAdapter(suction)


@pytest.fixture
def servo_gripper():
    return ServoGripper(simulate=True)


class TestMagnetGripperAdapter:
    def test_open(self, magnet_gripper, magnet):
        magnet_gripper.open()
        assert magnet_gripper.get_position() == 0.0
        assert magnet.state == MagnetState.OFF

    def test_close(self, magnet_gripper, magnet):
        magnet_gripper.close()
        assert magnet_gripper.get_position() == 1.0
        assert magnet.state == MagnetState.ON

    def test_set_position_threshold(self, magnet_gripper, magnet):
        magnet_gripper.set_position(0.7)
        assert magnet.state == MagnetState.ON
        magnet_gripper.set_position(0.3)
        assert magnet.state == MagnetState.OFF

    def test_is_not_proportional(self, magnet_gripper):
        assert magnet_gripper.is_proportional is False

    def test_clamps_position(self, magnet_gripper):
        magnet_gripper.set_position(2.0)
        assert magnet_gripper.get_position() == 1.0
        magnet_gripper.set_position(-1.0)
        assert magnet_gripper.get_position() == 0.0


class TestSuctionGripperAdapter:
    def test_open(self, suction_gripper, suction):
        suction_gripper.open()
        assert suction_gripper.get_position() == 0.0
        assert suction.state == PumpState.OFF

    def test_close(self, suction_gripper, suction):
        suction_gripper.close()
        assert suction_gripper.get_position() == 1.0
        assert suction.state == PumpState.ON

    def test_set_position_threshold(self, suction_gripper, suction):
        suction_gripper.set_position(0.7)
        assert suction.state == PumpState.ON
        suction_gripper.set_position(0.3)
        assert suction.state == PumpState.OFF

    def test_is_not_proportional(self, suction_gripper):
        assert suction_gripper.is_proportional is False

    def test_clamps_position(self, suction_gripper):
        suction_gripper.set_position(2.0)
        assert suction_gripper.get_position() == 1.0
        suction_gripper.set_position(-1.0)
        assert suction_gripper.get_position() == 0.0


class TestServoGripper:
    def test_open_close(self, servo_gripper):
        servo_gripper.open()
        assert servo_gripper.get_position() == 0.0
        servo_gripper.close()
        assert servo_gripper.get_position() == 1.0

    def test_is_proportional(self, servo_gripper):
        assert servo_gripper.is_proportional is True

    def test_set_position(self, servo_gripper):
        servo_gripper.set_position(0.5)
        assert servo_gripper.get_position() == 0.5


class TestCreateGripper:
    def test_create_magnet_gripper(self, magnet):
        g = create_gripper("magnet", magnet_driver=magnet)
        assert isinstance(g, MagnetGripperAdapter)

    def test_create_servo_gripper(self):
        g = create_gripper("servo", simulate=True)
        assert isinstance(g, ServoGripper)

    def test_create_suction_gripper(self, suction):
        g = create_gripper("suction", suction_driver=suction)
        assert isinstance(g, SuctionGripperAdapter)

    def test_create_unknown_raises(self):
        with pytest.raises(ValueError):
            create_gripper("unknown_type")

    def test_create_parallel_gripper(self):
        g = create_gripper("parallel", simulate=True)
        assert isinstance(g, ParallelGripper)
        assert g.is_proportional is True


# --- ParallelGripper tests ---

@pytest.fixture
def parallel_gripper():
    return ParallelGripper(simulate=True)


@pytest.fixture
def parallel_gripper_with_personality():
    personality = PersonalityEngine()
    return ParallelGripper(simulate=True, personality=personality)


class TestParallelGripperSimulate:
    def test_open(self, parallel_gripper):
        assert parallel_gripper.open() is True
        assert parallel_gripper.get_position() == 0.0

    def test_close(self, parallel_gripper):
        assert parallel_gripper.close() is True
        assert parallel_gripper.get_position() == 1.0

    def test_set_position_midpoint(self, parallel_gripper):
        assert parallel_gripper.set_position(0.5) is True
        assert parallel_gripper.get_position() == pytest.approx(0.5, abs=0.02)

    def test_set_position_clamps_high(self, parallel_gripper):
        parallel_gripper.set_position(2.0)
        assert parallel_gripper.get_position() == 1.0

    def test_set_position_clamps_low(self, parallel_gripper):
        parallel_gripper.set_position(-1.0)
        assert parallel_gripper.get_position() == 0.0

    def test_set_position_zero_is_open(self, parallel_gripper):
        parallel_gripper.set_position(0.0)
        assert parallel_gripper.get_position() == 0.0

    def test_set_position_one_is_closed(self, parallel_gripper):
        parallel_gripper.set_position(1.0)
        assert parallel_gripper.get_position() == 1.0

    def test_is_proportional(self, parallel_gripper):
        assert parallel_gripper.is_proportional is True

    def test_set_cobot(self, parallel_gripper):
        mock_cobot = MagicMock()
        parallel_gripper.set_cobot(mock_cobot)
        assert parallel_gripper._cobot is mock_cobot

    def test_no_cobot_non_simulate_returns_false(self):
        g = ParallelGripper(simulate=False, cobot=None)
        assert g.open() is False


class TestGripPresets:
    def test_cup_preset(self):
        preset = GRIP_PRESETS["cup"]
        assert preset.name == "cup"
        assert preset.grip_value == 60
        assert preset.approach_speed == 30

    def test_pen_preset(self):
        preset = GRIP_PRESETS["pen"]
        assert preset.grip_value == 80
        assert preset.approach_speed == 50

    def test_book_preset(self):
        preset = GRIP_PRESETS["book"]
        assert preset.grip_value == 40
        assert preset.approach_speed == 30

    def test_tissue_preset(self):
        preset = GRIP_PRESETS["tissue"]
        assert preset.grip_value == 90
        assert preset.approach_speed == 70

    def test_phone_preset(self):
        preset = GRIP_PRESETS["phone"]
        assert preset.grip_value == 75
        assert preset.approach_speed == 40

    def test_default_preset(self):
        preset = GRIP_PRESETS["default"]
        assert preset.grip_value == 70
        assert preset.approach_speed == 50

    def test_all_presets_have_hold_verify(self):
        for name, preset in GRIP_PRESETS.items():
            assert hasattr(preset, "hold_verify_ms")
            assert preset.hold_verify_ms >= 0

    def test_grip_preset_dataclass(self):
        custom = GripPreset("custom", grip_value=55, approach_speed=45, hold_verify_ms=300)
        assert custom.name == "custom"
        assert custom.grip_value == 55
        assert custom.approach_speed == 45
        assert custom.hold_verify_ms == 300


class TestGripObjectWithPersonality:
    def test_grip_known_object(self, parallel_gripper):
        """Grip without personality — uses base preset speed."""
        assert parallel_gripper.grip_object("cup") is True
        # Cup preset: grip_value=60 -> position = 1.0 - 60/100 = 0.4
        assert parallel_gripper.get_position() == pytest.approx(0.4, abs=0.02)

    def test_grip_unknown_falls_back_to_default(self, parallel_gripper):
        assert parallel_gripper.grip_object("banana") is True
        # Default preset: grip_value=70 -> position = 1.0 - 70/100 = 0.3
        assert parallel_gripper.get_position() == pytest.approx(0.3, abs=0.02)

    def test_grip_override_halves_speed(self, parallel_gripper_with_personality):
        """ActionOrigin.OVERRIDE should halve approach speed."""
        g = parallel_gripper_with_personality
        # Cup base speed = 30; override -> 30 * 0.5 = 15
        with patch.object(g, '_send', wraps=g._send) as mock_send:
            g.grip_object("cup", origin=ActionOrigin.OVERRIDE)
            mock_send.assert_called_once_with(60, 15)

    def test_grip_self_initiated_faster(self, parallel_gripper_with_personality):
        """ActionOrigin.SELF_INITIATED should multiply speed by 1.3."""
        g = parallel_gripper_with_personality
        # Cup base speed = 30; self_initiated -> 30 * 1.3 = 39
        with patch.object(g, '_send', wraps=g._send) as mock_send:
            g.grip_object("cup", origin=ActionOrigin.SELF_INITIATED)
            mock_send.assert_called_once_with(60, 39)

    def test_grip_user_requested_uses_base_speed(self, parallel_gripper_with_personality):
        """ActionOrigin.USER_REQUESTED should use base speed unmodified."""
        g = parallel_gripper_with_personality
        with patch.object(g, '_send', wraps=g._send) as mock_send:
            g.grip_object("pen", origin=ActionOrigin.USER_REQUESTED)
            mock_send.assert_called_once_with(80, 50)

    def test_grip_no_personality_no_origin_uses_base(self, parallel_gripper):
        """Without personality engine, origin is ignored — base speed used."""
        with patch.object(parallel_gripper, '_send', wraps=parallel_gripper._send) as mock_send:
            parallel_gripper.grip_object("cup", origin=ActionOrigin.OVERRIDE)
            # No personality => base speed 30 used as-is
            mock_send.assert_called_once_with(60, 30)


class TestNudge:
    def test_nudge_returns_true_simulate(self, parallel_gripper):
        assert parallel_gripper.nudge() is True

    def test_nudge_ends_open(self, parallel_gripper):
        """After nudge, gripper should be back open (position ~0.0)."""
        parallel_gripper.nudge()
        assert parallel_gripper.get_position() == 0.0

    def test_nudge_calls_send_twice(self, parallel_gripper):
        """Nudge should close slightly then reopen."""
        with patch.object(parallel_gripper, '_send', wraps=parallel_gripper._send) as mock_send:
            parallel_gripper.nudge()
            assert mock_send.call_count == 2
            # First call: close slightly (grip_value=60, speed=40)
            mock_send.assert_any_call(60, 40)
            # Second call: reopen (grip_value=100, speed=40)
            mock_send.assert_any_call(100, 40)
