"""Presence detection — ALICE knows when someone is at the desk.

Uses MediaPipe Face Detection on the front-facing camera to detect human
presence. Feeds PersonalityEngine.set_presence() so ALICE can react:
- Finish her Tetris piece before turning to greet someone
- Switch from idle scanning to attentive watching
- Adjust voice gate and movement dynamics

Also extracts basic engagement signals: face count, approximate distance
(from face bbox size), and whether someone is looking at the desk.
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

logger = logging.getLogger("Presence")

try:
    import mediapipe as mp
    MP_AVAILABLE = True
except ImportError:
    MP_AVAILABLE = False


@dataclass
class PresenceInfo:
    """Snapshot of who's at the desk."""
    detected: bool = False
    face_count: int = 0
    closest_distance: float = float("inf")  # rough distance in cm (from bbox size)
    looking_at_desk: bool = False
    timestamp: float = 0.0
    face_center_x: float = 0.0   # pixel X of closest face in frame
    face_center_y: float = 0.0   # pixel Y of closest face in frame

    def to_dict(self) -> dict:
        return {
            "detected": self.detected,
            "face_count": self.face_count,
            "closest_distance": round(self.closest_distance, 1),
            "looking_at_desk": self.looking_at_desk,
            "timestamp": self.timestamp,
            "face_center_x": round(self.face_center_x, 1),
            "face_center_y": round(self.face_center_y, 1),
        }


class PresenceDetector:
    """Detects human presence using MediaPipe Face Detection.

    Designed to run on the front-facing camera. Lightweight enough for
    real-time use alongside YOLO on the arm camera.

    Args:
        min_detection_confidence: MediaPipe confidence threshold.
        absence_timeout: Seconds without a face before declaring absence.
        reference_face_width: Expected face width in pixels at ~60cm distance.
    """

    # Rough conversion: face bbox width → distance
    # At ~60cm, a face is roughly 120px wide on a 720p front camera
    REFERENCE_DISTANCE_CM = 60.0
    REFERENCE_FACE_WIDTH_PX = 120.0

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        absence_timeout: float = 2.0,
        reference_face_width: float = 120.0,
    ):
        self._min_confidence = min_detection_confidence
        self._absence_timeout = absence_timeout
        self.REFERENCE_FACE_WIDTH_PX = reference_face_width

        self._face_detection = None
        self._last_seen_time: float = 0.0
        self._last_info = PresenceInfo()
        self._simulate = not MP_AVAILABLE

    @property
    def simulate(self) -> bool:
        return self._simulate

    def start(self) -> bool:
        """Initialize MediaPipe. Returns True on success."""
        if not MP_AVAILABLE:
            logger.warning("mediapipe not installed — presence detection in simulation mode")
            self._simulate = True
            return False

        try:
            self._face_detection = mp.solutions.face_detection.FaceDetection(
                model_selection=0,  # short-range model (< 2m, faster)
                min_detection_confidence=self._min_confidence,
            )
            logger.info("Presence detector started (MediaPipe Face Detection)")
            return True
        except Exception as e:
            logger.error(f"Failed to start presence detector: {e}")
            self._simulate = True
            return False

    def stop(self) -> None:
        """Release MediaPipe resources."""
        if self._face_detection is not None:
            self._face_detection.close()
            self._face_detection = None

    def detect(self, frame: np.ndarray) -> PresenceInfo:
        """Process a frame and return presence information.

        Args:
            frame: BGR image from the front-facing camera.

        Returns:
            PresenceInfo with detection results.
        """
        if self._simulate:
            return self._simulate_detect(frame)

        if self._face_detection is None:
            self.start()
            if self._simulate:
                return self._simulate_detect(frame)

        import cv2

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._face_detection.process(rgb)

        now = time.time()
        faces: List[dict] = []

        if results.detections:
            h, w = frame.shape[:2]
            for detection in results.detections:
                bbox = detection.location_data.relative_bounding_box
                face_width_px = bbox.width * w
                face_center_x = (bbox.xmin + bbox.width / 2) * w
                face_center_y = (bbox.ymin + bbox.height / 2) * h

                # Rough distance estimate from face width
                distance_cm = (
                    self.REFERENCE_DISTANCE_CM
                    * self.REFERENCE_FACE_WIDTH_PX
                    / max(face_width_px, 1)
                )

                faces.append({
                    "width_px": face_width_px,
                    "center_x": face_center_x,
                    "center_y": face_center_y,
                    "distance_cm": distance_cm,
                    "confidence": detection.score[0],
                })

            self._last_seen_time = now

        # Determine presence with timeout
        time_since_seen = now - self._last_seen_time if self._last_seen_time > 0 else float("inf")
        detected = len(faces) > 0 or time_since_seen < self._absence_timeout

        # Closest face
        closest = min(faces, key=lambda f: f["distance_cm"]) if faces else None

        # "Looking at desk" heuristic: face center is in lower half of frame
        # (person looking down toward the desk, not looking up/away)
        looking = False
        if closest:
            h = frame.shape[0]
            looking = closest["center_y"] > h * 0.4

        info = PresenceInfo(
            detected=detected,
            face_count=len(faces),
            closest_distance=closest["distance_cm"] if closest else float("inf"),
            looking_at_desk=looking,
            timestamp=now,
            face_center_x=closest["center_x"] if closest else 0.0,
            face_center_y=closest["center_y"] if closest else 0.0,
        )
        self._last_info = info
        return info

    @property
    def last_info(self) -> PresenceInfo:
        return self._last_info

    def _simulate_detect(self, frame: np.ndarray) -> PresenceInfo:
        """Return a simulated presence for testing."""
        info = PresenceInfo(
            detected=True,
            face_count=1,
            closest_distance=65.0,
            looking_at_desk=True,
            timestamp=time.time(),
            face_center_x=640.0,
            face_center_y=400.0,
        )
        self._last_info = info
        return info
