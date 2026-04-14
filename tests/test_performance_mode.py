"""Tests for logic/tea_choreography.py, logic/fist_bump.py, logic/teaching.py."""

import asyncio
from unittest.mock import MagicMock, AsyncMock, PropertyMock
import time

import numpy as np
import pytest

from logic.teaching import TeachingSession


# --- Teaching Session ---

class TestTeachingSession:
    def test_start_and_stop(self):
        teacher = MagicMock()
        teacher._arm.position.as_tuple.return_value = (90, 90, 90, 90)
        teacher.stop.return_value = MagicMock(frames=[1, 2, 3])
        session = TeachingSession(teacher)
        session.start("cup")
        assert session.is_active
        assert session.current_label == "cup"
        summary = session.stop()
        assert summary["label"] == "cup"
        assert not session.is_active

    def test_record_position_with_memory(self, tmp_path):
        from logic.object_memory import ObjectMemory
        teacher = MagicMock()
        teacher._arm.position.as_tuple.return_value = (90, 80, 70, 90)
        memory = ObjectMemory(path=tmp_path / "teach_mem.json")

        session = TeachingSession(teacher, object_memory=memory)
        session.start("cup")
        result = session.record_position((90, 80, 70, 90))
        assert result is True
        assert session.positions_taught == 1
        assert memory.get_object("cup_0") is not None

    def test_record_position_inactive(self):
        teacher = MagicMock()
        session = TeachingSession(teacher)
        assert session.record_position() is False


# --- Tea Choreography ---

class TestTeaChoreography:
    def test_compute_safe_position(self):
        from logic.tea_choreography import TeaChoreography
        tea = TeaChoreography()
        # Cup at (100, 100), laptop at (200, 100) → safe pos should be left of laptop
        safe = tea._compute_safe_position((100, 100), (200, 100))
        assert safe[0] < 200  # cup should be away from laptop



# --- Mode registry (basic check) ---

class TestModeRegistry:
    def test_idle_in_switchable_modes(self):
        from modes import UI_SWITCHABLE_MODES
        assert "idle" in UI_SWITCHABLE_MODES
