"""Tests for hardware.forward_kinematics module."""

import math

import numpy as np
import pytest

from hardware.calibration import ArmDimensions, JOINT_LIMITS
from hardware.forward_kinematics import (
    CameraExtrinsics,
    ForwardKinematics,
    _rot_x,
    _rot_y,
    _rot_z,
    _translation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def dims():
    return ArmDimensions()  # 50, 100, 100, 80 mm


@pytest.fixture
def fk(dims):
    return ForwardKinematics(dims)


@pytest.fixture
def fk_identity_cam(dims):
    """FK with identity (zero) camera extrinsics so camera == end-effector."""
    return ForwardKinematics(
        dims,
        CameraExtrinsics(
            x_offset_mm=0, y_offset_mm=0, z_offset_mm=0,
            roll_deg=0, pitch_deg=0, yaw_deg=0,
        ),
    )


# ---------------------------------------------------------------------------
# Home position (0, 0, 0, 0) — arm extended straight up along Z
# ---------------------------------------------------------------------------

class TestHomePosition:
    def test_home_translation(self, fk, dims):
        """At home all rotations are zero so the arm extends along +Z."""
        T = fk.end_effector_pose((0, 0, 0, 0))

        expected_z = (
            dims.base_height
            + dims.shoulder_length
            + dims.elbow_length
            + dims.wrist_length
        )
        pos = T[:3, 3]
        np.testing.assert_allclose(pos, [0, 0, expected_z], atol=1e-10)

    def test_home_rotation_is_identity(self, fk):
        """With zero angles the rotation block should be identity."""
        T = fk.end_effector_pose((0, 0, 0, 0))
        np.testing.assert_allclose(T[:3, :3], np.eye(3), atol=1e-10)

    def test_home_is_valid_se3(self, fk):
        """Bottom row must be [0, 0, 0, 1]."""
        T = fk.end_effector_pose((0, 0, 0, 0))
        np.testing.assert_allclose(T[3, :], [0, 0, 0, 1], atol=1e-10)


# ---------------------------------------------------------------------------
# Camera pose differs from end-effector pose by exactly the extrinsics
# ---------------------------------------------------------------------------

class TestCameraPose:
    def test_camera_equals_ee_with_identity_extrinsics(self, fk_identity_cam):
        """When extrinsics are zero/identity, camera and EE poses must match."""
        angles = (30, 20, -10, 5)
        T_ee = fk_identity_cam.end_effector_pose(angles)
        T_cam = fk_identity_cam.camera_pose(angles)
        np.testing.assert_allclose(T_cam, T_ee, atol=1e-10)

    def test_camera_offset_translation_only(self, dims):
        """Pure translation extrinsics shift the camera position."""
        ext = CameraExtrinsics(
            x_offset_mm=10, y_offset_mm=20, z_offset_mm=30,
            roll_deg=0, pitch_deg=0, yaw_deg=0,
        )
        fk = ForwardKinematics(dims, ext)
        angles = (0, 0, 0, 0)
        T_ee = fk.end_effector_pose(angles)
        T_cam = fk.camera_pose(angles)

        # The difference should be the extrinsics applied in the EE frame
        T_diff = np.linalg.inv(T_ee) @ T_cam
        np.testing.assert_allclose(T_diff[:3, 3], [10, 20, 30], atol=1e-10)
        np.testing.assert_allclose(T_diff[:3, :3], np.eye(3), atol=1e-10)

    def test_camera_extrinsics_roundtrip(self, dims):
        """T_world_cam = T_world_ee @ T_ee_cam  =>  T_ee_cam = inv(T_ee) @ T_cam."""
        ext = CameraExtrinsics(
            x_offset_mm=5, y_offset_mm=-10, z_offset_mm=30,
            roll_deg=10, pitch_deg=-90, yaw_deg=5,
        )
        fk = ForwardKinematics(dims, ext)
        angles = (45, 30, -20, 10)
        T_ee = fk.end_effector_pose(angles)
        T_cam = fk.camera_pose(angles)

        T_ee_cam = np.linalg.inv(T_ee) @ T_cam
        T_ext = fk._extrinsics_matrix()
        np.testing.assert_allclose(T_ee_cam, T_ext, atol=1e-10)


# ---------------------------------------------------------------------------
# Joint limits validation
# ---------------------------------------------------------------------------

class TestJointLimits:
    def test_all_zeros_valid(self):
        assert ForwardKinematics.validate_angles((0, 0, 0, 0)) is True

    def test_at_limits_valid(self):
        angles = tuple(float(hi) for _, hi in JOINT_LIMITS)
        assert ForwardKinematics.validate_angles(angles) is True

    def test_beyond_limits_invalid(self):
        angles = (0, 0, 0, 181)  # j4 max is 180
        assert ForwardKinematics.validate_angles(angles) is False

    def test_below_limits_invalid(self):
        angles = (-163, 0, 0, 0)  # j1 min is -162
        assert ForwardKinematics.validate_angles(angles) is False

    def test_wrong_count_invalid(self):
        assert ForwardKinematics.validate_angles((0, 0, 0)) is False

    def test_joint_to_se3_rejects_wrong_count(self, fk):
        with pytest.raises(ValueError, match="Expected 4"):
            fk.joint_to_se3((0, 0, 0))


# ---------------------------------------------------------------------------
# Round-trip: known position -> angles -> FK -> verify position
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_base_rotation_90(self, fk, dims):
        """Rotating base 90 deg should swing the arm along +Y instead of +X."""
        T = fk.end_effector_pose((90, 0, 0, 0))
        expected_z = (
            dims.base_height
            + dims.shoulder_length
            + dims.elbow_length
            + dims.wrist_length
        )
        pos = T[:3, 3]
        np.testing.assert_allclose(pos[0], 0, atol=1e-10)   # x ~ 0
        np.testing.assert_allclose(pos[1], 0, atol=1e-10)   # y ~ 0 (arm points up)
        np.testing.assert_allclose(pos[2], expected_z, atol=1e-10)

    def test_shoulder_90_extends_along_axis(self, fk, dims):
        """Shoulder at 90 deg tilts the arm into the XY plane.

        Standard rot_x(+90) maps Z -> -Y, so all links beyond the base
        end up along the -Y axis.
        """
        T = fk.end_effector_pose((0, 90, 0, 0))
        pos = T[:3, 3]

        # rot_x(90): local Z -> world -Y, so links point toward -Y
        expected_y = -(dims.shoulder_length + dims.elbow_length + dims.wrist_length)
        expected_z = dims.base_height

        np.testing.assert_allclose(pos[0], 0, atol=1e-10)
        np.testing.assert_allclose(pos[1], expected_y, atol=1e-10)
        np.testing.assert_allclose(pos[2], expected_z, atol=1e-10)

    def test_elbow_minus90_folds_back(self, fk, dims):
        """Shoulder 90, elbow -90 should fold the forearm back upward.

        After shoulder rot_x(+90) the shoulder link points along world -Y.
        Elbow rot_x(-90) cancels the shoulder rotation (net rotation = identity),
        so the elbow and wrist links extend back along world +Z.

        Expected position:
            x = 0
            y = -shoulder_length  (from the shoulder link along -Y)
            z = base_height + elbow_length + wrist_length  (vertical again)
        """
        T = fk.end_effector_pose((0, 90, -90, 0))
        pos = T[:3, 3]

        expected_y = -dims.shoulder_length
        expected_z = dims.base_height + dims.elbow_length + dims.wrist_length

        np.testing.assert_allclose(pos[0], 0, atol=1e-10)
        np.testing.assert_allclose(pos[1], expected_y, atol=1e-10)
        np.testing.assert_allclose(pos[2], expected_z, atol=1e-10)

    def test_full_reach(self, fk, dims):
        """Home position (all zero) should be at max Z height = sum of all links."""
        T = fk.end_effector_pose((0, 0, 0, 0))
        total = dims.base_height + dims.shoulder_length + dims.elbow_length + dims.wrist_length
        np.testing.assert_allclose(np.linalg.norm(T[:3, 3]), total, atol=1e-10)


# ---------------------------------------------------------------------------
# Camera intrinsics
# ---------------------------------------------------------------------------

class TestCameraIntrinsics:
    def test_shape(self):
        K = ForwardKinematics.camera_intrinsics_default()
        assert K.shape == (3, 3)

    def test_positive_focal_length(self):
        K = ForwardKinematics.camera_intrinsics_default()
        assert K[0, 0] > 0
        assert K[1, 1] > 0

    def test_principal_point_centred(self):
        K = ForwardKinematics.camera_intrinsics_default()
        np.testing.assert_allclose(K[0, 2], 960.0)
        np.testing.assert_allclose(K[1, 2], 540.0)

    def test_bottom_row(self):
        K = ForwardKinematics.camera_intrinsics_default()
        np.testing.assert_allclose(K[2, :], [0, 0, 1])


# ---------------------------------------------------------------------------
# Rotation helper sanity checks
# ---------------------------------------------------------------------------

class TestRotationHelpers:
    def test_rot_z_90(self):
        R = _rot_z(math.radians(90))
        # Should map X -> Y
        v = R @ np.array([1, 0, 0, 1])
        np.testing.assert_allclose(v[:3], [0, 1, 0], atol=1e-10)

    def test_rot_x_90(self):
        R = _rot_x(math.radians(90))
        # Should map Y -> Z
        v = R @ np.array([0, 1, 0, 1])
        np.testing.assert_allclose(v[:3], [0, 0, 1], atol=1e-10)

    def test_rot_y_90(self):
        R = _rot_y(math.radians(90))
        # Should map Z -> X
        v = R @ np.array([0, 0, 1, 1])
        np.testing.assert_allclose(v[:3], [1, 0, 0], atol=1e-10)

    def test_translation_helper(self):
        T = _translation(10, 20, 30)
        v = T @ np.array([0, 0, 0, 1])
        np.testing.assert_allclose(v[:3], [10, 20, 30])
