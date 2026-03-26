"""Forward kinematics for the 4-DOF MyPalletizer 260 arm.

Computes end-effector and camera SE(3) poses from joint angles using the
Denavit-Hartenberg convention.

DH joint layout
----------------
Joint 1 — base rotation about Z
Joint 2 — shoulder rotation about X (after translating up by base_height)
Joint 3 — elbow rotation about X (after translating by shoulder_length)
Joint 4 — wrist rotation about Z (after translating by elbow_length + wrist_length)
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from .calibration import ArmDimensions, JOINT_LIMITS


@dataclass
class CameraExtrinsics:
    """Rigid offset from the end-effector frame to the camera optical frame.

    Translation is in mm; rotation is in degrees (applied as roll-pitch-yaw
    intrinsic rotations: Rz(yaw) @ Ry(pitch) @ Rx(roll)).
    """
    x_offset_mm: float = 0.0
    y_offset_mm: float = 0.0
    z_offset_mm: float = 30.0
    roll_deg: float = 0.0
    pitch_deg: float = -90.0   # camera looks down from wrist by default
    yaw_deg: float = 0.0


def _rot_x(angle_rad: float) -> np.ndarray:
    """4x4 homogeneous rotation about the X axis."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array([
        [1, 0,  0, 0],
        [0, c, -s, 0],
        [0, s,  c, 0],
        [0, 0,  0, 1],
    ], dtype=np.float64)


def _rot_y(angle_rad: float) -> np.ndarray:
    """4x4 homogeneous rotation about the Y axis."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array([
        [ c, 0, s, 0],
        [ 0, 1, 0, 0],
        [-s, 0, c, 0],
        [ 0, 0, 0, 1],
    ], dtype=np.float64)


def _rot_z(angle_rad: float) -> np.ndarray:
    """4x4 homogeneous rotation about the Z axis."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array([
        [c, -s, 0, 0],
        [s,  c, 0, 0],
        [0,  0, 1, 0],
        [0,  0, 0, 1],
    ], dtype=np.float64)


def _translation(x: float, y: float, z: float) -> np.ndarray:
    """4x4 pure translation."""
    T = np.eye(4, dtype=np.float64)
    T[0, 3] = x
    T[1, 3] = y
    T[2, 3] = z
    return T


class ForwardKinematics:
    """Forward kinematics for the 4-DOF MyPalletizer 260 arm.

    Parameters
    ----------
    arm_dims : ArmDimensions
        Link lengths (base_height, shoulder_length, elbow_length, wrist_length)
        all in mm.
    camera_extrinsics : CameraExtrinsics, optional
        Rigid offset from end-effector to camera frame.  When *None* the
        default ``CameraExtrinsics()`` is used (camera looking straight down
        from 30 mm above the wrist).
    """

    def __init__(
        self,
        arm_dims: ArmDimensions,
        camera_extrinsics: Optional[CameraExtrinsics] = None,
    ) -> None:
        self.arm_dims = arm_dims
        self.camera_extrinsics = camera_extrinsics or CameraExtrinsics()

    # ------------------------------------------------------------------
    # Core FK
    # ------------------------------------------------------------------

    def joint_to_se3(self, angles: Tuple[float, ...]) -> np.ndarray:
        """Return the 4x4 SE(3) homogeneous transform for the full chain.

        Parameters
        ----------
        angles : tuple of four floats
            Joint angles in **degrees** ``(j1, j2, j3, j4)``.

        Returns
        -------
        np.ndarray
            4x4 homogeneous transformation matrix (world -> end-effector).
        """
        if len(angles) != 4:
            raise ValueError(f"Expected 4 joint angles, got {len(angles)}")

        j1, j2, j3, j4 = (math.radians(a) for a in angles)

        d = self.arm_dims

        # --- Build chain ---
        # Base: translate up by base_height, then rotate about Z by j1
        T = _translation(0, 0, d.base_height) @ _rot_z(j1)

        # Shoulder: rotate about X by j2, then translate along Z by shoulder_length
        T = T @ _rot_x(j2) @ _translation(0, 0, d.shoulder_length)

        # Elbow: rotate about X by j3, then translate along Z by elbow_length
        T = T @ _rot_x(j3) @ _translation(0, 0, d.elbow_length)

        # Wrist: translate along Z by wrist_length, then rotate about Z by j4
        T = T @ _translation(0, 0, d.wrist_length) @ _rot_z(j4)

        return T

    def end_effector_pose(self, angles: Tuple[float, ...]) -> np.ndarray:
        """SE(3) pose of the end-effector (synonym for ``joint_to_se3``)."""
        return self.joint_to_se3(angles)

    # ------------------------------------------------------------------
    # Camera pose
    # ------------------------------------------------------------------

    def _extrinsics_matrix(self) -> np.ndarray:
        """Build the 4x4 rigid transform from end-effector to camera."""
        ex = self.camera_extrinsics
        T_trans = _translation(ex.x_offset_mm, ex.y_offset_mm, ex.z_offset_mm)

        roll = math.radians(ex.roll_deg)
        pitch = math.radians(ex.pitch_deg)
        yaw = math.radians(ex.yaw_deg)

        # Intrinsic RPY: Rz(yaw) @ Ry(pitch) @ Rx(roll)
        T_rot = _rot_z(yaw) @ _rot_y(pitch) @ _rot_x(roll)

        return T_trans @ T_rot

    def camera_pose(self, angles: Tuple[float, ...]) -> np.ndarray:
        """SE(3) pose of the camera in the world frame.

        ``T_world_camera = T_world_ee @ T_ee_camera``
        """
        T_ee = self.end_effector_pose(angles)
        T_cam = self._extrinsics_matrix()
        return T_ee @ T_cam

    # ------------------------------------------------------------------
    # Camera intrinsics
    # ------------------------------------------------------------------

    @staticmethod
    def camera_intrinsics_default() -> np.ndarray:
        """Return a 3x3 intrinsic matrix *K* for a standard 1080p webcam.

        Uses reasonable defaults:
        - focal length  ~960 px  (≈ 60 degree horizontal FOV on a 1920-wide sensor)
        - principal point at the image centre
        """
        fx = fy = 960.0
        cx, cy = 960.0, 540.0
        return np.array([
            [fx,  0, cx],
            [ 0, fy, cy],
            [ 0,  0,  1],
        ], dtype=np.float64)

    # ------------------------------------------------------------------
    # Validation helper
    # ------------------------------------------------------------------

    @staticmethod
    def validate_angles(angles: Tuple[float, ...]) -> bool:
        """Return True if every joint angle is within its limits."""
        if len(angles) != 4:
            return False
        for i, a in enumerate(angles):
            lo, hi = JOINT_LIMITS[i]
            if a < lo or a > hi:
                return False
        return True
