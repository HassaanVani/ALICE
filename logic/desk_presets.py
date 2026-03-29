"""Desk layout presets — named configurations for how a desk should be organized.

Each preset defines where categories of objects belong for a specific activity
(studying, drawing, working, etc.). The desk organization FSM and audience
voting system use these to drive ALICE's tidying behavior.

Positions are relative to the desk center (0,0) in centimeters, with
x+ right, y+ away from user.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("DeskPresets")


@dataclass
class ObjectSlot:
    """A named slot in a desk layout where an object category belongs."""
    label: str                          # YOLO object label to match
    position: Tuple[float, float]       # (x, y) relative to desk center, cm
    zone: str = "center"                # semantic zone: center, left, right, back, front
    priority: int = 1                   # 1=must-place, 2=nice-to-have, 3=optional
    notes: str = ""                     # human-readable placement note


@dataclass
class DeskPreset:
    """A complete desk layout configuration for a specific activity."""
    name: str
    display_name: str
    description: str
    slots: List[ObjectSlot] = field(default_factory=list)
    clear_zones: List[str] = field(default_factory=list)  # zones that should be empty

    def get_slot_for(self, label: str) -> Optional[ObjectSlot]:
        """Find the slot for a given object label. Returns None if no slot."""
        for slot in self.slots:
            if slot.label == label:
                return slot
        return None

    def get_priority_objects(self, priority: int = 1) -> List[ObjectSlot]:
        """Get all slots at or above a priority level."""
        return [s for s in self.slots if s.priority <= priority]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "slots": [
                {
                    "label": s.label,
                    "position": list(s.position),
                    "zone": s.zone,
                    "priority": s.priority,
                    "notes": s.notes,
                }
                for s in self.slots
            ],
            "clear_zones": self.clear_zones,
        }

    @staticmethod
    def from_dict(data: dict) -> "DeskPreset":
        return DeskPreset(
            name=data["name"],
            display_name=data.get("display_name", data["name"]),
            description=data.get("description", ""),
            slots=[
                ObjectSlot(
                    label=s["label"],
                    position=tuple(s["position"]),
                    zone=s.get("zone", "center"),
                    priority=s.get("priority", 1),
                    notes=s.get("notes", ""),
                )
                for s in data.get("slots", [])
            ],
            clear_zones=data.get("clear_zones", []),
        )


# --- Built-in presets ---

PRESET_STUDYING = DeskPreset(
    name="studying",
    display_name="Study Mode",
    description="Notebooks center, pens accessible, phone face-down and pushed aside.",
    slots=[
        ObjectSlot("book", (0, 5), zone="center", priority=1, notes="notebooks center"),
        ObjectSlot("cell phone", (25, -10), zone="right", priority=1,
                   notes="face-down, out of the way"),
        ObjectSlot("cup", (-20, 10), zone="left", priority=2,
                   notes="drink within reach but away from notes"),
        ObjectSlot("laptop", (0, 15), zone="back", priority=2,
                   notes="pushed back, reference screen"),
        ObjectSlot("scissors", (30, 15), zone="right", priority=3),
    ],
    clear_zones=["center"],
)

PRESET_DRAWING = DeskPreset(
    name="drawing",
    display_name="Drawing Mode",
    description="Sketchbook center, tools fanned out, reference material propped up.",
    slots=[
        ObjectSlot("book", (0, 0), zone="center", priority=1, notes="sketchbook center"),
        ObjectSlot("scissors", (-15, -5), zone="left", priority=2, notes="tools left side"),
        ObjectSlot("cup", (25, -10), zone="right", priority=2,
                   notes="drink far from art"),
        ObjectSlot("cell phone", (-25, 10), zone="left", priority=3,
                   notes="reference photo"),
        ObjectSlot("laptop", (20, 15), zone="right", priority=3,
                   notes="reference if needed"),
    ],
    clear_zones=["center"],
)

PRESET_WORKING = DeskPreset(
    name="working",
    display_name="Work Mode",
    description="Laptop center, phone accessible, drink within reach.",
    slots=[
        ObjectSlot("laptop", (0, 5), zone="center", priority=1, notes="primary screen"),
        ObjectSlot("keyboard", (0, -10), zone="front", priority=1),
        ObjectSlot("mouse", (20, -8), zone="right", priority=1),
        ObjectSlot("cell phone", (-20, -5), zone="left", priority=2,
                   notes="accessible but not distracting"),
        ObjectSlot("cup", (25, 10), zone="right", priority=2, notes="within reach"),
        ObjectSlot("book", (-25, 10), zone="left", priority=3, notes="reference"),
    ],
    clear_zones=[],
)

PRESET_CLEAN = DeskPreset(
    name="clean",
    display_name="Clean Desk",
    description="Everything pushed to the edges. Maximum clear space.",
    slots=[
        ObjectSlot("laptop", (0, 20), zone="back", priority=1, notes="pushed back"),
        ObjectSlot("book", (-25, 15), zone="left", priority=2),
        ObjectSlot("cup", (25, 15), zone="right", priority=2),
        ObjectSlot("cell phone", (25, -10), zone="right", priority=2),
        ObjectSlot("scissors", (-25, -10), zone="left", priority=3),
        ObjectSlot("mouse", (25, 0), zone="right", priority=3),
    ],
    clear_zones=["center", "front"],
)

# Registry of all built-in presets
PRESETS: Dict[str, DeskPreset] = {
    "studying": PRESET_STUDYING,
    "drawing": PRESET_DRAWING,
    "working": PRESET_WORKING,
    "clean": PRESET_CLEAN,
}


def get_preset(name: str) -> Optional[DeskPreset]:
    """Get a preset by name. Returns None if not found."""
    return PRESETS.get(name)


def list_presets() -> List[str]:
    """Return all available preset names."""
    return list(PRESETS.keys())


def register_preset(preset: DeskPreset) -> None:
    """Add a custom preset to the registry."""
    PRESETS[preset.name] = preset
    logger.info(f"Registered desk preset: {preset.name}")
