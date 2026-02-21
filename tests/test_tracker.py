"""Tests for vision/tracker.py — BlockTracker with Kalman filter."""

import numpy as np
import pytest

from vision.aruco_detector import BlockData
from vision.tracker import BlockTracker, TrackedBlock, MAX_MISSING_FRAMES


def _make_detection(block_id, cx, cy, conf=1.0):
    return BlockData(
        block_id=block_id,
        marker_id=block_id - 1,
        center_x=cx,
        center_y=cy,
        corners=np.array([[cx-10, cy-10], [cx+10, cy-10],
                          [cx+10, cy+10], [cx-10, cy+10]], dtype=np.float32),
        rotation=0.0,
        confidence=conf,
    )


@pytest.fixture
def tracker():
    return BlockTracker()


class TestBlockTracker:
    def test_initial_no_tracks(self, tracker):
        assert len(tracker.active_tracks) == 0

    def test_first_detection_creates_track(self, tracker):
        dets = [_make_detection(1, 100, 200)]
        tracks = tracker.update(dets)
        assert len(tracks) == 1
        assert tracks[0].block_id == 1

    def test_multiple_blocks_tracked(self, tracker):
        dets = [_make_detection(i, i * 50, 100) for i in range(1, 5)]
        tracks = tracker.update(dets)
        assert len(tracks) == 4

    def test_reset(self, tracker):
        tracker.update([_make_detection(1, 100, 200)])
        tracker.reset()
        assert len(tracker.active_tracks) == 0

    def test_new_track_has_correct_position(self, tracker):
        tracker.update([_make_detection(1, 100, 200)])
        tracks = tracker.active_tracks
        assert len(tracks) == 1
        assert abs(tracks[0].filtered_x - 100) < 1
        assert abs(tracks[0].filtered_y - 200) < 1

    def test_track_association_by_block_id(self, tracker):
        tracker.update([_make_detection(1, 100, 200), _make_detection(2, 300, 200)])
        tracks = tracker.active_tracks
        ids = {t.block_id for t in tracks}
        assert ids == {1, 2}
