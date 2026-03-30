"""Tests for the learned habits system."""

import pytest
from pathlib import Path
from types import SimpleNamespace

from logic.habits import HabitEngine, BehaviorPattern, Habit


def _obj(oid, label, pos):
    """Create a mock ObjectRecord."""
    return SimpleNamespace(
        object_id=oid, label=label,
        last_seen_position=pos,
        preferred_position=pos,
        has_moved=False,
    )


class TestBehaviorPattern:
    def test_roundtrip(self):
        p = BehaviorPattern(
            pattern_id="abc", pattern_type="placement",
            description="cup near (10, 20)",
            objects_involved=["cup_0"],
            observations=5, confidence=0.8,
            centroid=(10.0, 20.0, 0.0), std_dev=3.0,
        )
        d = p.to_dict()
        p2 = BehaviorPattern.from_dict(d)
        assert p2.pattern_id == "abc"
        assert p2.centroid == (10.0, 20.0, 0.0)
        assert p2.observations == 5


class TestHabit:
    def test_roundtrip(self):
        h = Habit(
            habit_id="h1", trigger="cup appears",
            action="nudge_to_position",
            action_data={"target_position": [10, 20, 0]},
            strength=0.6, times_executed=3,
        )
        d = h.to_dict()
        h2 = Habit.from_dict(d)
        assert h2.habit_id == "h1"
        assert h2.strength == 0.6
        assert h2.action_data["target_position"] == [10, 20, 0]


