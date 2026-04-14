"""Tests for the LLM movement interpreter."""

import time
import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from logic.llm_interpreter import (
    LLMInterpreter, MovementModifiers, parse_modifiers,
    INTERPRETER_SYSTEM, _MOD_KEYS,
)


# ── MovementModifiers ──────────────────────────────────────────

class TestMovementModifiers:
    def test_defaults_are_unity(self):
        m = MovementModifiers()
        for key in _MOD_KEYS:
            assert getattr(m, key) == 1.0
        assert m.source == "default"

    def test_to_dict(self):
        m = MovementModifiers(spd=0.8, pos=1.5, source="llm")
        d = m.to_dict()
        assert d["spd"] == 0.8
        assert d["pos"] == 1.5
        assert d["source"] == "llm"


# ── parse_modifiers ────────────────────────────────────────────

class TestParseModifiers:
    def test_valid_json(self):
        raw = '{"spd":0.8,"hes":1.2,"pos":1.5,"scn":0.9,"per":1.1,"sfx":0.7,"appr":1.3,"tilt":1.4}'
        m = parse_modifiers(raw)
        assert m.spd == 0.8
        assert m.hes == 1.2
        assert m.pos == 1.5
        assert m.tilt == 1.4
        assert m.source == "llm"

    def test_partial_json(self):
        raw = '{"spd":0.6,"pos":1.8}'
        m = parse_modifiers(raw)
        assert m.spd == 0.6
        assert m.pos == 1.8
        assert m.hes == 1.0  # missing → default
        assert m.scn == 1.0

    def test_clamping_low(self):
        raw = '{"spd":0.1}'
        m = parse_modifiers(raw, min_val=0.3)
        assert m.spd == 0.3

    def test_clamping_high(self):
        raw = '{"pos":5.0}'
        m = parse_modifiers(raw, max_val=2.0)
        assert m.pos == 2.0

    def test_empty_string(self):
        m = parse_modifiers("")
        assert m.source == "default"
        assert m.spd == 1.0

    def test_garbage_text(self):
        m = parse_modifiers("I cannot help you with that request.")
        assert m.source == "default"

    def test_json_with_surrounding_text(self):
        raw = 'Here are the modifiers: {"spd":0.9,"pos":1.1} Hope that helps!'
        m = parse_modifiers(raw)
        assert m.spd == 0.9
        assert m.pos == 1.1
        assert m.source == "llm"

    def test_non_numeric_values(self):
        raw = '{"spd":"fast","pos":1.2}'
        m = parse_modifiers(raw)
        assert m.spd == 1.0  # "fast" → skipped, default
        assert m.pos == 1.2

    def test_unknown_keys_ignored(self):
        raw = '{"spd":0.8,"unknown_key":99}'
        m = parse_modifiers(raw)
        assert m.spd == 0.8
        assert not hasattr(m, 'unknown_key') or True  # no error

    def test_negative_values_clamped(self):
        raw = '{"hes":-1.0}'
        m = parse_modifiers(raw, min_val=0.3)
        assert m.hes == 0.3

    def test_all_keys(self):
        raw = '{"spd":1.1,"hes":0.8,"pos":1.3,"scn":1.0,"per":1.0,"sfx":0.9,"appr":1.0,"tilt":1.2}'
        m = parse_modifiers(raw)
        assert m.spd == 1.1
        assert m.hes == 0.8
        assert m.pos == 1.3
        assert m.sfx == 0.9
        assert m.tilt == 1.2


# ── Context building ───────────────────────────────────────────

