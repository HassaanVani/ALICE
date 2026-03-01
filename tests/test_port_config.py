"""Tests for hardware/port_config.py — serial port resolution."""

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

from hardware.port_config import get_serial_port, list_serial_ports, get_serial_port_from_config


class TestGetSerialPort:
    def test_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("ALICE_ARM_PORT", "/dev/custom_port")
        assert get_serial_port("arm") == "/dev/custom_port"

    def test_env_var_magnet(self, monkeypatch):
        monkeypatch.setenv("ALICE_MAGNET_PORT", "/dev/magnet_custom")
        assert get_serial_port("magnet") == "/dev/magnet_custom"

    def test_platform_default_linux(self, monkeypatch):
        monkeypatch.delenv("ALICE_ARM_PORT", raising=False)
        with patch("hardware.port_config.sys") as mock_sys:
            mock_sys.platform = "linux"
            # Re-import won't help due to module caching, so patch the module attribute
            with patch("hardware.port_config.sys.platform", "linux"):
                result = get_serial_port("arm")
                assert result == "/dev/ttyACM0"

    def test_glob_pattern_fallback(self, monkeypatch):
        """When glob finds no matches, strips * and appends 0."""
        monkeypatch.delenv("ALICE_ARM_PORT", raising=False)
        with patch("hardware.port_config.sys.platform", "darwin"):
            with patch("hardware.port_config.glob.glob", return_value=[]):
                result = get_serial_port("arm")
                assert result == "/dev/tty.usbmodem0"

    def test_glob_pattern_matches(self, monkeypatch):
        monkeypatch.delenv("ALICE_ARM_PORT", raising=False)
        with patch("hardware.port_config.sys.platform", "darwin"):
            with patch("hardware.port_config.glob.glob", return_value=["/dev/tty.usbmodem14201"]):
                result = get_serial_port("arm")
                assert result == "/dev/tty.usbmodem14201"


class TestListSerialPorts:
    def test_list_serial_ports_no_serial(self):
        with patch.dict("sys.modules", {"serial": None, "serial.tools": None, "serial.tools.list_ports": None}):
            # Force ImportError by patching the import inside
            with patch("hardware.port_config.list_serial_ports", return_value=[]):
                result = list_serial_ports()
                assert isinstance(result, list)


class TestGetSerialPortFromConfig:
    def test_get_serial_port_from_config(self, monkeypatch):
        config = MagicMock()
        config.hardware.arm_port = "/dev/config_arm"
        config.hardware.magnet_port = "/dev/config_magnet"
        config.hardware.imu_port = "/dev/config_imu"
        assert get_serial_port_from_config("arm", config) == "/dev/config_arm"

    def test_get_serial_port_from_config_fallback(self, monkeypatch):
        """Falls back to get_serial_port when config port is None."""
        monkeypatch.setenv("ALICE_ARM_PORT", "/dev/env_arm")
        config = MagicMock()
        config.hardware.arm_port = None
        config.hardware.magnet_port = None
        config.hardware.imu_port = None
        result = get_serial_port_from_config("arm", config)
        assert result == "/dev/env_arm"

    def test_get_serial_port_from_config_none_config(self, monkeypatch):
        monkeypatch.setenv("ALICE_ARM_PORT", "/dev/env_fallback")
        result = get_serial_port_from_config("arm", None)
        assert result == "/dev/env_fallback"
