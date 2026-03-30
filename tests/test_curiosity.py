"""Tests for the curiosity engine."""

import time
import pytest
from pathlib import Path
from types import SimpleNamespace

from logic.curiosity import CuriosityEngine, CuriosityRecord


def _det(label, obj_id=None, position=None):
    """Create a mock detection."""
    return SimpleNamespace(
        label=label,
        object_id=obj_id or label,
        position=position,
        last_seen_position=position,
        confidence=0.9,
        center_x=100,
        center_y=100,
    )


class TestCuriosityRecord:
    def test_roundtrip(self):
        r = CuriosityRecord(
            object_id="cup_0", label="cup",
            curiosity_level=0.7, times_examined=2,
            last_position=(10.0, 20.0, 0.5),
        )
        d = r.to_dict()
        r2 = CuriosityRecord.from_dict(d)
        assert r2.object_id == "cup_0"
        assert r2.curiosity_level == 0.7
        assert r2.times_examined == 2
        assert r2.last_position == (10.0, 20.0, 0.5)


class TestCuriosityEngine:
    def test_new_object_gets_novelty_spike(self):
        engine = CuriosityEngine()
        engine.update([_det("cup", "cup_0", (10, 20, 0))], {})
        assert "cup_0" in engine.records
        assert engine.records["cup_0"].curiosity_level == engine.NOVELTY_SPIKE

    def test_known_object_no_spike(self):
        engine = CuriosityEngine()
        engine.update([_det("cup", "cup_0", (10, 20, 0))], {})
        initial = engine.records["cup_0"].curiosity_level
        engine.update([_det("cup", "cup_0", (10, 20, 0))], {})
        assert engine.records["cup_0"].curiosity_level == initial

    def test_moved_object_spikes(self):
        engine = CuriosityEngine()
        engine.update([_det("cup", "cup_0", (10, 20, 0))], {})
        # Reduce curiosity first
        engine.records["cup_0"].curiosity_level = 0.1
        # Move it far
        engine.update([_det("cup", "cup_0", (50, 60, 0))], {})
        assert engine.records["cup_0"].curiosity_level >= 0.1 + engine.MOVEMENT_SPIKE - 0.01

    def test_decay(self):
        engine = CuriosityEngine()
        engine.update([_det("cup", "cup_0", (10, 20, 0))], {})
        initial = engine.records["cup_0"].curiosity_level

        for _ in range(10):
            engine.tick()

        assert engine.records["cup_0"].curiosity_level < initial

    def test_decay_to_zero(self):
        engine = CuriosityEngine()
        engine.update([_det("cup", "cup_0", (10, 20, 0))], {})
        for _ in range(500):
            engine.tick()
        assert engine.records["cup_0"].curiosity_level == 0.0

    def test_get_most_curious(self):
        engine = CuriosityEngine()
        engine.update([
            _det("cup", "cup_0", (10, 20, 0)),
            _det("phone", "phone_0", (30, 40, 0)),
        ], {})
        engine.records["cup_0"].curiosity_level = 0.8
        engine.records["phone_0"].curiosity_level = 0.3

        most = engine.get_most_curious()
        assert most is not None
        assert most.object_id == "cup_0"

    def test_get_most_curious_below_threshold(self):
        engine = CuriosityEngine()
        engine.update([_det("cup", "cup_0", (10, 20, 0))], {})
        engine.records["cup_0"].curiosity_level = 0.1
        assert engine.get_most_curious() is None

    def test_examine_reduces_curiosity(self):
        engine = CuriosityEngine()
        engine.update([_det("cup", "cup_0", (10, 20, 0))], {})
        before = engine.records["cup_0"].curiosity_level
        engine.record_examination("cup_0")
        after = engine.records["cup_0"].curiosity_level
        assert after < before
        assert engine.records["cup_0"].times_examined == 1

    def test_examine_cooldown(self):
        engine = CuriosityEngine()
        engine.update([_det("cup", "cup_0", (10, 20, 0))], {})
        engine.record_examination("cup_0")
        # Just examined — should not return it even if curiosity is high
        engine.records["cup_0"].curiosity_level = 1.0
        engine.records["cup_0"].last_examined = time.time()
        assert engine.get_most_curious() is None

    def test_total_curiosity(self):
        engine = CuriosityEngine()
        engine.update([
            _det("cup", "cup_0", (10, 20, 0)),
            _det("phone", "phone_0", (30, 40, 0)),
        ], {})
        total = engine.total_curiosity
        assert total == pytest.approx(engine.NOVELTY_SPIKE * 2, abs=0.01)

    def test_save_load_roundtrip(self, tmp_path):
        path = tmp_path / "curiosity.json"
        engine = CuriosityEngine(session_number=3)
        engine.update([_det("cup", "cup_0", (10, 20, 0))], {})
        engine.records["cup_0"].times_examined = 2
        engine.save(path)

        engine2 = CuriosityEngine()
        engine2.load(path)
        assert "cup_0" in engine2.records
        assert engine2.records["cup_0"].times_examined == 2
        assert engine2._session == 4  # incremented

    def test_cross_session_halves_curiosity(self, tmp_path):
        path = tmp_path / "curiosity.json"
        engine = CuriosityEngine()
        engine.update([_det("cup", "cup_0", (10, 20, 0))], {})
        engine.records["cup_0"].curiosity_level = 0.8
        engine.records["cup_0"].times_examined = 1  # examined, so no boost on load
        engine.save(path)

        engine2 = CuriosityEngine()
        engine2.load(path)
        assert engine2.records["cup_0"].curiosity_level == pytest.approx(0.4, abs=0.01)

    def test_cross_session_boosts_unexamined(self, tmp_path):
        path = tmp_path / "curiosity.json"
        engine = CuriosityEngine()
        engine.update([_det("cup", "cup_0", (10, 20, 0))], {})
        engine.records["cup_0"].curiosity_level = 0.2
        engine.records["cup_0"].times_examined = 0  # never examined
        engine.save(path)

        engine2 = CuriosityEngine()
        engine2.load(path)
        # 0.2 * 0.5 + 0.2 boost = 0.3
        assert engine2.records["cup_0"].curiosity_level == pytest.approx(0.3, abs=0.01)

    def test_clear(self):
        engine = CuriosityEngine()
        engine.update([_det("cup", "cup_0", (10, 20, 0))], {})
        engine.clear()
        assert len(engine.records) == 0

    def test_load_nonexistent_returns_false(self, tmp_path):
        engine = CuriosityEngine()
        assert engine.load(tmp_path / "nope.json") is False
