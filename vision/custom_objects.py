"""Custom object recognition — ALICE learns to see objects YOLO doesn't know.

When a user shows ALICE an object and gives it a name, she captures a color
histogram and thumbnail. Later, she can find that object by scanning the
camera frame for regions that match the stored color signature.

This is NOT fine-tuned YOLO. It's a lightweight template system for personal
desk objects: "my blue notebook", "the red stress ball", "that weird USB hub."
Objects with distinct colors work best. Two white objects will confuse her.

Storage: data/custom_objects/
  - registry.json — metadata for all registered objects
  - {name}_thumb.jpg — 64x64 thumbnail for dashboard/debug
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

logger = logging.getLogger("CustomObjects")

STORE_DIR = Path("data/custom_objects")
REGISTRY_FILE = STORE_DIR / "registry.json"
THUMB_SIZE = (64, 64)

# Histogram comparison threshold — lower = stricter match
# cv2.HISTCMP_CORREL returns 0-1, higher = better match
MATCH_THRESHOLD = 0.45

# Minimum contour area (pixels) to consider a match candidate
MIN_MATCH_AREA = 800


@dataclass
class CustomObject:
    """A user-registered object with a visual color signature."""
    name: str                           # user-given name ("notebook", "stress ball")
    histogram: Optional[np.ndarray] = None  # HSV color histogram (flattened)
    registered_at: float = 0.0
    last_seen: float = 0.0
    times_found: int = 0
    thumbnail_path: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "histogram": self.histogram.tolist() if self.histogram is not None else None,
            "registered_at": self.registered_at,
            "last_seen": self.last_seen,
            "times_found": self.times_found,
            "thumbnail_path": self.thumbnail_path,
        }

    @staticmethod
    def from_dict(data: dict) -> "CustomObject":
        hist = None
        if data.get("histogram") is not None:
            hist = np.array(data["histogram"], dtype=np.float32)
        return CustomObject(
            name=data["name"],
            histogram=hist,
            registered_at=data.get("registered_at", 0.0),
            last_seen=data.get("last_seen", 0.0),
            times_found=data.get("times_found", 0),
            thumbnail_path=data.get("thumbnail_path", ""),
        )


def _compute_histogram(image_bgr: np.ndarray) -> np.ndarray:
    """Compute a normalized HSV color histogram from a BGR image crop."""
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    # 2D histogram: hue (30 bins) x saturation (32 bins)
    # Ignoring value channel makes it more robust to lighting changes
    hist = cv2.calcHist([hsv], [0, 1], None, [30, 32],
                        [0, 180, 0, 256])
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
    return hist.flatten()


class CustomObjectStore:
    """Stores and matches user-registered objects by color signature.

    Usage:
        store = CustomObjectStore()
        store.load()

        # Registration: user shows an object
        store.register("notebook", frame, bbox=(x1, y1, x2, y2))

        # Detection: find a registered object in a new frame
        result = store.find("notebook", frame)
        if result:
            cx, cy, confidence = result
    """

    def __init__(self, store_dir: Path = STORE_DIR):
        self._dir = store_dir
        self._objects: Dict[str, CustomObject] = {}

    @property
    def names(self) -> List[str]:
        return list(self._objects.keys())

    @property
    def count(self) -> int:
        return len(self._objects)

    def get(self, name: str) -> Optional[CustomObject]:
        return self._objects.get(name)

    def register(self, name: str, frame_bgr: np.ndarray,
                 bbox: Optional[Tuple[int, int, int, int]] = None) -> bool:
        """Register a new object from a camera frame.

        Args:
            name: User-given name for the object.
            frame_bgr: Full camera frame (BGR, uint8).
            bbox: Optional (x1, y1, x2, y2) bounding box. If None,
                  uses the center 40% of the frame.

        Returns True on success.
        """
        if not CV2_AVAILABLE:
            logger.warning("OpenCV not available — cannot register objects")
            return False

        if frame_bgr is None or frame_bgr.size == 0:
            return False

        h, w = frame_bgr.shape[:2]

        # Default: center 40% of frame
        if bbox is None:
            margin_x = int(w * 0.3)
            margin_y = int(h * 0.3)
            bbox = (margin_x, margin_y, w - margin_x, h - margin_y)

        x1, y1, x2, y2 = bbox
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

        crop = frame_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            return False

        histogram = _compute_histogram(crop)

        # Save thumbnail
        self._dir.mkdir(parents=True, exist_ok=True)
        thumb = cv2.resize(crop, THUMB_SIZE)
        thumb_filename = f"{name}_thumb.jpg"
        thumb_path = self._dir / thumb_filename
        cv2.imwrite(str(thumb_path), thumb)

        obj = CustomObject(
            name=name,
            histogram=histogram,
            registered_at=time.time(),
            thumbnail_path=thumb_filename,
        )
        self._objects[name] = obj
        self.save()

        logger.info(f"Registered custom object: '{name}' (crop {x2-x1}x{y2-y1}px)")
        return True

    def unregister(self, name: str) -> bool:
        """Remove a registered object."""
        if name not in self._objects:
            return False

        obj = self._objects.pop(name)

        # Delete thumbnail
        if obj.thumbnail_path:
            thumb_path = self._dir / obj.thumbnail_path
            if thumb_path.exists():
                thumb_path.unlink()

        self.save()
        logger.info(f"Unregistered custom object: '{name}'")
        return True

    def find(self, name: str, frame_bgr: np.ndarray,
             ) -> Optional[Tuple[int, int, float]]:
        """Find a registered object in a camera frame.

        Uses histogram backprojection to locate regions matching the
        stored color signature, then finds the best contour.

        Args:
            name: Registered object name.
            frame_bgr: Current camera frame (BGR, uint8).

        Returns (center_x, center_y, confidence) or None if not found.
        """
        if not CV2_AVAILABLE:
            return None

        obj = self._objects.get(name)
        if obj is None or obj.histogram is None:
            return None

        if frame_bgr is None or frame_bgr.size == 0:
            return None

        h, w = frame_bgr.shape[:2]
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)

        # Reshape stored histogram back to 2D for backprojection
        hist_2d = obj.histogram.reshape(30, 32)

        # Backproject: highlight pixels that match the stored color distribution
        backproj = cv2.calcBackProject([hsv], [0, 1], hist_2d,
                                       [0, 180, 0, 256], 1)

        # Normalize backprojection to 0-255 range
        cv2.normalize(backproj, backproj, 0, 255, cv2.NORM_MINMAX)
        backproj = backproj.astype(np.uint8)

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        backproj = cv2.morphologyEx(backproj, cv2.MORPH_CLOSE, kernel)
        backproj = cv2.morphologyEx(backproj, cv2.MORPH_OPEN, kernel)

        # Threshold
        _, thresh = cv2.threshold(backproj, 50, 255, cv2.THRESH_BINARY)

        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        # Pick the largest contour above minimum area
        valid = [c for c in contours if cv2.contourArea(c) >= MIN_MATCH_AREA]
        if not valid:
            return None

        best = max(valid, key=cv2.contourArea)
        M = cv2.moments(best)
        if M["m00"] == 0:
            return None

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])

        # Confidence: compare the crop at the found location to stored histogram
        area = cv2.contourArea(best)
        x, y, bw, bh = cv2.boundingRect(best)
        crop = frame_bgr[y:y+bh, x:x+bw]
        if crop.size == 0:
            return None

        crop_hist = _compute_histogram(crop)
        similarity = cv2.compareHist(
            obj.histogram.reshape(30, 32),
            crop_hist.reshape(30, 32),
            cv2.HISTCMP_CORREL,
        )

        if similarity < MATCH_THRESHOLD:
            return None

        # Update tracking
        obj.last_seen = time.time()
        obj.times_found += 1

        return (cx, cy, float(similarity))

    def find_all(self, frame_bgr: np.ndarray,
                 ) -> List[Tuple[str, int, int, float]]:
        """Find all registered objects in a frame.

        Returns list of (name, center_x, center_y, confidence).
        """
        results = []
        for name in self._objects:
            match = self.find(name, frame_bgr)
            if match:
                cx, cy, conf = match
                results.append((name, cx, cy, conf))
        return results

    # ── Persistence ──────────────────────────────────────────────

    def save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        data = {name: obj.to_dict() for name, obj in self._objects.items()}
        registry_path = self._dir / "registry.json"
        with open(registry_path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self) -> bool:
        registry_path = self._dir / "registry.json"
        if not registry_path.exists():
            return False
        try:
            with open(registry_path) as f:
                data = json.load(f)
            self._objects = {
                name: CustomObject.from_dict(obj_data)
                for name, obj_data in data.items()
            }
            logger.info(f"Loaded {len(self._objects)} custom objects")
            return True
        except Exception as e:
            logger.error(f"Failed to load custom objects: {e}")
            return False