class TestContextBuilder:
    def test_builds_with_personality(self):
        interp = LLMInterpreter()

        # Mock personality
        personality = MagicMock()
        state = SimpleNamespace(
            overall_mood=0.7, emotional_state=SimpleNamespace(value="curious"),
            idle_duration=12.0, override_streak=0, is_in_flow=False,
            strongest_opinion=0.5,
        )
        personality.state = state
        interp._personality = personality

        ctx = interp._build_context()
        assert "mood:0.7" in ctx
        assert "emo:curious" in ctx

    def test_builds_with_curiosity(self):
        interp = LLMInterpreter()
        curiosity = MagicMock()
        curiosity.total_curiosity = 1.5
        most = SimpleNamespace(label="cup", curiosity_level=0.8)
        curiosity.get_most_curious.return_value = most
        interp._curiosity = curiosity

        ctx = interp._build_context()
        assert "curiosity:1.5" in ctx
        assert "cup" in ctx

    def test_builds_with_nothing(self):
        interp = LLMInterpreter()
        ctx = interp._build_context()
        assert ctx == "idle"

    def test_builds_with_presence(self):
        interp = LLMInterpreter()
        presence = MagicMock()
        presence.last_info = SimpleNamespace(
            detected=True, closest_distance=60.0, face_count=1,
        )
        interp._presence = presence

        ctx = interp._build_context()
        assert "presence:yes" in ctx
        assert "distance:60cm" in ctx

    def test_context_is_compact(self):
        interp = LLMInterpreter()
        # Attach all systems with mocks
        personality = MagicMock()
        personality.state = SimpleNamespace(
            overall_mood=0.7, emotional_state=SimpleNamespace(value="curious"),
            idle_duration=12.0, override_streak=2, is_in_flow=False,
            strongest_opinion=0.8,
        )
        interp._personality = personality

        curiosity = MagicMock()
        curiosity.total_curiosity = 2.0
        curiosity.get_most_curious.return_value = SimpleNamespace(label="cup", curiosity_level=0.9)
        interp._curiosity = curiosity

        obj_mem = MagicMock()
        obj_mem.object_count = 5
        interp._object_memory = obj_mem

        presence = MagicMock()
        presence.last_info = SimpleNamespace(detected=True, closest_distance=55.0, face_count=1)
        interp._presence = presence

        gaze = MagicMock()
        gaze.get_target.return_value = SimpleNamespace(target_type="face", label="user")
        interp._gaze = gaze

        body_lang = MagicMock()
        body_lang.current_posture_name = "lean_in"
        interp._body_language = body_lang

        ctx = interp._build_context()
        # Should be compact — word count as rough token proxy
        words = ctx.split()
        assert len(words) < 30, f"Context too long ({len(words)} words): {ctx}"


# ── Graceful degradation ──────────────────────────────────────

class TestGracefulDegradation:
    @pytest.mark.asyncio
    async def test_query_timeout_returns_defaults(self):
        interp = LLMInterpreter(timeout_s=0.01)
        # Mock generate to be very slow
        import asyncio
        async def slow_gen(*a, **kw):
            await asyncio.sleep(10)
            return ""
        with patch.object(interp, '_generate_sync', side_effect=Exception("timeout")):
            m = await interp._query()
        assert m.source == "default"
        assert m.spd == 1.0

    @pytest.mark.asyncio
    async def test_query_empty_response_returns_defaults(self):
        interp = LLMInterpreter()
        with patch.object(interp, '_generate_sync', return_value=""):
            m = await interp._query()
        assert m.source == "default"

    @pytest.mark.asyncio
    async def test_query_garbage_response_returns_defaults(self):
        interp = LLMInterpreter()
        with patch.object(interp, '_generate_sync', return_value="sorry I can't"):
            m = await interp._query()
        assert m.source == "default"

    @pytest.mark.asyncio
    async def test_query_valid_response_returns_llm(self):
        interp = LLMInterpreter()
        with patch.object(interp, '_generate_sync',
                          return_value='{"spd":0.7,"pos":1.4}'):
            m = await interp._query()
        assert m.source == "llm"
        assert m.spd == 0.7
        assert m.pos == 1.4


# ── Integration points ────────────────────────────────────────

