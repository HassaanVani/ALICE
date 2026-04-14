"""Tests for config.py — AliceConfig loader."""

import pytest

from config import (
    AliceConfig,
    _deep_merge,
    _apply_env_overrides,
    _dict_to_config,
    load_config,
)


class TestDefaultConfig:
    def test_default_mode_is_idle(self):
        cfg = AliceConfig()
        assert cfg.mode == "idle"

    def test_default_simulate_is_true(self):
        cfg = AliceConfig()
        assert cfg.simulate is True


class TestDeepMerge:
    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}}
        override = {"x": {"b": 3}}
        result = _deep_merge(base, override)
        assert result == {"x": {"a": 1, "b": 3}}

    def test_override_replaces_non_dict(self):
        base = {"x": {"a": 1}}
        override = {"x": "flat"}
        result = _deep_merge(base, override)
        assert result == {"x": "flat"}


class TestEnvOverrides:
    def test_mode_override(self, monkeypatch):
        monkeypatch.setenv("ALICE_MODE", "demo")
        data = _apply_env_overrides({})
        assert data["mode"] == "demo"

    def test_simulate_false_coerced(self, monkeypatch):
        monkeypatch.setenv("ALICE_SIMULATE", "false")
        data = _apply_env_overrides({})
        assert data["simulate"] is False

    def test_tensor_port_coerced_to_int(self, monkeypatch):
        monkeypatch.setenv("ALICE_TENSOR_PORT", "9999")
        data = _apply_env_overrides({})
        assert data["websocket"]["tensor_port"] == 9999
        assert isinstance(data["websocket"]["tensor_port"], int)

    def test_arm_port_preserves_string(self, monkeypatch):
        monkeypatch.setenv("ALICE_ARM_PORT", "/dev/ttyUSB0")
        data = _apply_env_overrides({})
        assert data["hardware"]["arm"]["port"] == "/dev/ttyUSB0"

    def test_cli_overrides_take_priority(self, monkeypatch):
        monkeypatch.setenv("ALICE_MODE", "demo")
        from pathlib import Path
        cfg = load_config(
            yaml_path=Path("/nonexistent_alice_test.yaml"),
            cli_overrides={"mode": "puppeteer"},
        )
        assert cfg.mode == "puppeteer"


class TestDictToConfig:
    def test_hardware_mapping(self):
        data = {"hardware": {"arm": {"port": "/dev/cu.usbserial", "baudrate": 9600}}}
        cfg = _dict_to_config(data)
        assert cfg.hardware.arm_port == "/dev/cu.usbserial"
        assert cfg.hardware.arm_baudrate == 9600

    def test_cameras_mapping(self):
        data = {"cameras": {"arm_mounted": {"device_id": 2, "width": 640}}}
        cfg = _dict_to_config(data)
        assert cfg.arm_camera.device_id == 2
        assert cfg.arm_camera.width == 640

    def test_cameras_backward_compat(self):
        """Old 'overhead' key still works."""
        data = {"cameras": {"overhead": {"device_id": 3, "width": 800}}}
        cfg = _dict_to_config(data)
        assert cfg.arm_camera.device_id == 3
        assert cfg.arm_camera.width == 800

    def test_websocket_mapping(self):
        data = {"websocket": {"tensor_port": 1234}}
        cfg = _dict_to_config(data)
        assert cfg.websocket.tensor_port == 1234
