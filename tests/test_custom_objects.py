"""Tests for vision/custom_objects.py — custom object registration and matching."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from vision.custom_objects import (
    CustomObject,
    CustomObjectStore,
    _compute_histogram,
)


@pytest.fixture
def store(tmp_path):
    """Create a store using a temp directory."""
    return CustomObjectStore(store_dir=tmp_path)


@pytest.fixture
def red_frame():
    """A 400x400 BGR frame with a red object on gray background."""
    frame = np.full((400, 400, 3), 128, dtype=np.uint8)  # gray background
    frame[120:280, 120:280] = (0, 0, 200)  # red square in center
    return frame


@pytest.fixture
def blue_frame():
    """A 400x400 BGR frame with a blue object on gray background."""
    frame = np.full((400, 400, 3), 128, dtype=np.uint8)  # gray background
    frame[120:280, 120:280] = (200, 0, 0)  # blue square in center
    return frame


class TestComputeHistogram:
    def test_returns_flattened_array(self, red_frame):
        hist = _compute_histogram(red_frame)
        assert isinstance(hist, np.ndarray)
        assert hist.shape == (30 * 32,)

    def test_normalized(self, red_frame):
        hist = _compute_histogram(red_frame)
        assert hist.max() <= 1.0
        assert hist.min() >= 0.0

    def test_different_colors_different_histograms(self, red_frame, blue_frame):
        h1 = _compute_histogram(red_frame)
        h2 = _compute_histogram(blue_frame)
        assert not np.allclose(h1, h2)


class TestCustomObjectStore:
    def test_register_object(self, store, red_frame):
        success = store.register("red_thing", red_frame)
        assert success is True
        assert "red_thing" in store.names
        assert store.count == 1

    def test_register_saves_thumbnail(self, store, red_frame):
        store.register("red_thing", red_frame)
        thumb_path = store._dir / "red_thing_thumb.jpg"
        assert thumb_path.exists()

    def test_register_with_bbox(self, store, red_frame):
        success = store.register("red_thing", red_frame, bbox=(10, 10, 190, 190))
        assert success is True

    def test_register_empty_frame_fails(self, store):
        empty = np.array([], dtype=np.uint8)
        assert store.register("thing", empty) is False

    def test_register_none_frame_fails(self, store):
        assert store.register("thing", None) is False

    def test_unregister(self, store, red_frame):
        store.register("red_thing", red_frame)
        assert store.unregister("red_thing") is True
        assert "red_thing" not in store.names
        assert store.count == 0

    def test_unregister_nonexistent(self, store):
        assert store.unregister("nope") is False

    def test_get_registered_object(self, store, red_frame):
        store.register("red_thing", red_frame)
        obj = store.get("red_thing")
        assert obj is not None
        assert obj.name == "red_thing"
        assert obj.histogram is not None

    def test_get_nonexistent(self, store):
        assert store.get("nope") is None

    def test_find_matching_object(self, store, red_frame):
        store.register("red_thing", red_frame)
        # Finding in the same frame should match
        result = store.find("red_thing", red_frame)
        assert result is not None
        cx, cy, conf = result
        assert conf > 0.4

    def test_find_wrong_color_no_match(self, store, red_frame, blue_frame):
        store.register("red_thing", red_frame)
        # Finding red in a blue frame should fail
        result = store.find("red_thing", blue_frame)
        assert result is None

    def test_find_unregistered_returns_none(self, store, red_frame):
        assert store.find("nope", red_frame) is None

    def test_find_all(self, store, red_frame):
        store.register("red_thing", red_frame)
        results = store.find_all(red_frame)
        assert len(results) >= 1
        assert results[0][0] == "red_thing"

    def test_persistence_save_load(self, store, red_frame):
        store.register("red_thing", red_frame)
        store.register("another", red_frame)

        # Create new store pointing at same dir
        store2 = CustomObjectStore(store_dir=store._dir)
        assert store2.load() is True
        assert store2.count == 2
        assert "red_thing" in store2.names
        assert "another" in store2.names

        # Histogram survived serialization
        obj = store2.get("red_thing")
        assert obj.histogram is not None
        assert obj.histogram.shape == (30 * 32,)

    def test_persistence_empty_load(self, tmp_path):
        store = CustomObjectStore(store_dir=tmp_path)
        assert store.load() is False
        assert store.count == 0


class TestCustomObject:
    def test_to_dict_round_trip(self):
        hist = np.random.rand(960).astype(np.float32)
        obj = CustomObject(
            name="test",
            histogram=hist,
            registered_at=1000.0,
            times_found=5,
        )
        d = obj.to_dict()
        obj2 = CustomObject.from_dict(d)
        assert obj2.name == "test"
        assert obj2.times_found == 5
        assert np.allclose(obj2.histogram, hist)

    def test_from_dict_no_histogram(self):
        obj = CustomObject.from_dict({"name": "test", "histogram": None})
        assert obj.histogram is None


class TestRegexRegistration:
    def test_this_is_my(self):
        from voice_input import CommandParser
        p = CommandParser()
        r = p.parse("this is my notebook")
        assert r.action == "register"
        assert r.source_label == "notebook"

    def test_register_this_as(self):
        from voice_input import CommandParser
        p = CommandParser()
        r = p.parse("register this as my stress ball")
        assert r.action == "register"
        assert "stress ball" in r.source_label

    def test_call_this(self):
        from voice_input import CommandParser
        p = CommandParser()
        r = p.parse("call this the usb hub")
        assert r.action == "register"
        assert "usb hub" in r.source_label
