"""3D Spatial Map — fuses RGB + depth + FK camera pose into a 3D model.

Uses Open3D's TSDF (Truncated Signed Distance Function) volume to integrate
multiple views from the arm-mounted camera into a coherent 3D representation
of the desk workspace. This gives ALICE true 3D understanding: distances in
centimeters, object heights, and spatial relationships.

The pipeline:
1. Arm camera captures RGB frame
2. MonocularDepthEstimator produces depth map
3. ForwardKinematics computes camera SE(3) pose from joint angles
4. TSDF volume integrates (RGB, depth, pose) into a fused 3D volume
5. Extract point cloud or mesh for dashboard visualization

Falls back to a simulated flat-desk model when Open3D is not available.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("SpatialMap")

try:
    import open3d as o3d
    O3D_AVAILABLE = True
except ImportError:
    O3D_AVAILABLE = False


@dataclass
class SpatialObject:
    """An object located in the 3D spatial map."""
    label: str
    position_cm: Tuple[float, float, float]   # (x, y, z) in workspace cm
    bbox_3d: Optional[Tuple[Tuple[float, float, float],
                             Tuple[float, float, float]]] = None  # min, max corners
    confidence: float = 0.0
    last_updated: float = 0.0

    def distance_to(self, other: "SpatialObject") -> float:
        """Euclidean distance in cm between two objects."""
        return sum(
            (a - b) ** 2 for a, b in zip(self.position_cm, other.position_cm)
        ) ** 0.5

    def to_dict(self) -> dict:
        d = {
            "label": self.label,
            "position_cm": [round(v, 1) for v in self.position_cm],
            "confidence": round(self.confidence, 3),
        }
        if self.bbox_3d:
            d["bbox_3d"] = [list(self.bbox_3d[0]), list(self.bbox_3d[1])]
        return d


@dataclass
class SpatialMapState:
    """Snapshot of the 3D spatial map for dashboard/WebSocket."""
    objects: List[SpatialObject] = field(default_factory=list)
    frame_count: int = 0
    last_update: float = 0.0
    volume_bounds_cm: Tuple[float, float, float] = (60.0, 40.0, 30.0)  # w, d, h

    def to_dict(self) -> dict:
        return {
            "objects": [o.to_dict() for o in self.objects],
            "frame_count": self.frame_count,
            "last_update": self.last_update,
            "volume_bounds_cm": list(self.volume_bounds_cm),
        }


class SpatialMap:
    """3D spatial map using TSDF volume integration.

    Integrates RGB-D frames (from monocular depth estimation) with known
    camera poses (from forward kinematics) to build a fused 3D model.

    Args:
        voxel_size: TSDF voxel size in meters. Smaller = more detail.
        sdf_trunc: Truncation distance for SDF. Usually 3-5x voxel_size.
        volume_bounds_m: (width, depth, height) of the workspace volume in meters.
        intrinsic_matrix: 3x3 camera intrinsic matrix K.
    """

    def __init__(
        self,
        voxel_size: float = 0.005,
        sdf_trunc: float = 0.02,
        volume_bounds_m: Tuple[float, float, float] = (0.6, 0.4, 0.3),
        intrinsic_matrix: Optional[np.ndarray] = None,
    ):
        self._voxel_size = voxel_size
        self._sdf_trunc = sdf_trunc
        self._volume_bounds_m = volume_bounds_m
        self._intrinsic = intrinsic_matrix
        self._volume = None
        self._simulate = not O3D_AVAILABLE
        self._frame_count = 0
        self._spatial_objects: Dict[str, SpatialObject] = {}
        self._point_cloud: Optional[np.ndarray] = None

    @property
    def simulate(self) -> bool:
        return self._simulate

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def spatial_objects(self) -> Dict[str, SpatialObject]:
        return dict(self._spatial_objects)

    def initialize(self, intrinsic_matrix: Optional[np.ndarray] = None) -> bool:
        """Create the TSDF volume. Call once before integrating frames."""
        if intrinsic_matrix is not None:
            self._intrinsic = intrinsic_matrix

        if self._simulate:
            logger.info("Spatial map in simulation mode (Open3D not available)")
            return True

        try:
            self._volume = o3d.pipelines.integration.ScalableTSDFVolume(
                voxel_length=self._voxel_size,
                sdf_trunc=self._sdf_trunc,
                color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8,
            )
            logger.info(
                f"TSDF volume initialized: voxel={self._voxel_size}m, "
                f"trunc={self._sdf_trunc}m"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to initialize TSDF volume: {e}")
            self._simulate = True
            return True

    def integrate_frame(
        self,
        color: np.ndarray,
        depth: np.ndarray,
        camera_pose: np.ndarray,
        intrinsic: Optional[np.ndarray] = None,
    ) -> None:
        """Integrate one RGB-D frame into the TSDF volume.

        Args:
            color: BGR uint8 image (H, W, 3).
            depth: float32 depth map in meters (H, W).
            camera_pose: 4x4 SE(3) camera-to-world transform.
            intrinsic: Optional 3x3 intrinsic matrix (overrides default).
        """
        self._frame_count += 1

        if self._simulate:
            return

        K = intrinsic if intrinsic is not None else self._intrinsic
        if K is None:
            logger.warning("No intrinsic matrix — skipping frame integration")
            return

        try:
            h, w = depth.shape[:2]

            o3d_intrinsic = o3d.camera.PinholeCameraIntrinsic(
                width=w, height=h,
                fx=K[0, 0], fy=K[1, 1],
                cx=K[0, 2], cy=K[1, 2],
            )

            # Convert depth to Open3D format (float64, meters)
            depth_o3d = o3d.geometry.Image(depth.astype(np.float32))

            # Convert color BGR → RGB for Open3D
            import cv2
            rgb = cv2.cvtColor(color, cv2.COLOR_BGR2RGB)
            color_o3d = o3d.geometry.Image(rgb.astype(np.uint8))

            rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
                color_o3d, depth_o3d,
                depth_scale=1.0,
                depth_trunc=3.0,
                convert_rgb_to_intensity=False,
            )

            # Camera pose: Open3D expects world-to-camera (extrinsic)
            extrinsic = np.linalg.inv(camera_pose)

            self._volume.integrate(rgbd, o3d_intrinsic, extrinsic)

        except Exception as e:
            logger.debug(f"Frame integration failed: {e}")

    def extract_point_cloud(self) -> Optional[np.ndarray]:
        """Extract the fused point cloud as an Nx6 array (x,y,z,r,g,b).

        Coordinates are in meters. Returns None if no frames integrated.
        """
        if self._simulate:
            return self._simulate_point_cloud()

        if self._volume is None or self._frame_count == 0:
            return None

        try:
            pcd = self._volume.extract_point_cloud()
            points = np.asarray(pcd.points)
            colors = np.asarray(pcd.colors)
            if len(points) == 0:
                return None
            self._point_cloud = np.hstack([points, colors])
            return self._point_cloud
        except Exception as e:
            logger.error(f"Point cloud extraction failed: {e}")
            return None

    def place_object_in_3d(
        self,
        label: str,
        pixel_x: int,
        pixel_y: int,
        depth_m: float,
        camera_pose: np.ndarray,
        intrinsic: Optional[np.ndarray] = None,
        confidence: float = 1.0,
    ) -> SpatialObject:
        """Project a 2D detection + depth into 3D workspace coordinates.

        Given a pixel location, its depth, and the camera pose, compute the
        3D position in the workspace frame. This is how YOLO detections
        become 3D objects.
        """
        K = intrinsic if intrinsic is not None else self._intrinsic
        if K is None:
            # Fallback: use default intrinsics
            from hardware.forward_kinematics import ForwardKinematics
            K = ForwardKinematics.camera_intrinsics_default()

        fx, fy = K[0, 0], K[1, 1]
        cx, cy = K[0, 2], K[1, 2]

        # Back-project pixel to camera frame (meters)
        x_cam = (pixel_x - cx) * depth_m / fx
        y_cam = (pixel_y - cy) * depth_m / fy
        z_cam = depth_m

        # Transform to world frame
        point_cam = np.array([x_cam, y_cam, z_cam, 1.0])
        point_world = camera_pose @ point_cam

        # Convert to cm
        pos_cm = (
            float(point_world[0]) * 100,
            float(point_world[1]) * 100,
            float(point_world[2]) * 100,
        )

        obj = SpatialObject(
            label=label,
            position_cm=pos_cm,
            confidence=confidence,
            last_updated=time.time(),
        )
        self._spatial_objects[label] = obj
        return obj

    def get_distance_between(self, label_a: str, label_b: str) -> Optional[float]:
        """Distance in cm between two tracked objects. None if either unknown."""
        a = self._spatial_objects.get(label_a)
        b = self._spatial_objects.get(label_b)
        if a is None or b is None:
            return None
        return a.distance_to(b)

    def get_state(self) -> SpatialMapState:
        """Current spatial map state for dashboard."""
        return SpatialMapState(
            objects=list(self._spatial_objects.values()),
            frame_count=self._frame_count,
            last_update=time.time(),
            volume_bounds_cm=tuple(v * 100 for v in self._volume_bounds_m),
        )

    def reset(self) -> None:
        """Clear the TSDF volume and all tracked objects."""
        self._frame_count = 0
        self._spatial_objects.clear()
        self._point_cloud = None
        if not self._simulate and self._volume is not None:
            self.initialize()

    def _simulate_point_cloud(self) -> np.ndarray:
        """Generate a simulated flat desk point cloud."""
        rng = np.random.default_rng(42)
        n_points = 500
        w, d, _ = self._volume_bounds_m
        # Flat desk surface with slight noise
        x = rng.uniform(-w / 2, w / 2, n_points)
        y = rng.uniform(-d / 2, d / 2, n_points)
        z = rng.normal(0, 0.002, n_points)  # nearly flat
        r = rng.uniform(0.3, 0.5, n_points)
        g = rng.uniform(0.25, 0.45, n_points)
        b = rng.uniform(0.2, 0.4, n_points)
        return np.column_stack([x, y, z, r, g, b]).astype(np.float32)
