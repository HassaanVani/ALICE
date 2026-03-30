"""Tests for body language posture overlay system."""

import time
import pytest

from logic.body_language import BodyLanguage, PostureOverlay, POSTURES, _ActiveOverlay


class TestPostureDefinitions:
    def test_all_postures_exist(self):
        expected = ["droop", "perk_up", "bounce", "shrink_back", "lean_in",
                     "settle", "attentive", "recoil"]
        for name in expected:
            assert name in POSTURES

    def test_postures_have_nonzero_offsets(self):
        for name, p in POSTURES.items():
            total = abs(p.j1_offset) + abs(p.j2_offset) + abs(p.j3_offset) + abs(p.j4_offset)
            assert total > 0, f"Posture {name} has zero offset"

    def test_postures_have_valid_timing(self):
        for name, p in POSTURES.items():
            assert p.blend_in_s >= 0
            assert p.hold_s >= 0
            assert p.decay_s > 0


class TestBodyLanguage:
    def test_initial_offset_is_zero(self):
        bl = BodyLanguage()
        assert bl.get_current_offset() == (0.0, 0.0, 0.0, 0.0)

    def test_emotion_triggers_posture(self):
        bl = BodyLanguage()
        bl.on_emotion_change("content", "curious")
        assert bl.active_count == 1
        assert bl.current_posture_name == "lean_in"

    def test_voice_praise_triggers_perk(self):
        bl = BodyLanguage()
        bl.on_voice_sentiment("praise", 0.8)
        assert bl.active_count == 1
        assert bl.current_posture_name == "perk_up"

    def test_voice_scold_triggers_droop(self):
        bl = BodyLanguage()
        bl.on_voice_sentiment("scold", 0.7)
        assert bl.current_posture_name == "droop"

    def test_low_confidence_ignored(self):
        bl = BodyLanguage()
        bl.on_voice_sentiment("praise", 0.2)
        assert bl.active_count == 0

    def test_neutral_sentiment_no_posture(self):
        bl = BodyLanguage()
        bl.on_voice_sentiment("neutral", 1.0)
        assert bl.active_count == 0

    def test_event_triggers_posture(self):
        bl = BodyLanguage()
        bl.on_event("startle")
        assert bl.current_posture_name == "recoil"

    def test_event_bump_triggers_bounce(self):
        bl = BodyLanguage()
        bl.on_event("bump_reciprocated")
        assert bl.current_posture_name == "bounce"

    def test_unknown_event_ignored(self):
        bl = BodyLanguage()
        bl.on_event("nonexistent_event")
        assert bl.active_count == 0

    def test_tick_blends_in(self):
        bl = BodyLanguage()
        bl.on_emotion_change("content", "curious")
        # Immediately after trigger, strength should start blending
        bl.tick(0.1)
        offset = bl.get_current_offset()
        # lean_in has j3_offset=4.0 — should be partially there
        assert offset[2] > 0  # j3 should be positive

    def test_tick_decays(self):
        bl = BodyLanguage()
        bl.on_emotion_change("content", "curious")
        # Simulate time passing beyond blend_in + hold + decay
        overlay = bl._active[0]
        overlay.start_time = time.time() - 20  # way in the past
        bl.tick(0.1)
        assert bl.active_count == 0  # should have decayed away

    def test_offset_clamp(self):
        bl = BodyLanguage()
        # Stack multiple postures to test clamping
        bl.on_emotion_change("content", "curious")
        bl.on_voice_sentiment("praise", 1.0)
        bl.on_event("new_person")
        bl.tick(0.1)
        offset = bl.get_current_offset()
        for v in offset:
            assert -10.0 <= v <= 10.0

    def test_same_posture_not_stacked(self):
        bl = BodyLanguage()
        bl.on_emotion_change("content", "curious")  # lean_in
        bl.on_emotion_change("content", "curious")  # lean_in again
        assert bl.active_count == 1

    def test_max_active_limit(self):
        bl = BodyLanguage()
        bl.on_event("startle")
        bl.on_event("new_person")
        bl.on_event("task_complete")
        bl.on_event("bump_reciprocated")  # should evict oldest
        assert bl.active_count <= bl.MAX_ACTIVE

    def test_disabled_no_postures(self):
        bl = BodyLanguage()
        bl.set_enabled(False)
        bl.on_emotion_change("content", "curious")
        assert bl.active_count == 0
        assert bl.get_current_offset() == (0.0, 0.0, 0.0, 0.0)

    def test_disable_clears_active(self):
        bl = BodyLanguage()
        bl.on_emotion_change("content", "curious")
        assert bl.active_count == 1
        bl.set_enabled(False)
        assert bl.active_count == 0
