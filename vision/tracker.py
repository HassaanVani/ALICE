"""Real-time object tracking with Kalman filter and greedy association.

Tracks Detection objects (YOLO) using spatial proximity and label matching
for frame-to-frame association. Duck-typed: any object with center_x,
center_y, confidence attributes works.
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Union

import cv2
import numpy as np

logger = logging.getLogger("Tracker")

MAX_MISSING_FRAMES = 15  # ~0.5s at 30fps
ASSOCIATION_THRESHOLD = 80  # pixels


@dataclass
class TrackedBlock:
    block_id: int
    track_id: int
    filtered_x: float
    filtered_y: float
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    confidence: float = 1.0
    frames_since_seen: int = 0
    label: str = ""  # YOLO label (empty for ArUco-only tracking)
    _kalman: cv2.KalmanFilter = field(default=None, repr=False)

    def __post_init__(self):
        if self._kalman is None:
            self._kalman = self._create_kalman(self.filtered_x, self.filtered_y)

    @staticmethod
    def _create_kalman(x: float, y: float) -> cv2.KalmanFilter:
        kf = cv2.KalmanFilter(4, 2)  # 4 state vars (x, y, vx, vy), 2 measurements (x, y)

        # Transition matrix: x' = x + vx, y' = y + vy
        kf.transitionMatrix = np.array([
            [1, 0, 1, 0],
            [0, 1, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ], dtype=np.float32)

        # Measurement matrix: we observe x, y
        kf.measurementMatrix = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ], dtype=np.float32)

        kf.processNoiseCov = np.eye(4, dtype=np.float32) * 1e-2
        kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 1e-1
        kf.errorCovPost = np.eye(4, dtype=np.float32)

        kf.statePost = np.array([x, y, 0, 0], dtype=np.float32)
        return kf

    def predict(self) -> Tuple[float, float]:
        predicted = self._kalman.predict()
        self.filtered_x = float(predicted[0].item() if hasattr(predicted[0], 'item') else predicted[0])
        self.filtered_y = float(predicted[1].item() if hasattr(predicted[1], 'item') else predicted[1])
        self.velocity_x = float(predicted[2].item() if hasattr(predicted[2], 'item') else predicted[2])
        self.velocity_y = float(predicted[3].item() if hasattr(predicted[3], 'item') else predicted[3])
        return self.filtered_x, self.filtered_y

    def update(self, x: float, y: float, confidence: float):
        measurement = np.array([x, y], dtype=np.float32)
        corrected = self._kalman.correct(measurement)
        self.filtered_x = float(corrected[0].item() if hasattr(corrected[0], 'item') else corrected[0])
        self.filtered_y = float(corrected[1].item() if hasattr(corrected[1], 'item') else corrected[1])
        self.velocity_x = float(corrected[2].item() if hasattr(corrected[2], 'item') else corrected[2])
        self.velocity_y = float(corrected[3].item() if hasattr(corrected[3], 'item') else corrected[3])
        self.confidence = confidence
        self.frames_since_seen = 0

    @property
    def speed(self) -> float:
        """Pixels per frame."""
        return (self.velocity_x ** 2 + self.velocity_y ** 2) ** 0.5


def _det_center_x(det) -> float:
    return float(det.center_x)


def _det_center_y(det) -> float:
    return float(det.center_y)


def _det_confidence(det) -> float:
    return float(det.confidence)


def _det_label(det) -> str:
    """Extract label from either BlockData or Detection."""
    if hasattr(det, "label") and det.label:
        return det.label
    if hasattr(det, "block_id"):
        return str(det.block_id)
    return ""


def _det_block_id(det) -> int:
    """Extract integer block_id from either type. Returns -1 for non-block objects."""
    if hasattr(det, "block_id"):
        return int(det.block_id)
    return -1


class BlockTracker:
    def __init__(self):
        self._tracks: Dict[int, TrackedBlock] = {}  # track_id -> TrackedBlock
        self._next_track_id: int = 1
        self._lock = threading.Lock()

    @property
    def active_tracks(self) -> List[TrackedBlock]:
        return [t for t in self._tracks.values() if t.frames_since_seen <= MAX_MISSING_FRAMES]

    def update(self, detections: list) -> List[TrackedBlock]:
        """Update tracker with new detections, return tracked results.

        Accepts List[BlockData] or List[Detection] (duck-typed on center_x,
        center_y, confidence). Thread-safe: all Kalman predict/correct calls
        are serialized by _lock.
        """
        with self._lock:
            # Predict step for all existing tracks
            for track in self._tracks.values():
                track.predict()
                track.frames_since_seen += 1

            if not detections and not self._tracks:
                return []

            # Build cost matrix for Hungarian algorithm
            tracks_list = list(self._tracks.values())
            n_tracks = len(tracks_list)
            n_dets = len(detections)

            if n_tracks == 0:
                # All detections become new tracks
                for det in detections:
                    self._create_track(det)
                return self.active_tracks

            if n_dets == 0:
                # Just age existing tracks, prune old
                self._prune_lost_tracks()
                return self.active_tracks

            # Cost matrix: distance between predicted track positions and detection positions
            cost = np.full((n_tracks, n_dets), ASSOCIATION_THRESHOLD * 2, dtype=np.float32)
            for i, track in enumerate(tracks_list):
                for j, det in enumerate(detections):
                    dist = np.sqrt(
                        (track.filtered_x - _det_center_x(det)) ** 2
                        + (track.filtered_y - _det_center_y(det)) ** 2
                    )
                    # Penalize label/id mismatch to prefer same-object associations
                    det_label = _det_label(det)
                    track_label = track.label or str(track.block_id)
                    if track_label != det_label:
                        dist += ASSOCIATION_THRESHOLD * 0.5
                    cost[i, j] = dist

            # Greedy matching
            matched_tracks = set()
            matched_dets = set()

            while True:
                min_val = cost.min()
                if min_val >= ASSOCIATION_THRESHOLD:
                    break
                idx = np.unravel_index(cost.argmin(), cost.shape)
                i, j = idx

                tracks_list[i].update(
                    _det_center_x(detections[j]),
                    _det_center_y(detections[j]),
                    _det_confidence(detections[j]),
                )
                tracks_list[i].block_id = _det_block_id(detections[j])
                tracks_list[i].label = _det_label(detections[j])
                matched_tracks.add(i)
                matched_dets.add(j)

                cost[i, :] = ASSOCIATION_THRESHOLD * 2
                cost[:, j] = ASSOCIATION_THRESHOLD * 2

            # Create new tracks for unmatched detections
            for j in range(n_dets):
                if j not in matched_dets:
                    self._create_track(detections[j])

            self._prune_lost_tracks()
            return self.active_tracks

    def get_track_by_label(self, label: str) -> Optional[TrackedBlock]:
        """Find the most confident active track with a given label."""
        matches = [
            t for t in self.active_tracks
            if t.label == label
        ]
        if not matches:
            return None
        return max(matches, key=lambda t: t.confidence)

    def get_tracks_by_label(self, label: str) -> List[TrackedBlock]:
        """Find all active tracks with a given label."""
        return [t for t in self.active_tracks if t.label == label]

    def _create_track(self, det) -> TrackedBlock:
        track = TrackedBlock(
            block_id=_det_block_id(det),
            track_id=self._next_track_id,
            filtered_x=float(_det_center_x(det)),
            filtered_y=float(_det_center_y(det)),
            confidence=_det_confidence(det),
            label=_det_label(det),
        )
        self._tracks[self._next_track_id] = track
        self._next_track_id += 1
        return track

    def _prune_lost_tracks(self):
        to_remove = [
            tid for tid, track in self._tracks.items()
            if track.frames_since_seen > MAX_MISSING_FRAMES
        ]
        for tid in to_remove:
            del self._tracks[tid]

    def reset(self):
        self._tracks.clear()
        self._next_track_id = 1


# Alias — new code should use ObjectTracker, old code keeps working
ObjectTracker = BlockTracker
