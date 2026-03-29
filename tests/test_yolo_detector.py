"""Tests for vision/yolo_detector.py — YOLO object detection."""

import numpy as np
import pytest

from vision.yolo_detector import (
    YoloDetector, Detection, ObjectCategory, DESK_OBJECTS, NO_GRAB,
    _category_color,
)


# --- Detection dataclass ---

class TestDetection:
    def test_center_computed_from_bbox(self):
        det = Detection(label="cup", confidence=0.9, bbox=(100, 200, 180, 300))
        assert det.center_x == 140
        assert det.center_y == 250

    def test_category_assigned_from_label(self):
        det = Detection(label="cup", confidence=0.9, bbox=(0, 0, 10, 10))
        assert det.category == ObjectCategory.DRINKWARE

    def test_electronics_category(self):
        det = Detection(label="laptop", confidence=0.9, bbox=(0, 0, 10, 10))
        assert det.category == ObjectCategory.ELECTRONICS

    def test_unknown_category(self):
        det = Detection(label="alien_artifact", confidence=0.5, bbox=(0, 0, 10, 10))
        assert det.category == ObjectCategory.UNKNOWN

    def test_is_grabbable_true_for_cup(self):
        det = Detection(label="cup", confidence=0.9, bbox=(0, 0, 10, 10))
        assert det.is_grabbable is True

    def test_is_grabbable_false_for_laptop(self):
        det = Detection(label="laptop", confidence=0.9, bbox=(0, 0, 10, 10))
        assert det.is_grabbable is False

    def test_is_grabbable_false_for_keyboard(self):
        det = Detection(label="keyboard", confidence=0.9, bbox=(0, 0, 10, 10))
        assert det.is_grabbable is False

    def test_width_height_area(self):
        det = Detection(label="cup", confidence=0.9, bbox=(10, 20, 50, 80))
        assert det.width == 40
        assert det.height == 60
        assert det.area == 2400

    def test_as_dict(self):
        det = Detection(label="cup", confidence=0.923, bbox=(10, 20, 50, 80),
                        class_id=41)
        d = det.as_dict()
        assert d["label"] == "cup"
        assert d["confidence"] == 0.923
        assert d["bbox"] == [10, 20, 50, 80]
        assert d["center"] == (30, 50)
        assert d["category"] == "drinkware"
        assert d["is_grabbable"] is True
        assert "track_id" not in d

    def test_as_dict_includes_track_id_when_set(self):
        det = Detection(label="cup", confidence=0.9, bbox=(0, 0, 10, 10))
        det.track_id = 7
        d = det.as_dict()
        assert d["track_id"] == 7


# --- ObjectCategory ---

class TestObjectCategory:
    def test_from_label_known(self):
        assert ObjectCategory.from_label("cup") == ObjectCategory.DRINKWARE
        assert ObjectCategory.from_label("laptop") == ObjectCategory.ELECTRONICS
        assert ObjectCategory.from_label("book") == ObjectCategory.STATIONERY
        assert ObjectCategory.from_label("fork") == ObjectCategory.TOOL
        assert ObjectCategory.from_label("clock") == ObjectCategory.PERSONAL

    def test_from_label_unknown(self):
        assert ObjectCategory.from_label("potato") == ObjectCategory.UNKNOWN


# --- YoloDetector (simulation mode — no ultralytics needed) ---

class TestYoloDetectorSimulation:
    def test_simulate_mode_without_ultralytics(self):
        detector = YoloDetector()
        detector._simulate = True  # force sim
        assert detector.simulate is True

    def test_simulate_detect_returns_detections(self):
        detector = YoloDetector()
        detector._simulate = True
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        results = detector.detect(frame)
        assert len(results) == 3
        labels = {d.label for d in results}
        assert "cup" in labels
        assert "laptop" in labels
        assert "cell phone" in labels

    def test_simulate_detect_has_valid_bboxes(self):
        detector = YoloDetector()
        detector._simulate = True
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        results = detector.detect(frame)
        for det in results:
            x1, y1, x2, y2 = det.bbox
            assert x1 < x2
            assert y1 < y2
            assert det.center_x == (x1 + x2) // 2
            assert det.center_y == (y1 + y2) // 2

    def test_detect_specific(self):
        detector = YoloDetector()
        detector._simulate = True
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cups = detector.detect_specific(frame, "cup")
        assert len(cups) == 1
        assert cups[0].label == "cup"

    def test_detect_specific_no_match(self):
        detector = YoloDetector()
        detector._simulate = True
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect_specific(frame, "banana")
        assert result == []

    def test_detect_grabbable(self):
        detector = YoloDetector()
        detector._simulate = True
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        grabbable = detector.detect_grabbable(frame)
        for det in grabbable:
            assert det.is_grabbable is True
        labels = {d.label for d in grabbable}
        assert "laptop" not in labels

    def test_confidence_threshold_property(self):
        detector = YoloDetector(confidence_threshold=0.6)
        assert detector.confidence_threshold == 0.6
        detector.confidence_threshold = 0.3
        assert detector.confidence_threshold == 0.3

    def test_confidence_threshold_clamped(self):
        detector = YoloDetector()
        detector.confidence_threshold = 1.5
        assert detector.confidence_threshold == 1.0
        detector.confidence_threshold = -0.5
        assert detector.confidence_threshold == 0.0

    def test_draw_detections(self):
        detector = YoloDetector()
        detector._simulate = True
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        dets = detector.detect(frame)
        output = detector.draw_detections(frame, dets)
        assert output.shape == frame.shape
        # Output should be modified (not all zeros)
        assert output.sum() > 0

    def test_is_loaded_false_before_load(self):
        detector = YoloDetector()
        assert detector.is_loaded is False


# --- Category colors ---

class TestCategoryColor:
    def test_known_categories_have_colors(self):
        for cat in ObjectCategory:
            color = _category_color(cat)
            assert len(color) == 3
            assert all(0 <= c <= 255 for c in color)


# --- DESK_OBJECTS and NO_GRAB constants ---

class TestConstants:
    def test_desk_objects_has_expected_classes(self):
        labels = set(DESK_OBJECTS.values())
        assert "cup" in labels
        assert "laptop" in labels
        assert "cell phone" in labels
        assert "book" in labels

    def test_no_grab_subset(self):
        assert "laptop" in NO_GRAB
        assert "keyboard" in NO_GRAB
        assert "cup" not in NO_GRAB
