"""YOLO-based object detector — ALICE can see real desk objects.

Replaces the ArUco marker + CNN pipeline with Ultralytics YOLOv8 for
general-purpose object detection. ALICE no longer needs markers — she sees
cups, laptops, phones, pens, and everything else on a real desk.

The detector produces Detection objects that feed into the ObjectTracker
and personality engine's preference system.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger("YoloDetector")

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


# COCO classes relevant to a desk environment
DESK_OBJECTS: Dict[int, str] = {
    39: "bottle",
    41: "cup",
    42: "fork",
    43: "knife",
    44: "spoon",
    45: "bowl",
    56: "chair",
    63: "laptop",
    64: "mouse",
    65: "remote",
    66: "keyboard",
    67: "cell phone",
    73: "book",
    74: "clock",
    75: "vase",
    76: "scissors",
    77: "teddy bear",
}

# Objects ALICE should never try to grab (too big, too fragile, or fixtures)
NO_GRAB: Set[str] = {"laptop", "keyboard", "chair", "monitor"}


class ObjectCategory(Enum):
    """Semantic grouping for desk objects."""
    DRINKWARE = "drinkware"     # cup, bottle, bowl
    STATIONERY = "stationery"   # pen, scissors, book
    ELECTRONICS = "electronics"  # laptop, phone, mouse, keyboard, remote
    PERSONAL = "personal"       # teddy bear, clock, vase
    TOOL = "tool"               # fork, knife, spoon
    UNKNOWN = "unknown"

    @staticmethod
    def from_label(label: str) -> "ObjectCategory":
        _map = {
            "cup": ObjectCategory.DRINKWARE,
            "bottle": ObjectCategory.DRINKWARE,
            "bowl": ObjectCategory.DRINKWARE,
            "book": ObjectCategory.STATIONERY,
            "scissors": ObjectCategory.STATIONERY,
            "laptop": ObjectCategory.ELECTRONICS,
            "mouse": ObjectCategory.ELECTRONICS,
            "keyboard": ObjectCategory.ELECTRONICS,
            "cell phone": ObjectCategory.ELECTRONICS,
            "remote": ObjectCategory.ELECTRONICS,
            "clock": ObjectCategory.PERSONAL,
            "vase": ObjectCategory.PERSONAL,
            "teddy bear": ObjectCategory.PERSONAL,
            "fork": ObjectCategory.TOOL,
            "knife": ObjectCategory.TOOL,
            "spoon": ObjectCategory.TOOL,
            "chair": ObjectCategory.UNKNOWN,
        }
        return _map.get(label, ObjectCategory.UNKNOWN)


@dataclass
class Detection:
    """A single detected object from YOLO.

    This is the universal detection type for the desk-assistant pipeline.
    Compatible with the ObjectTracker and personality engine.
    """
    label: str                          # COCO class name ("cup", "laptop", ...)
    confidence: float                   # 0.0–1.0
    bbox: Tuple[int, int, int, int]     # (x1, y1, x2, y2) pixel coords
    center_x: int = 0
    center_y: int = 0
    category: ObjectCategory = ObjectCategory.UNKNOWN
    class_id: int = -1                  # COCO class index
    track_id: Optional[int] = None      # assigned by ObjectTracker
    is_grabbable: bool = True

    def __post_init__(self):
        x1, y1, x2, y2 = self.bbox
        self.center_x = (x1 + x2) // 2
        self.center_y = (y1 + y2) // 2
        self.category = ObjectCategory.from_label(self.label)
        self.is_grabbable = self.label not in NO_GRAB

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]

    @property
    def area(self) -> int:
        return self.width * self.height

    def as_dict(self) -> dict:
        d = {
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "bbox": list(self.bbox),
            "center": (self.center_x, self.center_y),
            "category": self.category.value,
            "is_grabbable": self.is_grabbable,
        }
        if self.track_id is not None:
            d["track_id"] = self.track_id
        return d


class YoloDetector:
    """Ultralytics YOLO wrapper for desk object detection.

    Loads a pretrained COCO model and filters results to desk-relevant
    objects. Produces Detection objects compatible with ObjectTracker.

    Args:
        model_path: Path to YOLO weights. Defaults to 'yolov8n.pt' (nano).
        confidence_threshold: Minimum detection confidence.
        desk_filter: If True, only return objects in DESK_OBJECTS.
        device: PyTorch device string. None for auto-detect.
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence_threshold: float = 0.4,
        desk_filter: bool = True,
        device: Optional[str] = None,
    ):
        self._model_path = model_path
        self._confidence_threshold = confidence_threshold
        self._desk_filter = desk_filter
        self._device = device
        self._model: Optional[object] = None
        self._class_names: Dict[int, str] = {}
        self._simulate = not YOLO_AVAILABLE

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def simulate(self) -> bool:
        return self._simulate

    def load(self) -> bool:
        """Load the YOLO model. Returns True on success."""
        if not YOLO_AVAILABLE:
            logger.warning("ultralytics not installed — YOLO detector in simulation mode")
            self._simulate = True
            return False

        try:
            kwargs = {"task": "detect"}
            if self._device is not None:
                kwargs["verbose"] = False
            self._model = YOLO(self._model_path, **kwargs)
            self._class_names = self._model.names
            logger.info(
                f"YOLO loaded: {self._model_path} "
                f"({len(self._class_names)} classes)"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self._simulate = True
            return False

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Run detection on a BGR frame.

        Returns a list of Detection objects, sorted by confidence (highest first).
        """
        if self._simulate:
            return self._simulate_detect(frame)

        if self._model is None:
            if not self.load():
                return []

        results = self._model(
            frame,
            conf=self._confidence_threshold,
            verbose=False,
            device=self._device,
        )

        detections: List[Detection] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                conf = float(boxes.conf[i].item())
                label = self._class_names.get(cls_id, f"class_{cls_id}")

                # Filter to desk objects if enabled
                if self._desk_filter and cls_id not in DESK_OBJECTS:
                    continue

                x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy().astype(int)

                det = Detection(
                    label=label,
                    confidence=conf,
                    bbox=(int(x1), int(y1), int(x2), int(y2)),
                    class_id=cls_id,
                )
                detections.append(det)

        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections

    def detect_specific(self, frame: np.ndarray, label: str) -> List[Detection]:
        """Detect only objects matching a specific label."""
        return [d for d in self.detect(frame) if d.label == label]

    def detect_grabbable(self, frame: np.ndarray) -> List[Detection]:
        """Detect only objects ALICE can physically grab."""
        return [d for d in self.detect(frame) if d.is_grabbable]

    def draw_detections(self, frame: np.ndarray,
                        detections: List[Detection]) -> np.ndarray:
        """Draw bounding boxes and labels on a frame."""
        import cv2

        output = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            color = _category_color(det.category)

            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)

            text = f"{det.label} {det.confidence:.0%}"
            (tw, th), _ = cv2.getTextSize(
                text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            cv2.rectangle(output, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
            cv2.putText(
                output, text, (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
            )

            cv2.circle(output, (det.center_x, det.center_y), 4, color, -1)

        return output

    def _simulate_detect(self, frame: np.ndarray) -> List[Detection]:
        """Return deterministic fake detections for testing without YOLO."""
        h, w = frame.shape[:2]
        return [
            Detection(
                label="cup",
                confidence=0.92,
                bbox=(w // 4, h // 4, w // 4 + 80, h // 4 + 100),
                class_id=41,
            ),
            Detection(
                label="laptop",
                confidence=0.88,
                bbox=(w // 2, h // 3, w // 2 + 200, h // 3 + 150),
                class_id=63,
            ),
            Detection(
                label="cell phone",
                confidence=0.75,
                bbox=(w * 3 // 4, h // 2, w * 3 // 4 + 60, h // 2 + 120),
                class_id=67,
            ),
        ]

    @property
    def confidence_threshold(self) -> float:
        return self._confidence_threshold

    @confidence_threshold.setter
    def confidence_threshold(self, value: float) -> None:
        self._confidence_threshold = max(0.0, min(1.0, value))


def _category_color(category: ObjectCategory) -> Tuple[int, int, int]:
    """BGR color for each object category."""
    colors = {
        ObjectCategory.DRINKWARE: (0, 165, 255),    # orange
        ObjectCategory.STATIONERY: (0, 255, 0),      # green
        ObjectCategory.ELECTRONICS: (255, 100, 100),  # blue
        ObjectCategory.PERSONAL: (255, 0, 255),       # magenta
        ObjectCategory.TOOL: (0, 255, 255),           # yellow
        ObjectCategory.UNKNOWN: (200, 200, 200),      # gray
    }
    return colors.get(category, (200, 200, 200))
