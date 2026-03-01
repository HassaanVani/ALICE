import json
import logging
import math
from pathlib import Path
from typing import Tuple, List, Optional
from dataclasses import dataclass, asdict

import numpy as np

logger = logging.getLogger("Calibration")


@dataclass
class CalibrationPoint:
    pixel_x: int
    pixel_y: int
    arm_angles: Tuple[float, ...]


@dataclass
class ArmDimensions:
    """Arm link lengths in mm — measure from actual hardware."""
    base_height: float = 50.0
    shoulder_length: float = 100.0
    elbow_length: float = 100.0
    wrist_length: float = 80.0

JOINT_LIMITS = ((-162, 162), (-2, 90), (-92, 60), (-180, 180))


class CalibrationManager:
    DEFAULT_PATH = Path("calibration_data.json")
    
    def __init__(self, arm_dims: Optional[ArmDimensions] = None):
        self.arm_dims = arm_dims or ArmDimensions()
        self.calibration_points: List[CalibrationPoint] = []
        self._transform_matrix: Optional[np.ndarray] = None
        self._camera_resolution = (1920, 1080)
        self._workspace_bounds = {
            "x_min": -200, "x_max": 200,
            "y_min": 50, "y_max": 300,
            "z_min": 0, "z_max": 100
        }
    
    def set_camera_resolution(self, width: int, height: int) -> None:
        self._camera_resolution = (width, height)
    
    def add_calibration_point(self, pixel_x: int, pixel_y: int, arm_angles: Tuple[float, ...]) -> None:
        point = CalibrationPoint(pixel_x, pixel_y, arm_angles)
        self.calibration_points.append(point)
        
        if len(self.calibration_points) >= 4:
            self._compute_transform()
    
    def _compute_transform(self) -> None:
        if len(self.calibration_points) < 4:
            return
        
        src_pts = np.array([[p.pixel_x, p.pixel_y] for p in self.calibration_points], dtype=np.float32)
        
        dst_pts = np.array([
            self._angles_to_workspace(p.arm_angles) for p in self.calibration_points
        ], dtype=np.float32)
        
        n = len(src_pts)
        A = np.zeros((2 * n, 6))
        b = np.zeros(2 * n)
        
        for i in range(n):
            x, y = src_pts[i]
            A[2*i] = [x, y, 1, 0, 0, 0]
            A[2*i + 1] = [0, 0, 0, x, y, 1]
            b[2*i] = dst_pts[i][0]
            b[2*i + 1] = dst_pts[i][1]
        
        params, *_ = np.linalg.lstsq(A, b, rcond=None)
        
        self._transform_matrix = np.array([
            [params[0], params[1], params[2]],
            [params[3], params[4], params[5]],
            [0, 0, 1]
        ])
    
    def _angles_to_workspace(self, angles: Tuple[float, ...]) -> Tuple[float, float]:
        base, shoulder, elbow, *_ = angles

        base_rad = math.radians(base)
        shoulder_rad = math.radians(shoulder)
        elbow_rad = math.radians(elbow)

        r = (self.arm_dims.shoulder_length * math.cos(shoulder_rad) +
             self.arm_dims.elbow_length * math.cos(shoulder_rad + elbow_rad))

        x = r * math.cos(base_rad)
        y = r * math.sin(base_rad)

        return (x, y)
    
    def pixel_to_arm(self, pixel_x: int, pixel_y: int, z: float = 0) -> Tuple[float, ...]:
        if self._transform_matrix is not None:
            point = np.array([pixel_x, pixel_y, 1])
            workspace = self._transform_matrix @ point
            return self._inverse_kinematics(workspace[0], workspace[1], z)
        
        return self._simple_mapping(pixel_x, pixel_y, z)
    
    def _simple_mapping(self, px: int, py: int, z: float) -> Tuple[float, ...]:
        w, h = self._camera_resolution
        
        norm_x = (px / w) * 2 - 1
        norm_y = 1 - (py / h) * 2
        
        world_x = norm_x * 150
        world_y = 100 + norm_y * 100
        
        return self._inverse_kinematics(world_x, world_y, z)
    
    def _inverse_kinematics(self, x: float, y: float, z: float) -> Tuple[float, ...]:
        j1 = math.degrees(math.atan2(y, x))  # base rotation, centered at 0

        r = math.sqrt(x*x + y*y)
        target_z = z - self.arm_dims.base_height + self.arm_dims.wrist_length

        L1 = self.arm_dims.shoulder_length
        L2 = self.arm_dims.elbow_length

        d = math.sqrt(r*r + target_z*target_z)
        d = min(d, L1 + L2 - 1)

        cos_elbow = (d*d - L1*L1 - L2*L2) / (2 * L1 * L2)
        cos_elbow = max(-1, min(1, cos_elbow))
        elbow_angle = math.degrees(math.acos(cos_elbow))

        alpha = math.atan2(target_z, r)
        cos_beta = (L1*L1 + d*d - L2*L2) / (2 * L1 * d)
        cos_beta = max(-1, min(1, cos_beta))
        beta = math.acos(cos_beta)
        j2 = math.degrees(alpha + beta)  # shoulder

        j3 = -elbow_angle  # elbow (negative convention for the 260)

        j4 = 0  # keep suction cup pointing down for top-down picking

        def _clamp(val, idx):
            lo, hi = JOINT_LIMITS[idx]
            return max(lo, min(hi, val))

        return (_clamp(j1, 0), _clamp(j2, 1), _clamp(j3, 2), _clamp(j4, 3))
    
    def save(self, path: Optional[Path] = None) -> None:
        path = path or self.DEFAULT_PATH
        data = {
            "arm_dimensions": asdict(self.arm_dims),
            "camera_resolution": self._camera_resolution,
            "calibration_points": [asdict(p) for p in self.calibration_points],
            "transform_matrix": self._transform_matrix.tolist() if self._transform_matrix is not None else None
        }
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def _validate_point(self, point: CalibrationPoint) -> bool:
        """Check that pixel coords are within image bounds and arm angles are valid."""
        w, h = self._camera_resolution
        if not (0 <= point.pixel_x <= w and 0 <= point.pixel_y <= h):
            logger.warning(f"Calibration point pixel ({point.pixel_x}, {point.pixel_y}) "
                           f"outside image bounds ({w}x{h})")
            return False
        for i, angle in enumerate(point.arm_angles):
            if i < len(JOINT_LIMITS):
                lo, hi = JOINT_LIMITS[i]
                if not (lo <= angle <= hi):
                    logger.warning(f"Calibration point arm angle {angle} outside valid range [{lo}, {hi}] for joint {i}")
                    return False
        return True

    def load(self, path: Optional[Path] = None) -> bool:
        path = path or self.DEFAULT_PATH

        if not path.exists():
            return False

        try:
            with open(path) as f:
                data = json.load(f)

            self.arm_dims = ArmDimensions(**data["arm_dimensions"])
            self._camera_resolution = tuple(data["camera_resolution"])

            raw_points = [CalibrationPoint(**p) for p in data["calibration_points"]]
            valid_points = [p for p in raw_points if self._validate_point(p)]
            if len(valid_points) < len(raw_points):
                logger.warning(f"Dropped {len(raw_points) - len(valid_points)} invalid calibration points")
            self.calibration_points = valid_points

            if data["transform_matrix"]:
                self._transform_matrix = np.array(data["transform_matrix"])

            return True
        except Exception as e:
            logger.error(f"Load failed: {e}")
            return False