class TestHabitEngine:
    def test_placement_pattern_detection(self):
        engine = HabitEngine()
        engine.MIN_OBSERVATIONS = 3

        # Place cup in similar but distinct positions (>2cm apart to register)
        positions = [(10, 20, 0), (13, 22, 0), (11, 21, 0), (12, 20, 0), (10, 23, 0)]
        for pos in positions:
            objects = {"cup_0": _obj("cup_0", "cup", pos)}
            engine.observe_snapshot(objects)

        assert len(engine.patterns) > 0
        placement_pats = [p for p in engine.patterns.values() if p.pattern_type == "placement"]
        assert len(placement_pats) > 0

    def test_habit_generated_from_pattern(self):
        engine = HabitEngine()
        engine.MIN_OBSERVATIONS = 3

        positions = [(10, 20, 0), (13, 22, 0), (11, 21, 0), (12, 20, 0), (10, 23, 0)]
        for pos in positions:
            objects = {"cup_0": _obj("cup_0", "cup", pos)}
            engine.observe_snapshot(objects)

        assert len(engine.habits) > 0
        habit = list(engine.habits.values())[0]
        assert habit.action == "nudge_to_position"
        assert habit.strength > 0

    def test_habit_strength_grows(self):
        engine = HabitEngine()
        engine.MIN_OBSERVATIONS = 2

        positions = [(10, 20, 0), (13, 22, 0), (11, 21, 0), (12, 20, 0), (10, 23, 0), (14, 21, 0)]
        for pos in positions:
            objects = {"cup_0": _obj("cup_0", "cup", pos)}
            engine.observe_snapshot(objects)

        habits = list(engine.habits.values())
        assert len(habits) > 0
        assert habits[0].strength > engine.STRENGTH_INCREMENT

    def test_user_undo_weakens_habit(self):
        engine = HabitEngine()
        engine.MIN_OBSERVATIONS = 2

        positions = [(10, 20, 0), (13, 22, 0), (11, 21, 0), (12, 20, 0)]
        for pos in positions:
            objects = {"cup_0": _obj("cup_0", "cup", pos)}
            engine.observe_snapshot(objects)

        habits = list(engine.habits.values())
        assert len(habits) > 0
        hid = habits[0].habit_id
        initial_strength = habits[0].strength

        engine.record_user_undo(hid)
        assert engine.habits[hid].strength < initial_strength

    def test_habit_deactivation(self):
        engine = HabitEngine()
        engine.MIN_OBSERVATIONS = 2
        engine.DEACTIVATION_THRESHOLD = 2

        positions = [(10, 20, 0), (13, 22, 0), (11, 21, 0), (12, 20, 0)]
        for pos in positions:
            engine.observe_snapshot({"cup_0": _obj("cup_0", "cup", pos)})

        hid = list(engine.habits.keys())[0]
        engine.record_user_undo(hid)
        engine.record_user_undo(hid)

        assert engine.habits[hid].active is False

    def test_record_execution(self):
        engine = HabitEngine()
        engine.MIN_OBSERVATIONS = 2

        positions = [(10, 20, 0), (13, 22, 0), (11, 21, 0), (12, 20, 0)]
        for pos in positions:
            engine.observe_snapshot({"cup_0": _obj("cup_0", "cup", pos)})

        hid = list(engine.habits.keys())[0]
        engine.record_execution(hid)
        assert engine.habits[hid].times_executed == 1

    def test_triggered_habit_placement(self):
        engine = HabitEngine()
        engine.MIN_OBSERVATIONS = 2

        # Build habit: cup placed near cluster around (11, 21, 0)
        positions = [(10, 20, 0), (13, 22, 0), (11, 21, 0), (12, 20, 0)]
        for pos in positions:
            engine.observe_snapshot({"cup_0": _obj("cup_0", "cup", pos)})

        # Now cup is far from target
        current = {"cup_0": _obj("cup_0", "cup", (50, 60, 0))}
        triggered = engine.get_triggered_habits(current, mood=0.8)
        assert len(triggered) > 0
        assert triggered[0].action == "nudge_to_position"

    def test_no_trigger_when_in_position(self):
        engine = HabitEngine()
        engine.MIN_OBSERVATIONS = 2

        positions = [(10, 20, 0), (13, 22, 0), (11, 21, 0), (12, 20, 0)]
        for pos in positions:
            engine.observe_snapshot({"cup_0": _obj("cup_0", "cup", pos)})

        # Cup is already near the cluster centroid — should not trigger
        current = {"cup_0": _obj("cup_0", "cup", (11, 21, 0))}
        triggered = engine.get_triggered_habits(current, mood=0.8)
        assert len(triggered) == 0

    def test_relational_pattern(self):
        engine = HabitEngine()
        engine.MIN_OBSERVATIONS = 2

        # Cup and phone always near each other
        for i in range(4):
            engine.observe_snapshot({
                "cup_0": _obj("cup_0", "cup", (10, 20, 0)),
                "phone_0": _obj("phone_0", "phone", (12, 22, 0)),
            })

        relational = [p for p in engine.patterns.values() if p.pattern_type == "relational"]
        assert len(relational) > 0

    def test_sequence_pattern(self):
        engine = HabitEngine()
        engine.MIN_OBSERVATIONS = 2

        # Repeated A-then-B events
        import time
        for _ in range(4):
            engine.observe_event("moved", "cup_0")
            engine.observe_event("moved", "phone_0")

        sequences = [p for p in engine.patterns.values() if p.pattern_type == "sequence"]
        assert len(sequences) > 0

    def test_save_load_roundtrip(self, tmp_path):
        path = tmp_path / "habits.json"
        engine = HabitEngine()
        engine.MIN_OBSERVATIONS = 2

        positions = [(10, 20, 0), (13, 22, 0), (11, 21, 0), (12, 20, 0)]
        for pos in positions:
            engine.observe_snapshot({"cup_0": _obj("cup_0", "cup", pos)})

        engine.save(path)

        engine2 = HabitEngine()
        engine2.load(path)
        assert len(engine2.patterns) == len(engine.patterns)
        assert len(engine2.habits) == len(engine.habits)

    def test_clear(self):
        engine = HabitEngine()
        engine.MIN_OBSERVATIONS = 2
        positions = [(10, 20, 0), (13, 22, 0), (11, 21, 0), (12, 20, 0)]
        for pos in positions:
            engine.observe_snapshot({"cup_0": _obj("cup_0", "cup", pos)})
        engine.clear()
        assert len(engine.patterns) == 0
        assert len(engine.habits) == 0

    def test_active_habit_count(self):
        engine = HabitEngine()
        engine.MIN_OBSERVATIONS = 2
        positions = [(10, 20, 0), (13, 22, 0), (11, 21, 0), (12, 20, 0)]
        for pos in positions:
            engine.observe_snapshot({"cup_0": _obj("cup_0", "cup", pos)})
        assert engine.active_habit_count > 0

    def test_tick_decays_strength(self):
        engine = HabitEngine()
        engine.MIN_OBSERVATIONS = 2
        positions = [(10, 20, 0), (13, 22, 0), (11, 21, 0), (12, 20, 0)]
        for pos in positions:
            engine.observe_snapshot({"cup_0": _obj("cup_0", "cup", pos)})

        h = list(engine.habits.values())[0]
        before = h.strength
        for _ in range(10):
            engine.tick()
        assert h.strength < before
