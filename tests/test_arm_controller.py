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
        p = ArmPosition(10, 20, 30, 40)
        assert p.as_tuple() == (10, 20, 30, 40)

    def test_from_tuple(self):
        p = ArmPosition.from_tuple((10, 20, 30, 40))
        assert p.j1 == 10 and p.j4 == 40

    def test_from_tuple_extra_values_ignored(self):
        p = ArmPosition.from_tuple((10, 20, 30, 40, 50, 60))
        assert p.as_tuple() == (10, 20, 30, 40)


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
        assert arm.position.as_tuple() == (-33, -2, -72, 43)

    def test_move_to(self, arm):
        result = arm.move_to((45, 60, -30, 0))
        assert result is True
        pos = arm.position.as_tuple()
        assert abs(pos[0] - 45) < 1
        assert abs(pos[1] - 60) < 1

    def test_move_to_clamps_angles(self, arm):
        result = arm.move_to((-200, 200, -100, 200))
        assert result is True
        pos = arm.position.as_tuple()
        assert pos[0] >= -162
        assert pos[1] <= 90

    def test_move_to_wrong_axis_count_raises(self, arm):
        with pytest.raises(ValueError, match="Expected 4"):
            arm.move_to((0, 0, 0))

    def test_move_axis(self, arm):
        arm.home()
        arm.move_axis(0, 45)
        assert abs(arm.position.j1 - 45) < 1

    def test_move_axis_invalid_raises(self, arm):
        with pytest.raises(ValueError, match="Invalid axis"):
            arm.move_axis(5, 0)

    def test_move_to_disconnected_returns_false(self):
        arm = ArmController(simulate=True)
        # Don't connect
        assert arm.move_to((0, 0, 0, 0)) is False

    def test_context_manager(self):
        with ArmController(simulate=True) as arm:
            assert arm.is_connected
        assert arm.state == ArmState.DISCONNECTED

    def test_reconnect_simulation(self, arm):
        assert arm.reconnect() is True
