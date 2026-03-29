"""Object memory — ALICE remembers what's on the desk across sessions.

Persists the personality engine's object preferences to disk so ALICE can:
- Remember where things belong between power cycles
- Notice when something has moved since last session
- Build stronger preferences over time

Storage format: JSON file with object entries, timestamps, and spatial data.
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("ObjectMemory")

DEFAULT_MEMORY_PATH = Path(__file__).parent.parent / "data" / "object_memory.json"


@dataclass
class ObjectRecord:
    """Persistent record of a single object ALICE has seen."""
    object_id: str                      # e.g. "cup_1", "laptop_0"
    label: str                          # YOLO class name
    preferred_position: Optional[Tuple[float, float, float]] = None  # (x, y, z) in cm
    last_seen_position: Optional[Tuple[float, float, float]] = None
    confidence: float = 0.0
    times_placed: int = 0
    times_overridden: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0
    session_count: int = 0              # how many sessions ALICE has seen this object

    def to_dict(self) -> dict:
        d = {
            "object_id": self.object_id,
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "times_placed": self.times_placed,
            "times_overridden": self.times_overridden,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "session_count": self.session_count,
        }
        if self.preferred_position is not None:
            d["preferred_position"] = [round(v, 1) for v in self.preferred_position]
        if self.last_seen_position is not None:
            d["last_seen_position"] = [round(v, 1) for v in self.last_seen_position]
        return d

    @staticmethod
    def from_dict(data: dict) -> "ObjectRecord":
        pp = data.get("preferred_position")
        lsp = data.get("last_seen_position")
        return ObjectRecord(
            object_id=data["object_id"],
            label=data["label"],
            preferred_position=tuple(pp) if pp else None,
            last_seen_position=tuple(lsp) if lsp else None,
            confidence=data.get("confidence", 0.0),
            times_placed=data.get("times_placed", 0),
            times_overridden=data.get("times_overridden", 0),
            first_seen=data.get("first_seen", 0.0),
            last_seen=data.get("last_seen", 0.0),
            session_count=data.get("session_count", 0),
        )

    @property
    def has_moved(self) -> bool:
        """True if last_seen_position differs from preferred_position."""
        if self.preferred_position is None or self.last_seen_position is None:
            return False
        dist = sum(
            (a - b) ** 2
            for a, b in zip(self.preferred_position, self.last_seen_position)
        ) ** 0.5
        return dist > 5.0  # cm threshold


@dataclass
class DeskSnapshot:
    """A complete snapshot of what ALICE knows about the desk."""
    objects: Dict[str, ObjectRecord] = field(default_factory=dict)
    session_start: float = 0.0
    last_save: float = 0.0

    def to_dict(self) -> dict:
        return {
            "session_start": self.session_start,
            "last_save": self.last_save,
            "objects": {
                oid: obj.to_dict() for oid, obj in self.objects.items()
            },
        }

    @staticmethod
    def from_dict(data: dict) -> "DeskSnapshot":
        snap = DeskSnapshot(
            session_start=data.get("session_start", 0.0),
            last_save=data.get("last_save", 0.0),
        )
        for oid, obj_data in data.get("objects", {}).items():
            snap.objects[oid] = ObjectRecord.from_dict(obj_data)
        return snap


class ObjectMemory:
    """Persistent object memory for ALICE.

    Tracks objects across sessions. Saves to JSON on disk.

    Usage:
        memory = ObjectMemory()
        memory.load()
        memory.observe("cup_0", "cup", position=(15.0, 20.0, 0.5))
        memory.save()
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = path or DEFAULT_MEMORY_PATH
        self._snapshot = DeskSnapshot()
        self._dirty = False

    @property
    def path(self) -> Path:
        return self._path

    @property
    def objects(self) -> Dict[str, ObjectRecord]:
        return self._snapshot.objects

    @property
    def object_count(self) -> int:
        return len(self._snapshot.objects)

    def load(self) -> bool:
        """Load memory from disk. Returns True if a file was loaded."""
        if not self._path.exists():
            logger.info(f"No memory file at {self._path} — starting fresh")
            self._snapshot = DeskSnapshot(session_start=time.time())
            return False

        try:
            with open(self._path) as f:
                data = json.load(f)
            self._snapshot = DeskSnapshot.from_dict(data)
            self._snapshot.session_start = time.time()
            # Increment session count for all objects
            for obj in self._snapshot.objects.values():
                obj.session_count += 1
            logger.info(f"Loaded memory: {len(self._snapshot.objects)} objects from {self._path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load memory: {e}")
            self._snapshot = DeskSnapshot(session_start=time.time())
            return False

    def save(self) -> bool:
        """Save memory to disk. Returns True on success."""
        self._snapshot.last_save = time.time()
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(self._snapshot.to_dict(), f, indent=2)
            self._dirty = False
            logger.debug(f"Saved memory: {len(self._snapshot.objects)} objects")
            return True
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
            return False

    def observe(self, object_id: str, label: str,
                position: Optional[Tuple[float, float, float]] = None) -> ObjectRecord:
        """Record that ALICE sees an object. Creates or updates its record."""
        now = time.time()
        if object_id in self._snapshot.objects:
            obj = self._snapshot.objects[object_id]
            obj.last_seen = now
            if position:
                obj.last_seen_position = position
        else:
            obj = ObjectRecord(
                object_id=object_id,
                label=label,
                last_seen_position=position,
                first_seen=now,
                last_seen=now,
                session_count=1,
            )
            self._snapshot.objects[object_id] = obj
            logger.debug(f"New object: {object_id} ({label})")

        self._dirty = True
        return obj

    def record_placement(self, object_id: str,
                         position: Tuple[float, float, float]) -> None:
        """ALICE placed an object — strengthen preference."""
        if object_id not in self._snapshot.objects:
            return
        obj = self._snapshot.objects[object_id]
        obj.preferred_position = position
        obj.last_seen_position = position
        obj.times_placed += 1
        obj.confidence = min(1.0, obj.confidence + 0.15)
        obj.last_seen = time.time()
        self._dirty = True

    def record_override(self, object_id: str,
                        new_position: Tuple[float, float, float]) -> None:
        """User moved an object after ALICE placed it."""
        if object_id not in self._snapshot.objects:
            return
        obj = self._snapshot.objects[object_id]
        obj.times_overridden += 1
        obj.last_seen_position = new_position
        obj.confidence = max(0.0, obj.confidence - 0.1)
        obj.last_seen = time.time()
        self._dirty = True

    def get_moved_objects(self) -> List[ObjectRecord]:
        """Objects whose current position differs from their preferred position."""
        return [obj for obj in self._snapshot.objects.values() if obj.has_moved]

    def get_objects_by_label(self, label: str) -> List[ObjectRecord]:
        """Find all objects with a given label."""
        return [obj for obj in self._snapshot.objects.values() if obj.label == label]

    def get_object(self, object_id: str) -> Optional[ObjectRecord]:
        return self._snapshot.objects.get(object_id)

    def forget(self, object_id: str) -> bool:
        """Remove an object from memory."""
        if object_id in self._snapshot.objects:
            del self._snapshot.objects[object_id]
            self._dirty = True
            return True
        return False

    def clear(self) -> None:
        """Reset all memory."""
        self._snapshot = DeskSnapshot(session_start=time.time())
        self._dirty = True

    @property
    def needs_save(self) -> bool:
        return self._dirty

    def get_snapshot_dict(self) -> dict:
        """JSON-serializable snapshot for dashboard/WebSocket."""
        return self._snapshot.to_dict()