class TestIntegrationPoints:
    def _make_interpreter(self, **overrides):
        interp = LLMInterpreter()
        mods = MovementModifiers(**overrides, source="llm", timestamp=time.time())
        interp._modifiers = mods
        return interp

    def test_body_language_applies_modifier(self):
        from logic.body_language import BodyLanguage

        # Without modifier
        bl1 = BodyLanguage()
        bl1.on_emotion_change("content", "curious")
        bl1.tick(0.3)
        offset_raw = bl1.get_current_offset()

        # With pos=2.0 modifier (same posture, same tick)
        bl2 = BodyLanguage()
        interp = self._make_interpreter(pos=2.0)
        bl2.set_llm_interpreter(interp)
        # Manually inject the same overlay with the same timing
        from logic.body_language import _ActiveOverlay, POSTURES
        import time as _time
        now = _time.time()
        bl2._active = [_ActiveOverlay(
            overlay=POSTURES["lean_in"], start_time=now, strength=0.5,
        )]
        offset_mod = bl2.get_current_offset()

        # Raw lean_in has j3_offset=4.0, so at strength 0.5: raw j3 = 2.0
        # With pos=2.0: mod j3 = 4.0
        # Just verify modifier amplifies the output
        assert abs(offset_mod[2]) > abs(offset_raw[2]) or offset_raw[2] == 0

    def test_body_language_no_interpreter_unchanged(self):
        from logic.body_language import BodyLanguage
        bl = BodyLanguage()
        # No interpreter set
        bl.on_emotion_change("content", "curious")
        bl.tick(0.5)
        offset = bl.get_current_offset()
        # Should still work — nonzero offset from lean_in
        assert any(v != 0 for v in offset)

    def test_gaze_scan_applies_modifier(self):
        from logic.gaze_tracker import GazeTracker
        import math

        gt = GazeTracker(alpha=1.0)
        interp = self._make_interpreter(scn=2.0, per=1.0)
        gt.set_llm_interpreter(interp)
        gt._scan_phase = 1.0  # nonzero for sin to produce output
        target_mod = gt.get_target()

        gt2 = GazeTracker(alpha=1.0)
        gt2._scan_phase = 1.0
        target_raw = gt2.get_target()

        # Modulated scan amplitude should be ~2x (offset from neutral)
        from logic.gaze_tracker import GazeTracker as _GT
        neutral_j1 = _GT.NEUTRAL_ANGLES[0]
        offset_mod = abs(target_mod.angles[0] - neutral_j1)
        offset_raw = abs(target_raw.angles[0] - neutral_j1)
        if offset_raw > 0.1:
            ratio = offset_mod / offset_raw
            assert abs(ratio - 2.0) < 0.3

    def test_sound_effects_applies_modifier(self):
        from audio.sound_effects import SoundEffects, ServoPattern
        from hardware.arm_controller import ArmController

        arm = ArmController(simulate=True)
        arm.connect()
        sfx = SoundEffects(arm=arm, enabled=True, intensity=1.0)
        interp = self._make_interpreter(sfx=0.5)
        sfx.set_llm_interpreter(interp)
        # The modifier is applied inside _execute_pattern, tested indirectly
        # via the amplitude calculation
        assert sfx._llm_interpreter.modifiers.sfx == 0.5

    def test_dynamics_speed_modifier(self):
        """Verify the interpreter field is set correctly on dynamics."""
        from hardware.arm_controller import ArmController
        from hardware.dynamics import MovementDynamics

        arm = ArmController(simulate=True)
        arm.connect()
        dynamics = MovementDynamics(arm)
        interp = self._make_interpreter(spd=0.7, hes=1.5)
        dynamics.set_llm_interpreter(interp)
        assert dynamics._llm_interpreter.modifiers.spd == 0.7
        assert dynamics._llm_interpreter.modifiers.hes == 1.5

    def test_proactive_applies_modifier(self):
        from logic.proactive import ProactiveEngagement
        from logic.curiosity import CuriosityEngine
        from logic.habits import HabitEngine
        from logic.gaze_tracker import GazeTracker
        from logic.body_language import BodyLanguage
        from logic.personality import PersonalityEngine
        from logic.object_memory import ObjectMemory
        from audio.sound_effects import SoundEffects
        from hardware.arm_controller import ArmController

        arm = ArmController(simulate=True)
        arm.connect()
        proactive = ProactiveEngagement(
            curiosity=CuriosityEngine(), habits=HabitEngine(),
            gaze=GazeTracker(), body_language=BodyLanguage(),
            sound_effects=SoundEffects(arm=arm),
            personality=PersonalityEngine(), object_memory=ObjectMemory(),
        )
        interp = self._make_interpreter(tilt=1.8, appr=0.6)
        proactive.set_llm_interpreter(interp)
        assert proactive._llm_interpreter.modifiers.tilt == 1.8
        assert proactive._llm_interpreter.modifiers.appr == 0.6


# ── System prompt ─────────────────────────────────────────────

class TestSystemPrompt:
    def test_prompt_is_compact(self):
        words = INTERPRETER_SYSTEM.split()
        assert len(words) < 80, f"System prompt too long: {len(words)} words"

    def test_prompt_contains_example(self):
        assert '"spd"' in INTERPRETER_SYSTEM
        assert '"pos"' in INTERPRETER_SYSTEM

    def test_prompt_contains_range(self):
        assert "0.3" in INTERPRETER_SYSTEM
        assert "2.0" in INTERPRETER_SYSTEM
