"""Tests for the proactive engagement orchestrator."""

import asyncio
import time
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from logic.proactive import ProactiveEngagement, EngagementAction, EngagementDecision
from logic.curiosity import CuriosityEngine
from logic.habits import HabitEngine
from logic.gaze_tracker import GazeTracker
from logic.body_language import BodyLanguage
from logic.personality import PersonalityEngine
from logic.object_memory import ObjectMemory
from audio.sound_effects import SoundEffects


@pytest.fixture
def proactive_setup():
    curiosity = CuriosityEngine()
    habits = HabitEngine()
    gaze = GazeTracker(alpha=1.0)
    body_lang = BodyLanguage()
    personality = PersonalityEngine()
    obj_memory = ObjectMemory()

    from hardware.arm_controller import ArmController
    arm = ArmController(simulate=True)
    arm.connect()
    sfx = SoundEffects(arm=arm, enabled=True)

    proactive = ProactiveEngagement(
        curiosity=curiosity,
        habits=habits,
        gaze=gaze,
        body_language=body_lang,
        sound_effects=sfx,
        personality=personality,
        object_memory=obj_memory,
    )
    return SimpleNamespace(
        proactive=proactive,
        curiosity=curiosity,
        habits=habits,
        gaze=gaze,
        body_lang=body_lang,
        sfx=sfx,
        personality=personality,
        obj_memory=obj_memory,
        arm=arm,
    )


class TestDecision:
    def test_none_when_nothing_happening(self, proactive_setup):
        s = proactive_setup
        decision = s.proactive.decide(None)
        assert decision.action == EngagementAction.NONE

    def test_none_during_cooldown(self, proactive_setup):
        s = proactive_setup
        s.proactive._last_action_time = time.time()  # just acted
        decision = s.proactive.decide(None)
        assert decision.action == EngagementAction.NONE

    def test_none_while_executing(self, proactive_setup):
        s = proactive_setup
        s.proactive._executing = True
        decision = s.proactive.decide(None)
        assert decision.action == EngagementAction.NONE

    def test_examine_when_curious(self, proactive_setup):
        s = proactive_setup
        s.proactive._last_action_time = 0  # no cooldown

        # Add a curious object
        from logic.curiosity import CuriosityRecord
        s.curiosity._records["cup_0"] = CuriosityRecord(
            object_id="cup_0", label="cup",
            curiosity_level=0.8, last_examined=0,
            last_position=(10, 20, 0),
        )

        decision = s.proactive.decide(None)
        assert decision.action == EngagementAction.EXAMINE_OBJECT
        assert decision.target_object == "cup_0"

    def test_look_at_user_when_present(self, proactive_setup):
        s = proactive_setup
        s.proactive._last_action_time = 0
        s.proactive._last_look_time = 0

        presence = SimpleNamespace(detected=True, face_count=1, closest_distance=60)
        decision = s.proactive.decide(presence)
        assert decision.action == EngagementAction.LOOK_AT_USER

    def test_examine_rate_limit(self, proactive_setup):
        s = proactive_setup
        s.proactive._last_action_time = 0
        s.proactive._examine_count_minute = 10  # way over limit
        s.proactive._examine_minute_start = time.time()

        from logic.curiosity import CuriosityRecord
        s.curiosity._records["cup_0"] = CuriosityRecord(
            object_id="cup_0", label="cup",
            curiosity_level=0.8, last_examined=0,
        )

        decision = s.proactive.decide(None)
        # Should NOT examine because rate limited
        assert decision.action != EngagementAction.EXAMINE_OBJECT


class TestExecution:
    @pytest.mark.asyncio
    async def test_examine_object(self, proactive_setup):
        s = proactive_setup
        from hardware.dynamics import MovementDynamics
        dynamics = MovementDynamics(s.arm)

        from logic.curiosity import CuriosityRecord
        s.curiosity._records["cup_0"] = CuriosityRecord(
            object_id="cup_0", label="cup",
            curiosity_level=0.8, last_examined=0,
            last_position=(100, 200, 0),
        )

        decision = EngagementDecision(
            action=EngagementAction.EXAMINE_OBJECT,
            target_object="cup_0",
        )
        result = await s.proactive.execute(decision, dynamics, s.arm)
        assert result is True
        assert s.curiosity.records["cup_0"].times_examined == 1

    @pytest.mark.asyncio
    async def test_look_at_user(self, proactive_setup):
        s = proactive_setup
        from hardware.dynamics import MovementDynamics
        dynamics = MovementDynamics(s.arm)

        decision = EngagementDecision(action=EngagementAction.LOOK_AT_USER)
        result = await s.proactive.execute(decision, dynamics, s.arm)
        assert result is True

    @pytest.mark.asyncio
    async def test_none_returns_false(self, proactive_setup):
        s = proactive_setup
        from hardware.dynamics import MovementDynamics
        dynamics = MovementDynamics(s.arm)

        decision = EngagementDecision(action=EngagementAction.NONE)
        result = await s.proactive.execute(decision, dynamics, s.arm)
        assert result is False

    @pytest.mark.asyncio
    async def test_executing_flag(self, proactive_setup):
        s = proactive_setup
        from hardware.dynamics import MovementDynamics
        dynamics = MovementDynamics(s.arm)

        decision = EngagementDecision(action=EngagementAction.LOOK_AT_USER)
        # Execute — should set and clear _executing
        await s.proactive.execute(decision, dynamics, s.arm)
        assert s.proactive.is_executing is False
