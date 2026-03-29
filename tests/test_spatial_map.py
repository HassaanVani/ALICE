"""Tests for vision/spatial_map.py — 3D spatial mapping."""

import numpy as np
import pytest

from vision.spatial_map import SpatialMap, SpatialObject, SpatialMapState


@pytest.fixture
def spatial_map():
    sm = SpatialMap()
    sm._simulate = True
    sm.initialize()
    return sm


class TestSpatialObject:
    def test_distance_to(self):
        a = SpatialObject(label="cup", position_cm=(10, 0, 0))
        b = SpatialObject(label="laptop", position_cm=(20, 0, 0))
        assert abs(a.distance_to(b) - 10.0) < 0.01

    def test_distance_to_3d(self):
        a = SpatialObject(label="cup", position_cm=(0, 0, 0))
        b = SpatialObject(label="laptop", position_cm=(3, 4, 0))
        assert abs(a.distance_to(b) - 5.0) < 0.01

    def test_to_dict(self):
        obj = SpatialObject(label="cup", position_cm=(10.123, 20.456, 0.5),
                            confidence=0.85)
        d = obj.to_dict()
        assert d["label"] == "cup"
        assert d["position_cm"] == [10.1, 20.5, 0.5]
        assert d["confidence"] == 0.85


class TestSpatialMapState:
    def test_to_dict(self):
        state = SpatialMapState(
            objects=[SpatialObject(label="cup", position_cm=(10, 20, 0))],
            frame_count=5,
        )
        d = state.to_dict()
        assert d["frame_count"] == 5
        assert len(d["objects"]) == 1


class TestSpatialMap:
    def test_initialize(self, spatial_map):
        assert spatial_map.simulate is True
        assert spatial_map.frame_count == 0

    def test_integrate_frame_increments_count(self, spatial_map):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        depth = np.ones((480, 640), dtype=np.float32) * 0.4
        pose = np.eye(4)
        spatial_map.integrate_frame(frame, depth, pose)
        assert spatial_map.frame_count == 1

    def test_extract_point_cloud(self, spatial_map):
        pcd = spatial_map.extract_point_cloud()
        assert pcd is not None
        assert pcd.shape[1] == 6  # x, y, z, r, g, b
        assert len(pcd) > 0

    def test_place_object_in_3d(self, spatial_map):
        pose = np.eye(4)
        pose[2, 3] = 0.4  # camera 40cm above desk
        obj = spatial_map.place_object_in_3d(
            label="cup", pixel_x=960, pixel_y=540,
            depth_m=0.4, camera_pose=pose,
        )
        assert obj.label == "cup"
        assert len(obj.position_cm) == 3

    def test_get_distance_between(self, spatial_map):
        pose = np.eye(4)
        spatial_map.place_object_in_3d("cup", 100, 100, 0.4, pose)
        spatial_map.place_object_in_3d("laptop", 500, 100, 0.4, pose)
        dist = spatial_map.get_distance_between("cup", "laptop")
        assert dist is not None
        assert dist > 0

    def test_get_distance_unknown_object(self, spatial_map):
        assert spatial_map.get_distance_between("cup", "banana") is None

    def test_get_state(self, spatial_map):
        pose = np.eye(4)
        spatial_map.place_object_in_3d("cup", 100, 100, 0.4, pose)
        state = spatial_map.get_state()
        assert state.frame_count == 0
        assert len(state.objects) == 1
        d = state.to_dict()
        assert "objects" in d

    def test_reset(self, spatial_map):
        pose = np.eye(4)
        spatial_map.place_object_in_3d("cup", 100, 100, 0.4, pose)
        spatial_map.integrate_frame(
            np.zeros((480, 640, 3), dtype=np.uint8),
            np.ones((480, 640), dtype=np.float32) * 0.4,
            pose,
        )
        spatial_map.reset()
        assert spatial_map.frame_count == 0
        assert len(spatial_map.spatial_objects) == 0

    def test_spatial_objects_property(self, spatial_map):
        pose = np.eye(4)
        spatial_map.place_object_in_3d("cup", 100, 100, 0.4, pose)
        objs = spatial_map.spatial_objects
        assert "cup" in objs
        assert isinstance(objs["cup"], SpatialObject)
