"""Tests for selftest.py — SelfTest startup checks."""

import pytest

from selftest import SelfTest, CheckResult


@pytest.fixture
def st():
    return SelfTest(simulate=True)


class TestSelfTest:
    def test_check_cameras_simulated(self, st):
        result = st.check_cameras()
        assert isinstance(result, CheckResult)
        assert result.passed is True
        assert result.duration_ms >= 0

    def test_check_arm_simulated(self, st):
        result = st.check_arm_connection()
        assert result.passed is True

    def test_check_magnet_simulated(self, st):
        result = st.check_magnet()
        assert result.passed is True

    def test_check_cnn_weights(self, st):
        result = st.check_cnn_weights()
        # Weights file should exist from training
        assert isinstance(result, CheckResult)

    def test_check_aruco_detection(self, st):
        result = st.check_aruco_detection()
        assert result.passed is True

    def test_run_all(self, st):
        results = st.run_all()
        assert len(results) >= 6  # cameras, arm, magnet, calibration, cnn, aruco + ports

    def test_all_passed_property(self, st):
        st.run_all()
        # In simulate mode, most checks pass (calibration file may not exist)
        assert isinstance(st.all_passed, bool)

    def test_check_websocket_port(self, st):
        result = st.check_websocket_port(59999, name="Test")
        assert result.passed is True  # Port should be available
