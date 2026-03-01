"""Tests for hardware/calibration.py — CalibrationManager."""

import numpy as np
import pytest

from hardware.calibration import CalibrationManager, CalibrationPoint, ArmDimensions


@pytest.fixture
def cal():
    return CalibrationManager()


class TestCalibrationManager:
    def test_validate_valid_point(self, cal):
        # Use angles within per-joint limits: J1 ±162, J2 -2..90, J3 -92..60, J4 ±180
        point = CalibrationPoint(pixel_x=500, pixel_y=300, arm_angles=(0.0, 45.0, -30.0, 0.0))
        assert cal._validate_point(point) is True

    def test_validate_rejects_pixel_out_of_bounds(self, cal):
        point = CalibrationPoint(pixel_x=2000, pixel_y=300, arm_angles=(0.0, 45.0, -30.0, 0.0))
        assert cal._validate_point(point) is False

    def test_validate_rejects_negative_pixel(self, cal):
        point = CalibrationPoint(pixel_x=-10, pixel_y=300, arm_angles=(0.0, 45.0, -30.0, 0.0))
        assert cal._validate_point(point) is False

    def test_validate_rejects_angle_over_limit(self, cal):
        # J2 max is 90, so 200 should be rejected
        point = CalibrationPoint(pixel_x=500, pixel_y=300, arm_angles=(0.0, 200.0, 0.0, 0.0))
        assert cal._validate_point(point) is False

    def test_validate_rejects_angle_under_limit(self, cal):
        # J2 min is -2, so -5 should be rejected
        point = CalibrationPoint(pixel_x=500, pixel_y=300, arm_angles=(0.0, -5.0, 0.0, 0.0))
        assert cal._validate_point(point) is False

    def test_transform_matrix_after_4_points(self, cal):
        points = [
            (100, 100, (45.0, 30.0, -30.0, 0.0)),
            (500, 100, (0.0, 45.0, -20.0, 0.0)),
            (100, 500, (45.0, 20.0, -10.0, 0.0)),
            (500, 500, (90.0, 20.0, -10.0, 0.0)),
        ]
        for px, py, angles in points:
            cal.add_calibration_point(px, py, angles)

        assert cal._transform_matrix is not None
        assert cal._transform_matrix.shape == (3, 3)

    def test_no_transform_with_fewer_than_4_points(self, cal):
        cal.add_calibration_point(100, 100, (0.0, 45.0, -30.0, 0.0))
        cal.add_calibration_point(500, 100, (0.0, 45.0, -30.0, 0.0))
        assert cal._transform_matrix is None
