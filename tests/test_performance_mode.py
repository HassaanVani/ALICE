"""Tests for modes/performance.py, logic/tea_choreography.py, logic/fist_bump.py, logic/teaching.py."""

import asyncio
from unittest.mock import MagicMock, AsyncMock, PropertyMock
import time

import numpy as np
import pytest

from logic.fist_bump import FistBumpInteraction, FIST_BUMP_ANGLES
from logic.teaching import TeachingSession


# --- Fist Bump ---

class TestFistBumpInteraction:
    @pytest.mark.asyncio
    async def test_trigger(self):
        bump = FistBumpInteraction(cooldown_s=0)
        arm = MagicMock()
        arm.move_to = MagicMock(return_value=True)
        result = await bump.trigger(arm)
        assert result is True
        arm.move_to.assert_called()

    @pytest.mark.asyncio
    async def test_cooldown_prevents_double_bump(self):
        bump = FistBumpInteraction(cooldown_s=60)
        arm = MagicMock()
        arm.move_to = MagicMock(return_value=True)
        await bump.trigger(arm)
        result = await bump.trigger(arm)
        assert result is False

    def test_should_trigger_close_presence(self):
        from vision.presence import PresenceInfo
        bump = FistBumpInteraction(cooldown_s=0)
        info = PresenceInfo(detected=True, closest_distance=30.0, looking_at_desk=True)
        assert bump.should_trigger(info) is True

    def test_should_trigger_far_presence(self):
        from vision.presence import PresenceInfo
        bump = FistBumpInteraction(cooldown_s=0)
        info = PresenceInfo(detected=True, closest_distance=100.0, looking_at_desk=True)
        assert bump.should_trigger(info) is False

    def test_should_trigger_no_presence(self):
        bump = FistBumpInteraction(cooldown_s=0)
        assert bump.should_trigger(None) is False


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


# --- Performance Mode (basic import test) ---

class TestPerformanceMode:
    def test_import(self):
        from modes.performance import PerformanceRunner
        assert PerformanceRunner is not None

    def test_mode_registered(self):
        from modes import DEMO_VISIBLE_MODES
        assert "performance" in DEMO_VISIBLE_MODES

    def test_mode_enum(self):
        from main import Mode
        assert Mode.PERFORMANCE.value == "performance"
