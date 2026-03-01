"""Tests for hardware/suction_driver.py — SuctionDriver in simulation mode."""

import pytest

from hardware.suction_driver import SuctionDriver, PumpState, toggle_suction


@pytest.fixture
def pump():
    return SuctionDriver(simulate=True)


class TestSuctionDriver:
    def test_initial_state_off(self, pump):
        assert pump.state == PumpState.OFF
        assert pump.is_on is False

    def test_on(self, pump):
        assert pump.on() is True
        assert pump.state == PumpState.ON
        assert pump.is_on is True

    def test_off(self, pump):
        pump.on()
        assert pump.off() is True
        assert pump.state == PumpState.OFF

    def test_toggle(self, pump):
        pump.toggle(True)
        assert pump.is_on is True
        pump.toggle(False)
        assert pump.is_on is False

    def test_connect_simulation(self, pump):
        assert pump.connect() is True

    def test_context_manager(self):
        with SuctionDriver(simulate=True) as p:
            p.on()
            assert p.is_on
        assert p.state == PumpState.OFF

    def test_toggle_suction_helper(self):
        assert toggle_suction(True) is True
        assert toggle_suction(False) is True
