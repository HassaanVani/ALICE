"""Tests for vision/presence.py — presence detection."""

import time

import numpy as np
import pytest

from vision.presence import PresenceDetector, PresenceInfo


class TestPresenceInfo:
    def test_defaults(self):
        info = PresenceInfo()
        assert info.detected is False
        assert info.face_count == 0
        assert info.closest_distance == float("inf")
        assert info.looking_at_desk is False

    def test_to_dict(self):
        info = PresenceInfo(
            detected=True, face_count=2, closest_distance=45.3,
            looking_at_desk=True, timestamp=1234.0,
        )
        d = info.to_dict()
        assert d["detected"] is True
        assert d["face_count"] == 2
        assert d["closest_distance"] == 45.3
        assert d["looking_at_desk"] is True
        assert d["timestamp"] == 1234.0


class TestPresenceDetectorSimulation:
    def test_simulate_mode(self):
        det = PresenceDetector()
        det._simulate = True
        assert det.simulate is True

    def test_simulate_detect_returns_presence(self):
        det = PresenceDetector()
        det._simulate = True
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        info = det.detect(frame)
        assert info.detected is True
        assert info.face_count == 1
        assert info.closest_distance > 0
        assert info.looking_at_desk is True
        assert info.timestamp > 0

    def test_last_info_updated(self):
        det = PresenceDetector()
        det._simulate = True
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        result = det.detect(frame)
        assert result.detected is True
        assert det.last_info.detected is True

    def test_stop_is_safe(self):
        det = PresenceDetector()
        det._simulate = True
        det.stop()  # should not raise


class TestPresencePersonalityIntegration:
    def test_presence_feeds_personality(self):
        """PresenceDetector output drives PersonalityEngine.set_presence()."""
        from logic.personality import PersonalityEngine, EmotionalState

        engine = PersonalityEngine()
        det = PresenceDetector()
        det._simulate = True

        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        info = det.detect(frame)

        # Wire presence to personality
        engine.set_presence(info.detected)
        assert engine.emotional_state == EmotionalState.CURIOUS

    def test_no_presence_stays_content(self):
        from logic.personality import PersonalityEngine, EmotionalState

        engine = PersonalityEngine()
        engine.set_presence(False)
        assert engine.emotional_state != EmotionalState.CURIOUS
