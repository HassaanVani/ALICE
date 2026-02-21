"""Tests for hardware/force_sensor.py — SimulatedForceSensor."""

import pytest

from hardware.force_sensor import SimulatedForceSensor, ForceReading


@pytest.fixture
def sensor():
    return SimulatedForceSensor()


class TestSimulatedForceSensor:
    def test_read_no_objects_returns_zero(self, sensor):
        reading = sensor.read()
        assert isinstance(reading, ForceReading)
        assert reading.force_n == 0.0
        assert reading.contact_detected is False

    def test_read_close_object_returns_force(self, sensor):
        sensor.set_object_positions([(0, 0, 0)])
        sensor.set_arm_position(1, 0, 0)
        reading = sensor.read()
        assert reading.force_n > 0

    def test_read_far_object_returns_zero(self, sensor):
        sensor.set_object_positions([(100, 100, 100)])
        sensor.set_arm_position(0, 0, 0)
        reading = sensor.read()
        assert reading.force_n == 0.0

    def test_contact_detected_above_threshold(self, sensor):
        sensor.set_threshold(0.5)
        sensor.set_object_positions([(0, 0, 0)])
        sensor.set_arm_position(0.5, 0, 0)  # Very close
        reading = sensor.read()
        assert reading.contact_detected is True

    def test_calibrate_offsets_force(self, sensor):
        sensor.set_object_positions([(2, 0, 0)])
        sensor.set_arm_position(0, 0, 0)
        sensor.calibrate()
        reading = sensor.read()
        assert reading.force_n == 0.0

    def test_set_threshold(self, sensor):
        sensor.set_threshold(100.0)
        sensor.set_object_positions([(10, 0, 0)])
        sensor.set_arm_position(0, 0, 0)
        reading = sensor.read()
        # With very high threshold, moderate force should not trigger contact
        assert reading.contact_detected is False

    def test_timestamp_present(self, sensor):
        reading = sensor.read()
        assert reading.timestamp > 0
