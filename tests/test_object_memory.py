"""Tests for logic/object_memory.py — persistent object memory."""

import json
import time
from pathlib import Path

import pytest

from logic.object_memory import ObjectMemory, ObjectRecord, DeskSnapshot


@pytest.fixture
def tmp_memory(tmp_path):
    return ObjectMemory(path=tmp_path / "memory.json")


class TestObjectRecord:
    def test_to_dict(self):
        rec = ObjectRecord(
            object_id="cup_0", label="cup",
            preferred_position=(10.0, 20.0, 0.5),
            confidence=0.8, times_placed=3,
        )
        d = rec.to_dict()
        assert d["object_id"] == "cup_0"
        assert d["label"] == "cup"
        assert d["preferred_position"] == [10.0, 20.0, 0.5]
        assert d["confidence"] == 0.8

    def test_from_dict_roundtrip(self):
        rec = ObjectRecord(
            object_id="laptop_0", label="laptop",
            preferred_position=(0, 5, 0),
            last_seen_position=(0, 5, 0),
            confidence=0.5, times_placed=2, times_overridden=1,
            first_seen=1000.0, last_seen=2000.0, session_count=3,
        )
        d = rec.to_dict()
        rec2 = ObjectRecord.from_dict(d)
        assert rec2.object_id == "laptop_0"
        assert rec2.label == "laptop"
        assert rec2.times_placed == 2
        assert rec2.session_count == 3

    def test_has_moved_false_when_same(self):
        rec = ObjectRecord(
            object_id="cup_0", label="cup",
            preferred_position=(10, 20, 0.5),
            last_seen_position=(10, 20, 0.5),
        )
        assert rec.has_moved is False

    def test_has_moved_true_when_different(self):
        rec = ObjectRecord(
            object_id="cup_0", label="cup",
            preferred_position=(10, 20, 0.5),
            last_seen_position=(30, 20, 0.5),
        )
        assert rec.has_moved is True

    def test_has_moved_false_when_no_preferred(self):
        rec = ObjectRecord(object_id="cup_0", label="cup")
        assert rec.has_moved is False


class TestObjectMemory:
    def test_starts_empty(self, tmp_memory):
        assert tmp_memory.object_count == 0

    def test_observe_creates_record(self, tmp_memory):
        rec = tmp_memory.observe("cup_0", "cup", position=(10, 20, 0.5))
        assert rec.object_id == "cup_0"
        assert rec.label == "cup"
        assert tmp_memory.object_count == 1

    def test_observe_updates_existing(self, tmp_memory):
        tmp_memory.observe("cup_0", "cup", position=(10, 20, 0.5))
        tmp_memory.observe("cup_0", "cup", position=(12, 22, 0.5))
        assert tmp_memory.object_count == 1
        rec = tmp_memory.get_object("cup_0")
        assert rec.last_seen_position == (12, 22, 0.5)

    def test_record_placement(self, tmp_memory):
        tmp_memory.observe("cup_0", "cup")
        tmp_memory.record_placement("cup_0", (10, 20, 0.5))
        rec = tmp_memory.get_object("cup_0")
        assert rec.preferred_position == (10, 20, 0.5)
        assert rec.times_placed == 1
        assert rec.confidence > 0

    def test_record_override(self, tmp_memory):
        tmp_memory.observe("cup_0", "cup")
        tmp_memory.record_placement("cup_0", (10, 20, 0.5))
        tmp_memory.record_override("cup_0", (30, 20, 0.5))
        rec = tmp_memory.get_object("cup_0")
        assert rec.times_overridden == 1
        assert rec.last_seen_position == (30, 20, 0.5)

    def test_save_and_load(self, tmp_memory):
        tmp_memory.observe("cup_0", "cup", (10, 20, 0.5))
        tmp_memory.observe("laptop_0", "laptop", (0, 5, 0))
        assert tmp_memory.save() is True

        loaded = ObjectMemory(path=tmp_memory.path)
        assert loaded.load() is True
        assert loaded.object_count == 2
        assert loaded.get_object("cup_0").label == "cup"

    def test_load_increments_session_count(self, tmp_memory):
        tmp_memory.observe("cup_0", "cup")
        tmp_memory.save()

        loaded = ObjectMemory(path=tmp_memory.path)
        loaded.load()
        assert loaded.get_object("cup_0").session_count == 2

    def test_load_nonexistent_file(self, tmp_path):
        mem = ObjectMemory(path=tmp_path / "nope.json")
        assert mem.load() is False
        assert mem.object_count == 0

    def test_get_moved_objects(self, tmp_memory):
        tmp_memory.observe("cup_0", "cup")
        tmp_memory.record_placement("cup_0", (10, 20, 0.5))
        tmp_memory.record_override("cup_0", (30, 20, 0.5))
        moved = tmp_memory.get_moved_objects()
        assert len(moved) == 1
        assert moved[0].object_id == "cup_0"

    def test_get_objects_by_label(self, tmp_memory):
        tmp_memory.observe("cup_0", "cup")
        tmp_memory.observe("cup_1", "cup")
        tmp_memory.observe("laptop_0", "laptop")
        cups = tmp_memory.get_objects_by_label("cup")
        assert len(cups) == 2

    def test_forget(self, tmp_memory):
        tmp_memory.observe("cup_0", "cup")
        assert tmp_memory.forget("cup_0") is True
        assert tmp_memory.object_count == 0
        assert tmp_memory.forget("nonexistent") is False

    def test_clear(self, tmp_memory):
        tmp_memory.observe("cup_0", "cup")
        tmp_memory.observe("laptop_0", "laptop")
        tmp_memory.clear()
        assert tmp_memory.object_count == 0

    def test_needs_save(self, tmp_memory):
        assert tmp_memory.needs_save is False
        tmp_memory.observe("cup_0", "cup")
        assert tmp_memory.needs_save is True
        tmp_memory.save()
        assert tmp_memory.needs_save is False


class TestDeskSnapshot:
    def test_roundtrip(self):
        snap = DeskSnapshot(session_start=1000.0, last_save=2000.0)
        snap.objects["cup_0"] = ObjectRecord(object_id="cup_0", label="cup")
        d = snap.to_dict()
        snap2 = DeskSnapshot.from_dict(d)
        assert len(snap2.objects) == 1
        assert snap2.session_start == 1000.0
