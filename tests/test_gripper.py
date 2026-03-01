"""Tests for hardware/gripper.py — Gripper abstraction."""

import pytest

from hardware.magnet_driver import MagnetDriver, MagnetState
from hardware.suction_driver import SuctionDriver, PumpState
from hardware.gripper import (MagnetGripperAdapter, SuctionGripperAdapter,
                              ServoGripper, create_gripper)


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
