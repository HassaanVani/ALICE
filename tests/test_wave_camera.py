"""Tests for Wave to Camera routine and API endpoints in arm_test_web.py."""

import time
import pytest
from unittest.mock import MagicMock, patch

from tools.arm_test_web import (
    WAVE_DEFAULT_ANGLES,
    calculate_180_rotation_angles,
    execute_wave_camera_sequence,
    app,
    wave_cancel_event,
)


class TestWaveCameraKinematics:
    def test_default_neutral_angles(self):
        assert WAVE_DEFAULT_ANGLES == [-9, 45, -57, 43]


class TestWaveCameraSequence:
    def test_execute_wave_camera_sequence_full(self):
        mock_mc = MagicMock()
        wave_cancel_event.clear()

        # Patch time.sleep / wait to run quickly in test
        with patch.object(wave_cancel_event, 'wait', return_value=False):
            execute_wave_camera_sequence(mock_mc, [-9, 45, -57, 43], speed=50)

        # Check send_angles calls
        assert mock_mc.send_angles.call_count >= 6
        # First call should be neutral [-9, 45, -57, 43]
        first_call_args = mock_mc.send_angles.call_args_list[0][0]
        assert first_call_args[0] == [-9.0, 45.0, -57.0, 43.0]

        # Second call should be move j2 to -2 and j3 to -92: [-9, -2, -92, 43]
        second_call_args = mock_mc.send_angles.call_args_list[1][0]
        assert second_call_args[0] == [-9.0, -2.0, -92.0, 43.0]

        # Third call should move j1 to 162: [162, -2, -92, 43]
        third_call_args = mock_mc.send_angles.call_args_list[2][0]
        assert third_call_args[0] == [162.0, -2.0, -92.0, 43.0]

        # Fourth call should move j2 up 15-20 deg (16.0): [162, 16, -92, 43]
        fourth_call_args = mock_mc.send_angles.call_args_list[3][0]
        assert fourth_call_args[0] == [162.0, 16.0, -92.0, 43.0]

        # Gripper close should be called
        mock_mc.set_gripper_state.assert_called_with(1, 80)

        # Final call should return to neutral
        last_call_args = mock_mc.send_angles.call_args_list[-1][0]
        assert last_call_args[0] == [-9.0, 45.0, -57.0, 43.0]

    def test_execute_wave_camera_sequence_cancellation(self):
        mock_mc = MagicMock()
        wave_cancel_event.set()  # Already cancelled

        execute_wave_camera_sequence(mock_mc, [-9, 45, -57, 43], speed=50)
        # Should abort early
        assert mock_mc.send_angles.call_count <= 2


class TestWaveCameraFlaskAPI:
    @pytest.fixture
    def client(self):
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_wave_camera_endpoint_not_connected(self, client):
        with patch("tools.arm_test_web.mc", None):
            res = client.post("/api/wave_camera", json={"neutral_angles": [-9, 45, -57, 43]})
            data = res.get_json()
            assert res.status_code == 200
            assert data.get("error") == "not connected"

    def test_wave_camera_endpoint_connected(self, client):
        mock_mc = MagicMock()
        with patch("tools.arm_test_web.mc", mock_mc), patch("tools.arm_test_web.wave_active", False):
            res = client.post("/api/wave_camera", json={"neutral_angles": [-9, 45, -57, 43], "speed": 40})
            data = res.get_json()
            assert res.status_code == 200
            assert data.get("ok") is True
            assert data.get("neutral_angles") == [-9, 45, -57, 43]

    def test_wave_camera_stop_endpoint(self, client):
        res = client.post("/api/wave_camera/stop")
        data = res.get_json()
        assert res.status_code == 200
        assert data.get("ok") is True

    def test_wave_camera_status_endpoint(self, client):
        res = client.get("/api/wave_camera/status")
        data = res.get_json()
        assert res.status_code == 200
        assert data.get("ok") is True
        assert "active" in data
        assert "status" in data
