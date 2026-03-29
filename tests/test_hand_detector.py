"""Tests for vision/hand_detector.py — hand gesture detection."""

import time

import numpy as np
import pytest

from vision.hand_detector import (
    HandGestureDetector, HandDetection, HandGesture,
    FistBumpCandidate,
)


class TestHandGesture:
    def test_enum_values(self):
        assert HandGesture.FIST.value == "fist"
        assert HandGesture.OPEN.value == "open"
        assert HandGesture.POINTING.value == "pointing"
        assert HandGesture.THUMBS_UP.value == "thumbs_up"
        assert HandGesture.PEACE.value == "peace"
        assert HandGesture.UNKNOWN.value == "unknown"


class TestHandDetection:
    def test_to_dict(self):
        det = HandDetection(
            gesture=HandGesture.FIST, confidence=0.92,
            handedness="Right", center_x=0.5, center_y=0.6,
            pixel_x=320, pixel_y=288,
            hand_size=0.15, fingers_extended=0,
            is_stable=True,
        )
        d = det.to_dict()
        assert d["gesture"] == "fist"
        assert d["confidence"] == 0.92
        assert d["handedness"] == "Right"
        assert d["center"] == (320, 288)
        assert d["fingers_extended"] == 0
        assert d["is_stable"] is True

    def test_defaults(self):
        det = HandDetection(
            gesture=HandGesture.UNKNOWN, confidence=0.0,
            handedness="Left", center_x=0.0, center_y=0.0,
        )
        assert det.pixel_x == 0
        assert det.is_stable is False


class TestFistBumpCandidate:
    def test_is_ready_when_confident_and_stable(self):
        hand = HandDetection(
            gesture=HandGesture.FIST, confidence=0.9,
            handedness="Right", center_x=0.5, center_y=0.6,
            is_stable=True,
        )
        candidate = FistBumpCandidate(
            hand=hand, offer_confidence=0.85,
            hold_duration=0.6, direction="toward_alice",
        )
        assert candidate.is_ready is True

    def test_not_ready_low_confidence(self):
        hand = HandDetection(
            gesture=HandGesture.FIST, confidence=0.9,
            handedness="Right", center_x=0.5, center_y=0.6,
            is_stable=True,
        )
        candidate = FistBumpCandidate(
            hand=hand, offer_confidence=0.3,
            hold_duration=1.0, direction="toward_alice",
        )
        assert candidate.is_ready is False

    def test_not_ready_too_short(self):
        hand = HandDetection(
            gesture=HandGesture.FIST, confidence=0.9,
            handedness="Right", center_x=0.5, center_y=0.6,
            is_stable=True,
        )
        candidate = FistBumpCandidate(
            hand=hand, offer_confidence=0.9,
            hold_duration=0.1, direction="toward_alice",
        )
        assert candidate.is_ready is False

    def test_not_ready_unstable(self):
        hand = HandDetection(
            gesture=HandGesture.FIST, confidence=0.9,
            handedness="Right", center_x=0.5, center_y=0.6,
            is_stable=False,
        )
        candidate = FistBumpCandidate(
            hand=hand, offer_confidence=0.9,
            hold_duration=1.0, direction="toward_alice",
        )
        assert candidate.is_ready is False


class TestHandGestureDetectorSimulation:
    def test_simulate_mode(self):
        det = HandGestureDetector()
        det._simulate = True
        assert det.simulate is True

    def test_detect_returns_hands(self):
        det = HandGestureDetector()
        det._simulate = True
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        hands = det.detect(frame)
        assert len(hands) >= 1
        assert hands[0].gesture == HandGesture.FIST

    def test_detect_fist_bump_returns_candidate(self):
        det = HandGestureDetector()
        det._simulate = True
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        # Need to call detect first to populate fist hold timer
        det.detect(frame)
        # Simulate hold duration by setting the timer in the past
        det._fist_hold_start["Right"] = time.time() - 1.0
        candidate = det.detect_fist_bump(frame)
        assert candidate is not None
        assert candidate.hand.gesture == HandGesture.FIST
        assert candidate.hold_duration >= 0.5

    def test_detect_positions_valid(self):
        det = HandGestureDetector()
        det._simulate = True
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        hands = det.detect(frame)
        for hand in hands:
            assert 0 <= hand.center_x <= 1
            assert 0 <= hand.center_y <= 1
            assert hand.pixel_x >= 0
            assert hand.pixel_y >= 0

    def test_stop_is_safe(self):
        det = HandGestureDetector()
        det._simulate = True
        det.stop()  # should not raise


class TestHandDetectorStability:
    def test_stability_builds_over_frames(self):
        det = HandGestureDetector(stability_threshold_px=20, stability_window_s=0.5)
        det._simulate = True
        # Simulate multiple detections at same position
        now = time.time()
        det._prev_positions["Right"] = [
            (320, 240, now - 0.4),
            (322, 241, now - 0.3),
            (321, 239, now - 0.2),
            (320, 240, now - 0.1),
        ]
        is_stable = det._check_stability("Right", 321, 240, now)
        assert is_stable is True

    def test_unstable_when_moving(self):
        det = HandGestureDetector(stability_threshold_px=10, stability_window_s=0.5)
        now = time.time()
        det._prev_positions["Right"] = [
            (100, 100, now - 0.3),
            (200, 200, now - 0.2),
            (300, 300, now - 0.1),
        ]
        is_stable = det._check_stability("Right", 400, 400, now)
        assert is_stable is False
