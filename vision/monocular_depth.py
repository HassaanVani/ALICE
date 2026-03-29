"""Monocular depth estimation — RGB frame → depth map.

Uses a pretrained monocular depth model (Depth Anything v2 or MiDaS) to
estimate per-pixel depth from a single RGB image. Combined with forward
kinematics camera pose, this enables 3D spatial mapping without a depth sensor.

The depth maps are metric-scale when calibrated (via known desk height or
reference object), or relative-scale for spatial reasoning.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger("MonocularDepth")

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


@dataclass
class DepthEstimate:
    """Result of monocular depth estimation on a single frame."""
    depth_map: np.ndarray       # float32, shape (H, W), values in meters (or relative)
    color_frame: np.ndarray     # original BGR input
    is_metric: bool             # True if depth values are calibrated to meters
    min_depth: float            # minimum depth in the map
    max_depth: float            # maximum depth in the map
    timestamp: float = 0.0

    @property
    def shape(self) -> Tuple[int, int]:
        return self.depth_map.shape[:2]

    def depth_at(self, x: int, y: int) -> float:
        """Get depth at pixel (x, y). Returns 0.0 if out of bounds."""
        h, w = self.depth_map.shape
        if 0 <= y < h and 0 <= x < w:
            return float(self.depth_map[y, x])
        return 0.0

    def crop_depth(self, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
        """Extract depth within a bounding box."""
        h, w = self.depth_map.shape
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        return self.depth_map[y1:y2, x1:x2]

    def median_depth_in_bbox(self, x1: int, y1: int, x2: int, y2: int) -> float:
        """Median depth within a bounding box — robust to noise."""
        crop = self.crop_depth(x1, y1, x2, y2)
        if crop.size == 0:
            return 0.0
        return float(np.median(crop))


class MonocularDepthEstimator:
    """Estimates depth from a single RGB image using a pretrained model.

    Supports multiple backends:
    - 'depth_anything_v2': Depth Anything v2 (via torch.hub)
    - 'midas': MiDaS v3.1 (via torch.hub)
    - 'simulate': Generates flat depth maps for testing

    Args:
        model_type: Which depth model to use.
        target_size: Resolution to process at (width, height). Smaller = faster.
        device: PyTorch device. None for auto-detect.
    """

    SUPPORTED_MODELS = ("depth_anything_v2", "midas", "simulate")

    def __init__(
        self,
        model_type: str = "depth_anything_v2",
        target_size: Tuple[int, int] = (518, 518),
        device: Optional[str] = None,
    ):
        if model_type not in self.SUPPORTED_MODELS:
            logger.warning(f"Unknown model type '{model_type}', falling back to simulate")
            model_type = "simulate"

        self._model_type = model_type
        self._target_size = target_size
        self._device_str = device
        self._device = None
        self._model = None
        self._transform = None
        self._simulate = model_type == "simulate" or not TORCH_AVAILABLE

        # Metric calibration: scale + offset to convert relative depth to meters
        self._depth_scale: float = 1.0
        self._depth_offset: float = 0.0
        self._is_calibrated: bool = False

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def simulate(self) -> bool:
        return self._simulate

    @property
    def is_calibrated(self) -> bool:
        return self._is_calibrated

    def load(self) -> bool:
        """Load the depth model. Returns True on success."""
        if self._simulate:
            logger.info("Monocular depth in simulation mode")
            return True

        if not TORCH_AVAILABLE:
            logger.warning("PyTorch not available — depth estimation in simulation mode")
            self._simulate = True
            return False

        self._device = torch.device(
            self._device_str or ("cuda" if torch.cuda.is_available() else "cpu")
        )

        try:
            if self._model_type == "depth_anything_v2":
                return self._load_depth_anything()
            elif self._model_type == "midas":
                return self._load_midas()
        except Exception as e:
            logger.error(f"Failed to load depth model: {e}")
            self._simulate = True
            return False

        return False

    def _load_depth_anything(self) -> bool:
        """Load Depth Anything v2 via torch.hub."""
        try:
            self._model = torch.hub.load(
                "LiheYoung/Depth-Anything",
                "DepthAnything_vitb14",
                pretrained=True,
                trust_repo=True,
            )
            self._model.to(self._device)
            self._model.eval()
            logger.info("Depth Anything v2 loaded (ViT-B/14)")
            return True
        except Exception as e:
            logger.warning(f"Depth Anything v2 failed: {e}, trying MiDaS fallback")
            return self._load_midas()

    def _load_midas(self) -> bool:
        """Load MiDaS v3.1 via torch.hub."""
        try:
            self._model = torch.hub.load("intel-isl/MiDaS", "MiDaS_small")
            self._model.to(self._device)
            self._model.eval()
            midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")
            self._transform = midas_transforms.small_transform
            self._model_type = "midas"
            logger.info("MiDaS v3.1 (small) loaded")
            return True
        except Exception as e:
            logger.error(f"MiDaS failed: {e}")
            self._simulate = True
            return False

    def estimate(self, frame: np.ndarray) -> DepthEstimate:
        """Estimate depth from a BGR frame.

        Returns a DepthEstimate with the depth map at the original frame resolution.
        """
        if self._simulate:
            return self._simulate_estimate(frame)

        if self._model is None:
            if not self.load():
                return self._simulate_estimate(frame)

        if self._model_type == "midas":
            return self._estimate_midas(frame)
        else:
            return self._estimate_depth_anything(frame)

    def _estimate_depth_anything(self, frame: np.ndarray) -> DepthEstimate:
        """Run Depth Anything v2 inference."""
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Preprocess: resize, normalize, to tensor
        resized = cv2.resize(rgb, self._target_size)
        input_tensor = torch.from_numpy(resized).float().permute(2, 0, 1).unsqueeze(0)
        input_tensor = input_tensor / 255.0
        input_tensor = input_tensor.to(self._device)

        with torch.no_grad():
            depth = self._model(input_tensor)

        # Resize depth back to original resolution
        depth_np = depth.squeeze().cpu().numpy()
        depth_resized = cv2.resize(depth_np, (w, h), interpolation=cv2.INTER_LINEAR)

        # Apply metric calibration if available
        if self._is_calibrated:
            depth_resized = depth_resized * self._depth_scale + self._depth_offset

        return DepthEstimate(
            depth_map=depth_resized.astype(np.float32),
            color_frame=frame,
            is_metric=self._is_calibrated,
            min_depth=float(depth_resized.min()),
            max_depth=float(depth_resized.max()),
            timestamp=time.time(),
        )

    def _estimate_midas(self, frame: np.ndarray) -> DepthEstimate:
        """Run MiDaS inference."""
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        input_batch = self._transform(rgb).to(self._device)

        with torch.no_grad():
            prediction = self._model(input_batch)
            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=(h, w),
                mode="bicubic",
                align_corners=False,
            ).squeeze()

        depth_np = prediction.cpu().numpy()

        # MiDaS outputs inverse depth — convert to depth
        depth_np = 1.0 / (depth_np + 1e-6)

        if self._is_calibrated:
            depth_np = depth_np * self._depth_scale + self._depth_offset

        return DepthEstimate(
            depth_map=depth_np.astype(np.float32),
            color_frame=frame,
            is_metric=self._is_calibrated,
            min_depth=float(depth_np.min()),
            max_depth=float(depth_np.max()),
            timestamp=time.time(),
        )

    def calibrate_from_known_height(self, frame: np.ndarray,
                                     known_depth_m: float,
                                     roi: Optional[Tuple[int, int, int, int]] = None) -> None:
        """Calibrate depth scale using a known reference distance.

        Place the arm camera at a known height above the desk surface,
        then call this with the measured height in meters. The center
        region (or provided ROI) is used for calibration.

        Args:
            frame: BGR frame from the arm camera.
            known_depth_m: Actual distance from camera to desk surface in meters.
            roi: Optional (x1, y1, x2, y2) region to use for calibration.
        """
        raw = self.estimate(frame)

        if roi:
            x1, y1, x2, y2 = roi
            region = raw.depth_map[y1:y2, x1:x2]
        else:
            h, w = raw.depth_map.shape
            margin = min(h, w) // 4
            region = raw.depth_map[margin:h - margin, margin:w - margin]

        median_raw = float(np.median(region))
        if median_raw > 1e-6:
            self._depth_scale = known_depth_m / median_raw
            self._depth_offset = 0.0
            self._is_calibrated = True
            logger.info(
                f"Depth calibrated: scale={self._depth_scale:.4f} "
                f"(raw median={median_raw:.4f} → {known_depth_m:.3f}m)"
            )

    def _simulate_estimate(self, frame: np.ndarray) -> DepthEstimate:
        """Generate a flat desk depth map with slight gradient for testing."""
        h, w = frame.shape[:2]
        # Simulate a desk at ~0.4m with slight perspective gradient
        base_depth = 0.4
        gradient = np.linspace(0.35, 0.45, h, dtype=np.float32)
        depth_map = np.tile(gradient[:, np.newaxis], (1, w))
        # Add slight noise
        noise = np.random.default_rng(42).normal(0, 0.005, (h, w)).astype(np.float32)
        depth_map = depth_map + noise

        return DepthEstimate(
            depth_map=depth_map,
            color_frame=frame,
            is_metric=True,
            min_depth=float(depth_map.min()),
            max_depth=float(depth_map.max()),
            timestamp=time.time(),
        )
