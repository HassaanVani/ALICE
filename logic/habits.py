"""Learned habits — ALICE develops quirks from observing you.

No pre-programmed gags. ALICE watches what you do with objects over multiple
sessions, detects repeating patterns, and develops habits around them. If you
always put your coffee in the same spot, she starts nudging it there. If you
undo what she does, the habit weakens and eventually dies.

Quirks emerge. They aren't scripted.

Pattern types:
  - Placement: "user always puts X at position Y"
  - Sequence: "user moves X, then moves Y within 5 minutes"
  - Relational: "X is always near Y"
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("Habits")


@dataclass
class BehaviorPattern:
    """A detected pattern in user behavior."""
    pattern_id: str
    pattern_type: str             # "placement", "sequence", "relational"
    description: str
    objects_involved: List[str]
    observations: int = 0
    confidence: float = 0.0
    first_observed: float = 0.0
    last_observed: float = 0.0
    # Type-specific data
    centroid: Optional[Tuple[float, float, float]] = None  # for placement
    std_dev: float = float("inf")
    sequence_gap_s: float = 0.0   # avg time between events in sequence
    proximity_cm: float = 0.0     # avg distance for relational

    def to_dict(self) -> dict:
        d = {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "description": self.description,
            "objects_involved": self.objects_involved,
            "observations": self.observations,
            "confidence": round(self.confidence, 3),
            "first_observed": self.first_observed,
            "last_observed": self.last_observed,
            "std_dev": round(self.std_dev, 2) if self.std_dev != float("inf") else None,
            "sequence_gap_s": round(self.sequence_gap_s, 1),
            "proximity_cm": round(self.proximity_cm, 1),
        }
        if self.centroid:
            d["centroid"] = [round(v, 1) for v in self.centroid]
        return d

    @staticmethod
    def from_dict(data: dict) -> "BehaviorPattern":
        c = data.get("centroid")
        return BehaviorPattern(
            pattern_id=data["pattern_id"],
            pattern_type=data["pattern_type"],
            description=data.get("description", ""),
            objects_involved=data.get("objects_involved", []),
            observations=data.get("observations", 0),
            confidence=data.get("confidence", 0.0),
            first_observed=data.get("first_observed", 0.0),
            last_observed=data.get("last_observed", 0.0),
            centroid=tuple(c) if c else None,
            std_dev=data.get("std_dev") or float("inf"),
            sequence_gap_s=data.get("sequence_gap_s", 0.0),
            proximity_cm=data.get("proximity_cm", 0.0),
        )


@dataclass
class Habit:
    """An emergent behavior ALICE developed from observing patterns."""
    habit_id: str
    trigger: str                  # human-readable trigger condition
    action: str                   # what ALICE does (e.g. "nudge_to_position")
    action_data: dict = field(default_factory=dict)  # params for the action
    pattern_id: str = ""
    strength: float = 0.0        # 0.0-1.0, grows with observation
    times_executed: int = 0
    times_user_undid: int = 0
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "habit_id": self.habit_id,
            "trigger": self.trigger,
            "action": self.action,
            "action_data": self.action_data,
            "pattern_id": self.pattern_id,
            "strength": round(self.strength, 3),
            "times_executed": self.times_executed,
            "times_user_undid": self.times_user_undid,
            "active": self.active,
        }

    @staticmethod
    def from_dict(data: dict) -> "Habit":
        return Habit(
            habit_id=data["habit_id"],
            trigger=data["trigger"],
            action=data["action"],
            action_data=data.get("action_data", {}),
            pattern_id=data.get("pattern_id", ""),
            strength=data.get("strength", 0.0),
            times_executed=data.get("times_executed", 0),
            times_user_undid=data.get("times_user_undid", 0),
            active=data.get("active", True),
        )


def _make_id(*parts: str) -> str:
    """Generate a short deterministic ID from string parts."""
    h = hashlib.md5(":".join(parts).encode()).hexdigest()[:8]
    return h


class HabitEngine:
    """Observes user behavior patterns and generates emergent habits.

    Usage:
        engine = HabitEngine()
        engine.observe_snapshot(current_objects)  # call every ~30s
        engine.observe_event("moved", "cup_0", {"position": (10, 20, 0)})

        triggered = engine.get_triggered_habits(current_objects)
        for habit in triggered:
            # ... execute habit ...
            engine.record_execution(habit.habit_id)
    """

    MIN_OBSERVATIONS = 3         # pattern must be seen N times → habit
    STRENGTH_INCREMENT = 0.15    # per additional observation
    UNDO_PENALTY = 0.25          # per user undo
    DEACTIVATION_THRESHOLD = 3   # undos before habit deactivated
    PLACEMENT_STD_THRESHOLD = 8.0  # cm — tight cluster = pattern
    PROXIMITY_THRESHOLD = 15.0   # cm — objects "near" each other
    SEQUENCE_WINDOW = 300.0      # seconds — events within this = sequence
    MIN_STRENGTH_TO_FIRE = 0.3   # habit must be this strong to trigger

    def __init__(self):
        self._patterns: Dict[str, BehaviorPattern] = {}
        self._habits: Dict[str, Habit] = {}

        # Rolling event log for sequence detection
        self._events: List[dict] = []
        self._max_events = 200

        # Placement history: object_id → list of (position, timestamp)
        self._placement_history: Dict[str, List[Tuple[Tuple[float, ...], float]]] = {}

    @property
    def patterns(self) -> Dict[str, BehaviorPattern]:
        return dict(self._patterns)

    @property
    def habits(self) -> Dict[str, Habit]:
        return dict(self._habits)

    @property
    def active_habit_count(self) -> int:
        return sum(1 for h in self._habits.values() if h.active)

    def observe_snapshot(self, current_objects: dict) -> None:
        """Take a snapshot of current object positions. Call periodically (~30s).

        Args:
            current_objects: dict of object_id → ObjectRecord from ObjectMemory.
        """
        now = time.time()

        for oid, obj in current_objects.items():
            pos = getattr(obj, 'last_seen_position', None)
            if pos is None:
                continue

            pos = tuple(pos)

            # Track placement history
            if oid not in self._placement_history:
                self._placement_history[oid] = []

            history = self._placement_history[oid]

            # Only record if position changed from last record
            if history and self._distance(history[-1][0], pos) < 2.0:
                continue

            history.append((pos, now))

            # Keep history bounded
            if len(history) > 50:
                history[:] = history[-50:]

            # Check for placement pattern
            self._check_placement_pattern(oid, obj, history)

        # Check relational patterns between all object pairs
        self._check_relational_patterns(current_objects)

    def observe_event(self, event_type: str, object_id: str,
                      details: Optional[dict] = None) -> None:
        """Record a discrete event (object moved, picked up, etc)."""
        now = time.time()
        self._events.append({
            "type": event_type,
            "object_id": object_id,
            "time": now,
            "details": details or {},
        })

        # Trim event log
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

        # Check for sequence patterns
        self._check_sequence_patterns()

    def get_triggered_habits(self, current_objects: dict,
                             mood: float = 0.5) -> List[Habit]:
        """Check which habits should fire right now.

        Args:
            current_objects: current desk state.
            mood: personality mood (0-1). Lower mood = higher threshold.
        """
        triggered = []
        mood_threshold = self.MIN_STRENGTH_TO_FIRE + (1.0 - mood) * 0.1

        for habit in self._habits.values():
            if not habit.active:
                continue
            if habit.strength < mood_threshold:
                continue

            # Check trigger conditions
            if self._is_triggered(habit, current_objects):
                triggered.append(habit)

        return triggered

    def record_execution(self, habit_id: str) -> None:
        """Called after ALICE executes a habit."""
        if habit_id in self._habits:
            self._habits[habit_id].times_executed += 1

    def record_user_undo(self, habit_id: str) -> None:
        """User undid what ALICE's habit did. Weakens the habit."""
        if habit_id not in self._habits:
            return

        habit = self._habits[habit_id]
        habit.times_user_undid += 1
        habit.strength = max(0.0, habit.strength - self.UNDO_PENALTY)

        if habit.times_user_undid >= self.DEACTIVATION_THRESHOLD:
            habit.active = False
            logger.info(
                f"Habit deactivated (too many undos): {habit.habit_id} — {habit.trigger}"
            )

    def tick(self) -> None:
        """Periodic maintenance. Call occasionally (not every frame)."""
        # Very slow strength decay on unused habits
        for habit in self._habits.values():
            if habit.active and habit.strength > 0:
                habit.strength = max(0.0, habit.strength - 0.001)

    # --- Pattern detection ---

    def _check_placement_pattern(self, oid: str, obj, history: list) -> None:
        """Check if an object is consistently placed in the same spot."""
        if len(history) < self.MIN_OBSERVATIONS:
            return

        recent = history[-self.MIN_OBSERVATIONS:]
        positions = [p for p, _ in recent]

        # Compute centroid
        n = len(positions)
        centroid = tuple(
            sum(p[i] for p in positions) / n
            for i in range(min(3, len(positions[0])))
        )

        # Compute std dev from centroid
        std = (sum(
            sum((p[i] - centroid[i]) ** 2 for i in range(len(centroid)))
            for p in positions
        ) / n) ** 0.5

        if std > self.PLACEMENT_STD_THRESHOLD:
            return  # too scattered, no pattern

        pid = _make_id("placement", oid)
        label = getattr(obj, 'label', oid)
        now = time.time()

        if pid in self._patterns:
            pat = self._patterns[pid]
            pat.observations = len(history)
            pat.confidence = min(1.0, 1.0 - std / self.PLACEMENT_STD_THRESHOLD)
            pat.last_observed = now
            pat.centroid = centroid
            pat.std_dev = std
        else:
            self._patterns[pid] = BehaviorPattern(
                pattern_id=pid,
                pattern_type="placement",
                description=f"{label} consistently placed near ({centroid[0]:.0f}, {centroid[1]:.0f})",
                objects_involved=[oid],
                observations=len(history),
                confidence=min(1.0, 1.0 - std / self.PLACEMENT_STD_THRESHOLD),
                first_observed=history[0][1],
                last_observed=now,
                centroid=centroid,
                std_dev=std,
            )

        # Generate or update habit
        self._maybe_create_habit(pid)

    def _check_sequence_patterns(self) -> None:
        """Check for A-then-B event sequences."""
        if len(self._events) < 2:
            return

        # Look at recent event pairs
        recent = self._events[-20:]
        pair_counts: Dict[Tuple[str, str], List[float]] = {}

        for i in range(len(recent)):
            for j in range(i + 1, len(recent)):
                a, b = recent[i], recent[j]
                gap = b["time"] - a["time"]
                if gap > self.SEQUENCE_WINDOW:
                    break
                if a["object_id"] == b["object_id"]:
                    continue

                pair = (a["object_id"], b["object_id"])
                if pair not in pair_counts:
                    pair_counts[pair] = []
                pair_counts[pair].append(gap)

        for (a_id, b_id), gaps in pair_counts.items():
            if len(gaps) < self.MIN_OBSERVATIONS:
                continue

            avg_gap = sum(gaps) / len(gaps)
            pid = _make_id("sequence", a_id, b_id)
            now = time.time()

            if pid not in self._patterns:
                self._patterns[pid] = BehaviorPattern(
                    pattern_id=pid,
                    pattern_type="sequence",
                    description=f"After {a_id} is touched, {b_id} follows within {avg_gap:.0f}s",
                    objects_involved=[a_id, b_id],
                    observations=len(gaps),
                    confidence=min(1.0, len(gaps) / 6.0),
                    first_observed=now - avg_gap * len(gaps),
                    last_observed=now,
                    sequence_gap_s=avg_gap,
                )
            else:
                pat = self._patterns[pid]
                pat.observations = len(gaps)
                pat.last_observed = now
                pat.sequence_gap_s = avg_gap

            self._maybe_create_habit(pid)

    def _check_relational_patterns(self, current_objects: dict) -> None:
        """Check if certain objects are consistently near each other."""
        items = list(current_objects.items())
        now = time.time()

        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                oid_a, obj_a = items[i]
                oid_b, obj_b = items[j]

                pos_a = getattr(obj_a, 'last_seen_position', None)
                pos_b = getattr(obj_b, 'last_seen_position', None)
                if pos_a is None or pos_b is None:
                    continue

                dist = self._distance(pos_a, pos_b)
                if dist > self.PROXIMITY_THRESHOLD:
                    continue

                pid = _make_id("relational", *sorted([oid_a, oid_b]))

                if pid not in self._patterns:
                    self._patterns[pid] = BehaviorPattern(
                        pattern_id=pid,
                        pattern_type="relational",
                        description=f"{oid_a} and {oid_b} are kept near each other",
                        objects_involved=sorted([oid_a, oid_b]),
                        observations=1,
                        confidence=0.0,
                        first_observed=now,
                        last_observed=now,
                        proximity_cm=dist,
                    )
                else:
                    pat = self._patterns[pid]
                    pat.observations += 1
                    pat.last_observed = now
                    pat.proximity_cm = (pat.proximity_cm + dist) / 2  # running avg
                    pat.confidence = min(1.0, pat.observations / 8.0)

                self._maybe_create_habit(pid)

    def _maybe_create_habit(self, pattern_id: str) -> None:
        """Create a habit from a pattern if it's strong enough."""
        pattern = self._patterns.get(pattern_id)
        if pattern is None or pattern.observations < self.MIN_OBSERVATIONS:
            return

        hid = f"h_{pattern_id}"

        if hid in self._habits:
            # Strengthen existing habit
            habit = self._habits[hid]
            if habit.active:
                new_strength = min(1.0, habit.strength + self.STRENGTH_INCREMENT)
                habit.strength = new_strength
            return

        # Create new habit based on pattern type
        if pattern.pattern_type == "placement" and pattern.centroid:
            habit = Habit(
                habit_id=hid,
                trigger=f"{pattern.objects_involved[0]} appears on desk",
                action="nudge_to_position",
                action_data={
                    "object_id": pattern.objects_involved[0],
                    "target_position": list(pattern.centroid),
                },
                pattern_id=pattern_id,
                strength=self.STRENGTH_INCREMENT * pattern.observations,
            )
        elif pattern.pattern_type == "sequence" and len(pattern.objects_involved) >= 2:
            habit = Habit(
                habit_id=hid,
                trigger=f"{pattern.objects_involved[0]} is interacted with",
                action="orient_toward",
                action_data={
                    "object_id": pattern.objects_involved[1],
                },
                pattern_id=pattern_id,
                strength=self.STRENGTH_INCREMENT * pattern.observations,
            )
        elif pattern.pattern_type == "relational" and len(pattern.objects_involved) >= 2:
            habit = Habit(
                habit_id=hid,
                trigger=f"{pattern.objects_involved[0]} drifts from {pattern.objects_involved[1]}",
                action="nudge_together",
                action_data={
                    "object_a": pattern.objects_involved[0],
                    "object_b": pattern.objects_involved[1],
                },
                pattern_id=pattern_id,
                strength=self.STRENGTH_INCREMENT * pattern.observations,
            )
        else:
            return

        self._habits[hid] = habit
        logger.info(f"New habit: {habit.trigger} → {habit.action} (strength={habit.strength:.2f})")

    def _is_triggered(self, habit: Habit, current_objects: dict) -> bool:
        """Check if a habit's trigger conditions are met."""
        if habit.action == "nudge_to_position":
            oid = habit.action_data.get("object_id")
            target = habit.action_data.get("target_position")
            if not oid or not target:
                return False

            obj = current_objects.get(oid)
            if obj is None:
                return False

            pos = getattr(obj, 'last_seen_position', None)
            if pos is None:
                return False

            # Trigger if object is on desk but NOT near target
            dist = self._distance(pos, target)
            return dist > self.PLACEMENT_STD_THRESHOLD

        elif habit.action == "orient_toward":
            # Trigger: first object was recently interacted with
            oid = habit.action_data.get("object_id")
            return oid in current_objects

        elif habit.action == "nudge_together":
            a_id = habit.action_data.get("object_a")
            b_id = habit.action_data.get("object_b")
            obj_a = current_objects.get(a_id)
            obj_b = current_objects.get(b_id)
            if obj_a is None or obj_b is None:
                return False

            pos_a = getattr(obj_a, 'last_seen_position', None)
            pos_b = getattr(obj_b, 'last_seen_position', None)
            if pos_a is None or pos_b is None:
                return False

            # Trigger if they've drifted apart
            return self._distance(pos_a, pos_b) > self.PROXIMITY_THRESHOLD * 1.5

        return False

    @staticmethod
    def _distance(a, b) -> float:
        """Euclidean distance between two position tuples."""
        n = min(len(a), len(b))
        return sum((a[i] - b[i]) ** 2 for i in range(n)) ** 0.5

    # --- Persistence ---

    def save(self, path: Path) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "last_save": time.time(),
                "patterns": {pid: p.to_dict() for pid, p in self._patterns.items()},
                "habits": {hid: h.to_dict() for hid, h in self._habits.items()},
            }
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save habits: {e}")
            return False

    def load(self, path: Path) -> bool:
        if not path.exists():
            return False

        try:
            with open(path) as f:
                data = json.load(f)

            for pid, pdata in data.get("patterns", {}).items():
                self._patterns[pid] = BehaviorPattern.from_dict(pdata)

            for hid, hdata in data.get("habits", {}).items():
                self._habits[hid] = Habit.from_dict(hdata)

            logger.info(
                f"Loaded habits: {len(self._patterns)} patterns, "
                f"{len(self._habits)} habits"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to load habits: {e}")
            return False

    def clear(self) -> None:
        self._patterns.clear()
        self._habits.clear()
        self._events.clear()
        self._placement_history.clear()
