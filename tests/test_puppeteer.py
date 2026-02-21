"""Tests for hardware/puppeteer.py — neural activation encoding."""

import numpy as np
import pytest

from hardware.puppeteer import (
    PuppeteerState, ArmFrame,
    encode_as_neural_activations, get_websocket_payload,
)


@pytest.fixture
def frame():
    return ArmFrame(
        timestamp=1000.0,
        angles=(90.0, 90.0, 90.0, 90.0, 90.0),
        velocities=(10.0, -5.0, 0.0, 3.0, 1.0),
        accelerations=(100.0, -50.0, 0.0, 20.0, 5.0),
    )


class TestPuppeteerState:
    def test_states_exist(self):
        assert PuppeteerState.IDLE.value == "idle"
        assert PuppeteerState.LIVE.value == "live"
        assert PuppeteerState.RECORDING.value == "recording"
        assert PuppeteerState.PLAYBACK.value == "playback"


class TestEncodeAsNeuralActivations:
    def test_returns_all_regions(self, frame):
        activations = encode_as_neural_activations(frame)
        expected_keys = {"sensory_input", "motor_cortex", "premotor", "cerebellum", "basal_ganglia"}
        assert set(activations.keys()) == expected_keys

    def test_all_float32(self, frame):
        activations = encode_as_neural_activations(frame)
        for name, arr in activations.items():
            assert arr.dtype == np.float32, f"{name} has dtype {arr.dtype}"

    def test_sensory_input_shape(self, frame):
        activations = encode_as_neural_activations(frame)
        assert activations["sensory_input"].shape == (5,)

    def test_motor_cortex_shape(self, frame):
        activations = encode_as_neural_activations(frame)
        # outer product of 5-dim vector = 25 elements
        assert activations["motor_cortex"].shape == (25,)


class TestGetWebsocketPayload:
    def test_returns_bytes(self, frame):
        payload = get_websocket_payload(frame)
        assert isinstance(payload, bytes)
        assert len(payload) > 0

    def test_payload_starts_with_count(self, frame):
        import struct
        payload = get_websocket_payload(frame)
        count = struct.unpack("I", payload[:4])[0]
        assert count == 5  # 5 activation regions
