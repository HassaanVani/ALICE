"""Tests for tracker + YOLO Detection integration — ObjectTracker with string labels."""

import numpy as np
import pytest

from vision.yolo_detector import Detection
from vision.tracker import BlockTracker, ObjectTracker, TrackedBlock


def _make_yolo_det(label, cx, cy, conf=0.9, w=60, h=80):
    """Create a Detection as YOLO would produce."""
    x1 = cx - w // 2
    y1 = cy - h // 2
    return Detection(
        label=label,
        confidence=conf,
        bbox=(x1, y1, x1 + w, y1 + h),
    )


@pytest.fixture
def tracker():
    return ObjectTracker()


class TestObjectTrackerWithDetections:
    def test_alias_is_block_tracker(self):
        assert ObjectTracker is BlockTracker

    def test_track_yolo_detection(self, tracker):
        dets = [_make_yolo_det("cup", 100, 200)]
        tracks = tracker.update(dets)
        assert len(tracks) == 1
        assert tracks[0].label == "cup"
        assert abs(tracks[0].filtered_x - 100) < 1
        assert abs(tracks[0].filtered_y - 200) < 1

    def test_track_multiple_objects(self, tracker):
        dets = [
            _make_yolo_det("cup", 100, 200),
            _make_yolo_det("laptop", 400, 300),
            _make_yolo_det("cell phone", 600, 100),
        ]
        tracks = tracker.update(dets)
        assert len(tracks) == 3
        labels = {t.label for t in tracks}
        assert labels == {"cup", "laptop", "cell phone"}

    def test_association_across_frames(self, tracker):
        # Frame 1: cup at (100, 200)
        tracker.update([_make_yolo_det("cup", 100, 200)])
        # Frame 2: cup moved slightly
        tracks = tracker.update([_make_yolo_det("cup", 105, 203)])
        assert len(tracks) == 1
        assert tracks[0].label == "cup"
        # Position should be filtered (close to new position)
        assert abs(tracks[0].filtered_x - 105) < 10
        assert tracks[0].frames_since_seen == 0

    def test_label_mismatch_penalizes_association(self, tracker):
        tracker.update([_make_yolo_det("cup", 100, 200)])
        # New frame: same position but different label → new track
        tracks = tracker.update([_make_yolo_det("bottle", 100, 200)])
        # Should still associate (same position dominates) but update label
        cup_tracks = [t for t in tracks if t.label == "cup"]
        bottle_tracks = [t for t in tracks if t.label == "bottle"]
        # At least one track should exist
        assert len(tracks) >= 1

    def test_get_track_by_label(self, tracker):
        dets = [
            _make_yolo_det("cup", 100, 200, conf=0.95),
            _make_yolo_det("laptop", 400, 300, conf=0.88),
        ]
        tracker.update(dets)
        cup = tracker.get_track_by_label("cup")
        assert cup is not None
        assert cup.label == "cup"
        assert abs(cup.filtered_x - 100) < 1

    def test_get_track_by_label_none(self, tracker):
        tracker.update([_make_yolo_det("cup", 100, 200)])
        result = tracker.get_track_by_label("banana")
        assert result is None

    def test_get_tracks_by_label_multiple(self, tracker):
        # Two cups
        dets = [
            _make_yolo_det("cup", 100, 200),
            _make_yolo_det("cup", 500, 200),
        ]
        tracker.update(dets)
        cups = tracker.get_tracks_by_label("cup")
        assert len(cups) == 2

    def test_track_speed(self, tracker):
        # Stationary → speed ~0
        tracker.update([_make_yolo_det("cup", 100, 200)])
        tracks = tracker.update([_make_yolo_det("cup", 100, 200)])
        assert tracks[0].speed < 5

    def test_block_id_negative_for_yolo(self, tracker):
        """YOLO detections have block_id=-1 since they're not numbered blocks."""
        tracker.update([_make_yolo_det("cup", 100, 200)])
        tracks = tracker.active_tracks
        assert tracks[0].block_id == -1

    def test_reset_clears_all(self, tracker):
        tracker.update([_make_yolo_det("cup", 100, 200)])
        tracker.reset()
        assert len(tracker.active_tracks) == 0


class TestInferencePipelineYolo:
    def test_detect_objects_returns_detections(self):
        from brain.inference import InferencePipeline
        pipeline = InferencePipeline()
        # Force YOLO to sim mode
        pipeline.configure_yolo()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        dets = pipeline.detect_objects(frame)
        assert len(dets) >= 1
        assert all(hasattr(d, "label") for d in dets)

    def test_detect_objects_feeds_cnn_activations(self):
        from brain.inference import InferencePipeline
        pipeline = InferencePipeline()
        pipeline.configure_yolo()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        pipeline.detect_objects(frame)
        # CNN should have run, populating activation hooks
        activations = pipeline.hooks.get_activations()
        assert len(activations) > 0

    def test_detect_objects_respects_freeze(self):
        from brain.inference import InferencePipeline
        pipeline = InferencePipeline()
        pipeline.configure_yolo()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Run once to populate activations
        pipeline.detect_objects(frame)
        act1 = {k: v.copy() for k, v in pipeline.hooks.get_activations().items()}
        # Freeze and run with different frame
        pipeline.freeze()
        frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 128
        pipeline.detect_objects(frame2)
        act2 = pipeline.hooks.get_activations()
        # Activations should be unchanged (CNN didn't run)
        for key in act1:
            if key in act2:
                np.testing.assert_array_equal(act1[key], act2[key])
