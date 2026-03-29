"""Tests for logic/desk_presets.py — desk layout presets."""

import pytest

from logic.desk_presets import (
    DeskPreset, ObjectSlot, PRESETS,
    get_preset, list_presets, register_preset,
    PRESET_STUDYING, PRESET_DRAWING, PRESET_WORKING, PRESET_CLEAN,
)


class TestObjectSlot:
    def test_fields(self):
        slot = ObjectSlot("cup", (10, 20), zone="right", priority=2)
        assert slot.label == "cup"
        assert slot.position == (10, 20)
        assert slot.zone == "right"
        assert slot.priority == 2


class TestDeskPreset:
    def test_get_slot_for(self):
        preset = PRESET_STUDYING
        slot = preset.get_slot_for("book")
        assert slot is not None
        assert slot.label == "book"
        assert slot.zone == "center"

    def test_get_slot_for_missing(self):
        preset = PRESET_STUDYING
        assert preset.get_slot_for("banana") is None

    def test_get_priority_objects(self):
        preset = PRESET_STUDYING
        p1 = preset.get_priority_objects(1)
        assert all(s.priority <= 1 for s in p1)
        assert len(p1) >= 1

    def test_to_dict(self):
        d = PRESET_STUDYING.to_dict()
        assert d["name"] == "studying"
        assert d["display_name"] == "Study Mode"
        assert len(d["slots"]) > 0
        assert "position" in d["slots"][0]

    def test_from_dict_roundtrip(self):
        d = PRESET_WORKING.to_dict()
        preset = DeskPreset.from_dict(d)
        assert preset.name == "working"
        assert len(preset.slots) == len(PRESET_WORKING.slots)
        assert preset.slots[0].label == PRESET_WORKING.slots[0].label


class TestPresetRegistry:
    def test_all_presets_exist(self):
        names = list_presets()
        assert "studying" in names
        assert "drawing" in names
        assert "working" in names
        assert "clean" in names

    def test_get_preset(self):
        p = get_preset("studying")
        assert p is not None
        assert p.name == "studying"

    def test_get_preset_missing(self):
        assert get_preset("nonexistent") is None

    def test_register_custom_preset(self):
        custom = DeskPreset(
            name="gaming",
            display_name="Gaming Mode",
            description="Keyboard and mouse centered.",
            slots=[
                ObjectSlot("keyboard", (0, -5), zone="center", priority=1),
                ObjectSlot("mouse", (20, -5), zone="right", priority=1),
            ],
        )
        register_preset(custom)
        assert get_preset("gaming") is not None
        assert get_preset("gaming").display_name == "Gaming Mode"
        # Cleanup
        del PRESETS["gaming"]


class TestPresetContent:
    def test_studying_has_book_center(self):
        slot = PRESET_STUDYING.get_slot_for("book")
        assert slot.zone == "center"
        assert slot.priority == 1

    def test_studying_phone_out_of_way(self):
        slot = PRESET_STUDYING.get_slot_for("cell phone")
        assert slot is not None
        assert slot.zone == "right"

    def test_working_laptop_center(self):
        slot = PRESET_WORKING.get_slot_for("laptop")
        assert slot.zone == "center"
        assert slot.priority == 1

    def test_clean_has_clear_zones(self):
        assert len(PRESET_CLEAN.clear_zones) > 0
        assert "center" in PRESET_CLEAN.clear_zones

    def test_all_presets_have_description(self):
        for name, preset in PRESETS.items():
            assert preset.description, f"Preset {name} missing description"
            assert preset.display_name, f"Preset {name} missing display_name"
