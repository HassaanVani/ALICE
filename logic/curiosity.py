"""Curiosity engine — ALICE notices new things and wants to examine them.

Tracks novelty on the desk: new objects spike curiosity, moved objects re-spark
interest, familiar things fade to boring. Curiosity decays over time but
never-examined objects nag.

This system is purely data — it never moves the arm. The proactive engagement
system reads curiosity levels and orchestrates the actual examination behavior.

Cross-session persistence: saves to JSON so ALICE remembers what she's already
studied. On reload, curiosity halves (last session is less interesting) but
unexamined objects get a boost (she never got to them).
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("Curiosity")


@dataclass
class CuriosityRecord:
    """Per-object curiosity state."""
    object_id: str
    label: str
    curiosity_level: float = 0.0     # 0.0 = boring, 1.0 = must investigate
    times_examined: int = 0
    last_examined: float = 0.0
    last_position: Optional[Tuple[float, float, float]] = None
    first_seen_session: int = 1
    position_change_count: int = 0

    def to_dict(self) -> dict:
        d = {
            "object_id": self.object_id,
            "label": self.label,
            "curiosity_level": round(self.curiosity_level, 3),
            "times_examined": self.times_examined,
            "last_examined": self.last_examined,
            "first_seen_session": self.first_seen_session,
            "position_change_count": self.position_change_count,
        }
        if self.last_position is not None:
            d["last_position"] = [round(v, 1) for v in self.last_position]
        return d

    @staticmethod
    def from_dict(data: dict) -> "CuriosityRecord":
        lp = data.get("last_position")
        return CuriosityRecord(
            object_id=data["object_id"],
            label=data["label"],
            curiosity_level=data.get("curiosity_level", 0.0),
            times_examined=data.get("times_examined", 0),
            last_examined=data.get("last_examined", 0.0),
            last_position=tuple(lp) if lp else None,
            first_seen_session=data.get("first_seen_session", 1),
            position_change_count=data.get("position_change_count", 0),
        )


class CuriosityEngine:
    """Detects novelty and manages per-object curiosity levels.

    Usage:
        engine = CuriosityEngine()
        engine.update(detections, memory_objects)
        most_curious = engine.get_most_curious()
        if most_curious:
            # ... examine it ...
            engine.record_examination(most_curious.object_id)
    """

    NOVELTY_SPIKE = 0.9          # curiosity for brand-new objects
    MOVEMENT_SPIKE = 0.5         # curiosity bump when known object moves
    DECAY_RATE = 0.005           # per tick decay
    EXAMINE_REDUCTION = 0.4      # curiosity drop after examination
    EXAMINE_COOLDOWN = 30.0      # seconds before re-examining same object
    MIN_THRESHOLD = 0.25         # minimum curiosity to trigger examination
    POSITION_CHANGE_DIST = 5.0   # cm threshold to count as "moved"

    def __init__(self, session_number: int = 1):
        self._records: Dict[str, CuriosityRecord] = {}
        self._session = session_number

    @property
    def records(self) -> Dict[str, CuriosityRecord]:
        return dict(self._records)

    @property
    def total_curiosity(self) -> float:
        """Sum of all curiosity levels. High = ALICE wants to explore."""
        return sum(r.curiosity_level for r in self._records.values())

    def update(self, detections: list, memory_objects: dict) -> None:
        """Compare current detections against known memory.

        Args:
            detections: list of YOLO detection objects with .label, .object_id,
                       and optionally .position (3D) or .center_x/.center_y.
            memory_objects: dict of object_id → ObjectRecord from ObjectMemory.
        """
        seen_ids = set()

        for det in detections:
            obj_id = getattr(det, 'object_id', None) or getattr(det, 'label', 'unknown')
            label = getattr(det, 'label', 'unknown')
            seen_ids.add(obj_id)

            # Get position if available
            pos = None
            if hasattr(det, 'position') and det.position is not None:
                pos = tuple(det.position)
            elif hasattr(det, 'last_seen_position') and det.last_seen_position is not None:
                pos = tuple(det.last_seen_position)

            if obj_id not in self._records:
                # New object — high curiosity
                self._records[obj_id] = CuriosityRecord(
                    object_id=obj_id,
                    label=label,
                    curiosity_level=self.NOVELTY_SPIKE,
                    last_position=pos,
                    first_seen_session=self._session,
                )
                logger.debug(f"New object: {obj_id} ({label}) — curiosity={self.NOVELTY_SPIKE}")
            else:
                record = self._records[obj_id]

                # Check if it moved
                if pos is not None and record.last_position is not None:
                    dist = sum(
                        (a - b) ** 2
                        for a, b in zip(pos, record.last_position)
                    ) ** 0.5

                    if dist > self.POSITION_CHANGE_DIST:
                        record.position_change_count += 1
                        record.curiosity_level = min(
                            1.0, record.curiosity_level + self.MOVEMENT_SPIKE
                        )
                        logger.debug(
                            f"Object moved: {obj_id} — curiosity={record.curiosity_level:.2f}"
                        )

                if pos is not None:
                    record.last_position = pos

    def get_most_curious(self) -> Optional[CuriosityRecord]:
        """Return the object ALICE is most curious about, if above threshold."""
        now = time.time()
        candidates = [
            r for r in self._records.values()
            if (r.curiosity_level >= self.MIN_THRESHOLD and
                now - r.last_examined > self.EXAMINE_COOLDOWN)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda r: r.curiosity_level)

    def record_examination(self, object_id: str) -> None:
        """Called after ALICE examines an object."""
        if object_id in self._records:
            record = self._records[object_id]
            record.times_examined += 1
            record.last_examined = time.time()
            record.curiosity_level = max(
                0.0, record.curiosity_level - self.EXAMINE_REDUCTION
            )
            logger.debug(
                f"Examined {object_id} — curiosity now {record.curiosity_level:.2f}"
            )

    def tick(self) -> None:
        """Decay all curiosity levels. Call each loop iteration."""
        for record in self._records.values():
            if record.curiosity_level > 0:
                record.curiosity_level = max(
                    0.0, record.curiosity_level - self.DECAY_RATE
                )

    def save(self, path: Path) -> bool:
        """Persist curiosity state to JSON."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "session_count": self._session,
                "last_save": time.time(),
                "records": {
                    oid: rec.to_dict()
                    for oid, rec in self._records.items()
                },
            }
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save curiosity state: {e}")
            return False

    def load(self, path: Path) -> bool:
        """Load curiosity state from previous session.

        On load: curiosity halves (last session stuff is less fresh).
        Objects that were never examined get a small boost (unfinished business).
        """
        if not path.exists():
            return False

        try:
            with open(path) as f:
                data = json.load(f)

            prev_session = data.get("session_count", 0)
            self._session = prev_session + 1

            for oid, rec_data in data.get("records", {}).items():
                record = CuriosityRecord.from_dict(rec_data)

                # Half curiosity from last session
                record.curiosity_level *= 0.5

                # Boost never-examined objects
                if record.times_examined == 0:
                    record.curiosity_level = min(
                        1.0, record.curiosity_level + 0.2
                    )

                self._records[oid] = record

            logger.info(
                f"Loaded curiosity: {len(self._records)} objects from session {prev_session}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to load curiosity state: {e}")
            return False

    def clear(self) -> None:
        """Reset all curiosity."""
        self._records.clear()
