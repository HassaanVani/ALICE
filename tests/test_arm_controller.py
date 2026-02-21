"""Tests for hardware/arm_controller.py — ArmController in simulation mode."""

import pytest

from hardware.arm_controller import ArmController, ArmState, ArmPosition


@pytest.fixture
def arm():
    a = ArmController(simulate=True)
    a.connect()
    return a


class TestArmPosition:
    def test_as_tuple(self):
        p = ArmPosition(10, 20, 30, 40, 50)
        assert p.as_tuple() == (10, 20, 30, 40, 50)

    def test_from_tuple(self):
        p = ArmPosition.from_tuple((10, 20, 30, 40, 50))
        assert p.base == 10 and p.wrist_roll == 50

    def test_from_tuple_extra_values_ignored(self):
        p = ArmPosition.from_tuple((10, 20, 30, 40, 50, 60, 70))
        assert p.as_tuple() == (10, 20, 30, 40, 50)


class TestArmController:
    def test_connect_simulation(self, arm):
        assert arm.state == ArmState.IDLE
        assert arm.is_connected is True

    def test_disconnect(self, arm):
        arm.disconnect()
        assert arm.state == ArmState.DISCONNECTED
        assert arm.is_connected is False

    def test_home(self, arm):
        result = arm.home()
        assert result is True
        assert arm.position.as_tuple() == (90, 90, 90, 90, 90)

    def test_move_to(self, arm):
        result = arm.move_to((45, 60, 90, 120, 90))
        assert result is True
        pos = arm.position.as_tuple()
        assert abs(pos[0] - 45) < 1
        assert abs(pos[1] - 60) < 1

    def test_move_to_clamps_angles(self, arm):
        result = arm.move_to((-10, 200, 90, 90, 90))
        assert result is True
        pos = arm.position.as_tuple()
        assert pos[0] >= 0
        assert pos[1] <= 180

    def test_move_to_wrong_axis_count_raises(self, arm):
        with pytest.raises(ValueError, match="Expected 5"):
            arm.move_to((90, 90, 90))

    def test_move_axis(self, arm):
        arm.home()
        arm.move_axis(0, 45)
        assert abs(arm.position.base - 45) < 1

    def test_move_axis_invalid_raises(self, arm):
        with pytest.raises(ValueError, match="Invalid axis"):
            arm.move_axis(5, 90)

    def test_move_to_disconnected_returns_false(self):
        arm = ArmController(simulate=True)
        # Don't connect
        assert arm.move_to((90, 90, 90, 90, 90)) is False

    def test_context_manager(self):
        with ArmController(simulate=True) as arm:
            assert arm.is_connected
        assert arm.state == ArmState.DISCONNECTED

    def test_reconnect_simulation(self, arm):
        assert arm.reconnect() is True
