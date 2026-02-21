"""Tests for hardware/magnet_driver.py — MagnetDriver in simulation mode."""

import pytest

from hardware.magnet_driver import MagnetDriver, MagnetState, toggle_magnet


@pytest.fixture
def magnet():
    return MagnetDriver(simulate=True)


class TestMagnetDriver:
    def test_initial_state_off(self, magnet):
        assert magnet.state == MagnetState.OFF
        assert magnet.is_on is False

    def test_on(self, magnet):
        assert magnet.on() is True
        assert magnet.state == MagnetState.ON
        assert magnet.is_on is True

    def test_off(self, magnet):
        magnet.on()
        assert magnet.off() is True
        assert magnet.state == MagnetState.OFF

    def test_toggle(self, magnet):
        magnet.toggle(True)
        assert magnet.is_on is True
        magnet.toggle(False)
        assert magnet.is_on is False

    def test_connect_simulation(self, magnet):
        assert magnet.connect() is True

    def test_context_manager(self):
        with MagnetDriver(simulate=True) as m:
            m.on()
            assert m.is_on
        assert m.state == MagnetState.OFF

    def test_toggle_magnet_helper(self):
        assert toggle_magnet(True) is True
        assert toggle_magnet(False) is True
