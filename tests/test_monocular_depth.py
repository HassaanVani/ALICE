"""Tests for vision/monocular_depth.py — monocular depth estimation."""

import numpy as np
import pytest

from vision.monocular_depth import MonocularDepthEstimator, DepthEstimate


@pytest.fixture
def estimator():
    return MonocularDepthEstimator(model_type="simulate")


@pytest.fixture
def frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


class TestDepthEstimate:
    def test_shape(self, estimator, frame):
        result = estimator.estimate(frame)
        assert result.shape == (480, 640)

    def test_depth_at_valid(self, estimator, frame):
        result = estimator.estimate(frame)
        d = result.depth_at(320, 240)
        assert d > 0

    def test_depth_at_out_of_bounds(self, estimator, frame):
        result = estimator.estimate(frame)
        assert result.depth_at(-1, -1) == 0.0
        assert result.depth_at(9999, 9999) == 0.0

    def test_crop_depth(self, estimator, frame):
        result = estimator.estimate(frame)
        crop = result.crop_depth(100, 100, 200, 200)
        assert crop.shape == (100, 100)

    def test_crop_depth_clamped(self, estimator, frame):
        result = estimator.estimate(frame)
        crop = result.crop_depth(-10, -10, 50, 50)
        assert crop.shape == (50, 50)

    def test_median_depth_in_bbox(self, estimator, frame):
        result = estimator.estimate(frame)
        median = result.median_depth_in_bbox(100, 100, 200, 200)
        assert 0.3 < median < 0.5  # simulated desk at ~0.4m

    def test_median_depth_empty_bbox(self, estimator, frame):
        result = estimator.estimate(frame)
        assert result.median_depth_in_bbox(100, 100, 100, 100) == 0.0

    def test_is_metric(self, estimator, frame):
        result = estimator.estimate(frame)
        assert result.is_metric is True  # simulated is always metric

    def test_min_max_depth(self, estimator, frame):
        result = estimator.estimate(frame)
        assert result.min_depth < result.max_depth
        assert result.min_depth > 0


class TestMonocularDepthEstimator:
    def test_simulate_mode(self):
        est = MonocularDepthEstimator(model_type="simulate")
        assert est.simulate is True

    def test_unknown_model_falls_back(self):
        est = MonocularDepthEstimator(model_type="nonexistent_model")
        assert est.simulate is True

    def test_load_in_simulation(self, estimator):
        assert estimator.load() is True

    def test_not_loaded_before_load(self):
        est = MonocularDepthEstimator(model_type="simulate")
        assert est.is_loaded is False

    def test_estimate_returns_depth(self, estimator, frame):
        result = estimator.estimate(frame)
        assert isinstance(result, DepthEstimate)
        assert result.depth_map.dtype == np.float32

    def test_estimate_preserves_frame(self, estimator, frame):
        result = estimator.estimate(frame)
        assert result.color_frame is frame

    def test_depth_values_reasonable(self, estimator, frame):
        result = estimator.estimate(frame)
        assert result.depth_map.min() > 0.2
        assert result.depth_map.max() < 0.6

    def test_calibration(self, estimator, frame):
        assert estimator.is_calibrated is False
        estimator.calibrate_from_known_height(frame, known_depth_m=0.35)
        assert estimator.is_calibrated is True

    def test_supported_models_constant(self):
        assert "depth_anything_v2" in MonocularDepthEstimator.SUPPORTED_MODELS
        assert "midas" in MonocularDepthEstimator.SUPPORTED_MODELS
        assert "simulate" in MonocularDepthEstimator.SUPPORTED_MODELS


class TestDepthWithYolo:
    """Verify depth estimation integrates with YOLO detections."""

    def test_depth_at_detection_bbox(self, estimator, frame):
        from vision.yolo_detector import Detection
        det = Detection(label="cup", confidence=0.9, bbox=(100, 100, 160, 200))
        result = estimator.estimate(frame)
        depth = result.median_depth_in_bbox(*det.bbox)
        assert depth > 0

    def test_depth_for_multiple_detections(self, estimator, frame):
        from vision.yolo_detector import Detection
        dets = [
            Detection(label="cup", confidence=0.9, bbox=(100, 100, 160, 200)),
            Detection(label="laptop", confidence=0.85, bbox=(300, 150, 500, 350)),
        ]
        result = estimator.estimate(frame)
        depths = [result.median_depth_in_bbox(*d.bbox) for d in dets]
        assert all(d > 0 for d in depths)
