"""Inference pipeline — CNN activations for glass brain + YOLO object detection.

Two parallel inference paths:
1. CNN (BlockRecognizerCNN) — runs on cropped images, feeds activation hooks
   to the glass brain visualization. Kept for visual effect.
2. YOLO (YoloDetector) — runs on full frames, detects real desk objects.
   This is the primary perception system for the desk-assistant pipeline.
"""

import logging
from typing import Tuple, Dict, Optional, List
from pathlib import Path

import numpy as np

logger = logging.getLogger("Inference")
import torch
import torch.nn.functional as F

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from .cnn_model import BlockRecognizerCNN
from .hooks import HookManager
from .state_model import BlockStateClassifier, BlockState


class InferencePipeline:
    def __init__(self, model: Optional[BlockRecognizerCNN] = None):
        self.model = model or BlockRecognizerCNN()
        self.hooks = HookManager()
        self.hooks.register_hooks(self.model)
        self._frozen = False
        self._last_prediction: Optional[Tuple[int, float]] = None
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self._device)

        # YOLO detector — lazy-loaded on first call to detect_objects()
        self._yolo = None
        self._yolo_config: Dict = {}

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    @property
    def last_prediction(self) -> Optional[Tuple[int, float]]:
        return self._last_prediction

    @property
    def yolo(self):
        """Access the YOLO detector, loading it on first use."""
        if self._yolo is None:
            self._init_yolo()
        return self._yolo

    def freeze(self) -> None:
        self._frozen = True

    def unfreeze(self) -> None:
        self._frozen = False

    def toggle_freeze(self) -> bool:
        self._frozen = not self._frozen
        return self._frozen

    def configure_yolo(self, model_path: str = "yolov8n.pt",
                       confidence_threshold: float = 0.4,
                       desk_filter: bool = True,
                       device: Optional[str] = None) -> None:
        """Configure YOLO before first use. Call before detect_objects()."""
        self._yolo_config = {
            "model_path": model_path,
            "confidence_threshold": confidence_threshold,
            "desk_filter": desk_filter,
            "device": device,
        }
        # Reset so next access re-initializes with new config
        self._yolo = None

    def _init_yolo(self) -> None:
        """Lazy-initialize the YOLO detector."""
        from vision.yolo_detector import YoloDetector
        config = self._yolo_config
        self._yolo = YoloDetector(
            model_path=config.get("model_path", "yolov8n.pt"),
            confidence_threshold=config.get("confidence_threshold", 0.4),
            desk_filter=config.get("desk_filter", True),
            device=config.get("device"),
        )
        self._yolo.load()

    def detect_objects(self, frame: np.ndarray) -> List:
        """Detect desk objects using YOLO. Returns List[Detection].

        Also runs the CNN on the center crop for glass brain activations,
        so the dashboard visualization stays alive.
        """
        # Run CNN on center crop for glass brain visualization
        if not self._frozen:
            self._run_cnn_for_activations(frame)

        # Run YOLO for actual object detection
        return self.yolo.detect(frame)

    def _run_cnn_for_activations(self, frame: np.ndarray) -> None:
        """Run CNN on a center crop purely to feed activation hooks."""
        tensor = self.preprocess(frame)
        self.model.eval()
        with torch.no_grad():
            self.model(tensor)

    # --- Legacy CNN interface (kept for block-sorting modes) ---

    def preprocess(self, image: np.ndarray) -> torch.Tensor:
        if len(image.shape) == 3:
            if CV2_AVAILABLE:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = np.mean(image, axis=2).astype(np.uint8)
        else:
            gray = image

        if CV2_AVAILABLE:
            resized = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)
        else:
            h, w = gray.shape
            resized = np.zeros((64, 64), dtype=np.uint8)
            for i in range(64):
                for j in range(64):
                    resized[i, j] = gray[int(i * h / 64), int(j * w / 64)]

        normalized = resized.astype(np.float32) / 255.0
        tensor = torch.from_numpy(normalized).unsqueeze(0).unsqueeze(0)
        return tensor.to(self._device)

    def predict(self, image: np.ndarray) -> Tuple[int, float, Dict[str, np.ndarray]]:
        if self._frozen and self._last_prediction:
            return (*self._last_prediction, self.hooks.get_activations())

        self.model.eval()
        tensor = self.preprocess(image)

        with torch.no_grad():
            logits = self.model(tensor)
            probs = F.softmax(logits, dim=1)
            pred_idx = probs.argmax(dim=1).item()
            confidence = probs[0, pred_idx].item()

        block_id = pred_idx + 1
        self._last_prediction = (block_id, confidence)

        return block_id, confidence, self.hooks.get_activations()

    def predict_batch(self, images: List[np.ndarray]) -> List[Tuple[int, float]]:
        if not images:
            return []

        tensors = [self.preprocess(img) for img in images]
        batch = torch.cat(tensors, dim=0)

        self.model.eval()
        with torch.no_grad():
            logits = self.model(batch)
            probs = F.softmax(logits, dim=1)
            pred_indices = probs.argmax(dim=1)
            confidences = probs.gather(1, pred_indices.unsqueeze(1)).squeeze(1)

        results = [
            (int(idx.item()) + 1, float(conf.item()))
            for idx, conf in zip(pred_indices, confidences)
        ]

        return results

    def get_layer_voxels(self, layer_name: str, resolution: int = 32) -> Optional[np.ndarray]:
        return self.hooks.to_voxel_grid(layer_name, resolution)

    def get_all_layer_stats(self) -> Dict[str, dict]:
        return {
            name: self.hooks.get_activation_stats(name)
            for name in self.hooks.layer_names
        }

    def get_websocket_payload(self, layer_name: Optional[str] = None) -> bytes:
        return self.hooks.serialize_for_websocket(layer_name)

    def predict_state(self, image: np.ndarray) -> Tuple[BlockState, float]:
        """Predict block state (upright/tilted/stacked/occluded)."""
        if not hasattr(self, '_state_model') or self._state_model is None:
            self._state_model = BlockStateClassifier().to(self._device)
        tensor = self.preprocess(image)
        return self._state_model.predict(tensor)

    def load_state_weights(self, path: Path) -> bool:
        try:
            if not hasattr(self, '_state_model') or self._state_model is None:
                self._state_model = BlockStateClassifier()
            self._state_model.load(path)
            self._state_model.to(self._device)
            return True
        except Exception as e:
            logger.error(f"Failed to load state weights: {e}")
            return False

    def load_weights(self, path: Path) -> bool:
        try:
            self.model.load(path)
            self.model.to(self._device)
            return True
        except Exception as e:
            logger.error(f"Failed to load weights: {e}")
            return False


def create_pipeline(weights_path: Optional[Path] = None) -> InferencePipeline:
    pipeline = InferencePipeline()
    if weights_path:
        pipeline.load_weights(weights_path)
    return pipeline
