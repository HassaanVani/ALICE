"""Tests for gaze tracking / head following."""

import pytest

from logic.gaze_tracker import GazeTracker, GazeTarget


class TestGazeTracker:
    def test_initial_target_is_scan(self):
        gaze = GazeTracker()
        target = gaze.get_target()
        assert target.target_type == "scan"
        assert target.priority == 0.1

    def test_face_updates_target(self):
        gaze = GazeTracker(alpha=1.0)  # instant tracking for test
        gaze.update_face({
            "center_x": 640,
            "center_y": 360,
            "distance_cm": 60,
        })
        target = gaze.get_target()
        assert target.target_type == "face"
        assert target.label == "user"
        assert target.priority == 0.8

    def test_face_center_maps_to_zero(self):
        gaze = GazeTracker(alpha=1.0)
        # Center of frame should map to near-zero j1
        gaze.update_face({
            "center_x": 640,  # center of 1280
            "center_y": 360,  # center of 720
        })
        target = gaze.get_target()
        assert abs(target.angles[0]) < 2.0  # j1 near zero

    def test_face_left_maps_positive_j1(self):
        gaze = GazeTracker(alpha=1.0)
        gaze.update_face({
            "center_x": 100,  # far left
            "center_y": 360,
        })
        target = gaze.get_target()
        assert target.angles[0] > 10.0  # turn left (positive j1)

    def test_face_right_maps_negative_j1(self):
        gaze = GazeTracker(alpha=1.0)
        gaze.update_face({
            "center_x": 1200,  # far right
            "center_y": 360,
        })
        target = gaze.get_target()
        assert target.angles[0] < -10.0  # turn right (negative j1)

    def test_curiosity_target_overrides_scan(self):
        gaze = GazeTracker(alpha=1.0)
        gaze.set_curiosity_target("cup", 500, 400)
        target = gaze.get_target()
        assert target.target_type == "object"
        assert target.label == "cup"
        assert target.priority == 0.6

    def test_face_overrides_curiosity(self):
        gaze = GazeTracker(alpha=1.0)
        gaze.set_curiosity_target("cup", 500, 400)
        gaze.update_face({"center_x": 640, "center_y": 360})
        target = gaze.get_target()
        assert target.target_type == "face"

    def test_clear_curiosity_returns_to_scan(self):
        gaze = GazeTracker(alpha=1.0)
        gaze.set_curiosity_target("cup", 500, 400)
        gaze.clear_curiosity_target()
        target = gaze.get_target()
        assert target.target_type == "scan"

    def test_smooth_interpolation(self):
        gaze = GazeTracker(alpha=0.1)  # slow tracking
        gaze.update_face({"center_x": 100, "center_y": 360})

        # First get — should be partially toward target
        t1 = gaze.get_target()
        # Second get — should be further toward target
        t2 = gaze.get_target()

        # Both should be face targets but t2 should be closer to final
        assert t1.target_type == "face"
        assert abs(t2.angles[0]) > abs(t1.angles[0]) or abs(t2.angles[0] - t1.angles[0]) < 1

    def test_face_timeout(self):
        gaze = GazeTracker(alpha=1.0)
        gaze.update_face({"center_x": 640, "center_y": 360})
        # Simulate timeout by setting face_time in the past
        gaze._face_time = 0
        target = gaze.get_target()
        assert target.target_type != "face"

    def test_reset(self):
        gaze = GazeTracker()
        gaze.update_face({"center_x": 100, "center_y": 100})
        gaze.set_curiosity_target("mug", 300, 300)
        gaze.reset()
        assert gaze._face_target is None
        assert gaze._curiosity_target is None
        target = gaze.get_target()
        assert target.target_type == "scan"

    @pytest.mark.asyncio
    async def test_apply_moves_arm(self):
        from hardware.arm_controller import ArmController
        from hardware.dynamics import MovementDynamics

        arm = ArmController(simulate=True)
        arm.connect()
        dynamics = MovementDynamics(arm)

        gaze = GazeTracker(alpha=1.0)
        gaze.update_face({"center_x": 200, "center_y": 300})
        await gaze.apply(dynamics)

        pos = arm.position.as_tuple()
        # Arm should have moved from home (0,0,0,0)
        assert any(abs(a) > 0.1 for a in pos)
