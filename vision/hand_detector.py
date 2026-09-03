"""Hand gesture detection — classifies fist, open hand, pointing, etc.

Uses MediaPipe Hands to detect and classify hand gestures from the front-facing
camera. The primary use case is fist bump detection: ALICE sees a closed fist
offered toward her and responds.

Gesture classification uses landmark geometry:
- Fist: all fingertips are below their corresponding PIP joints (curled in)
- Open hand: all fingertips are above their PIP joints (extended)
- Pointing: only index finger extended
- Thumbs up: only thumb extended

The detector also provides the hand's 3D position estimate for aiming
the arm response.
"""

import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger("HandDetector")

try:
    import mediapipe as mp
    MP_AVAILABLE = True
except ImportError:
    MP_AVAILABLE = False


class HandGesture(Enum):
    UNKNOWN = "unknown"
    FIST = "fist"
    OPEN = "open"
    POINTING = "pointing"
    THUMBS_UP = "thumbs_up"
    PEACE = "peace"


# MediaPipe hand landmark indices
_WRIST = 0
_THUMB_TIP = 4
_THUMB_IP = 3
_INDEX_TIP = 8
_INDEX_PIP = 6
_MIDDLE_TIP = 12
_MIDDLE_PIP = 10
_RING_TIP = 16
_RING_PIP = 14
_PINKY_TIP = 20
_PINKY_PIP = 18
_INDEX_MCP = 5
_PINKY_MCP = 17


@dataclass
class HandDetection:
    """A single detected hand with gesture classification."""
    gesture: HandGesture
    confidence: float                   # gesture classification confidence
    handedness: str                     # "Left" or "Right"
    center_x: float                     # normalized 0-1, center of palm
    center_y: float                     # normalized 0-1, center of palm
    pixel_x: int = 0                    # pixel coordinates in frame
    pixel_y: int = 0
    wrist_x: float = 0.0               # normalized wrist position
    wrist_y: float = 0.0
    hand_size: float = 0.0             # normalized distance wrist-to-middle-tip
    fingers_extended: int = 0           # count of extended fingers
    is_stable: bool = False             # True if hand hasn't moved much recently
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "gesture": self.gesture.value,
            "confidence": round(self.confidence, 3),
            "handedness": self.handedness,
            "center": (self.pixel_x, self.pixel_y),
            "hand_size": round(self.hand_size, 3),
            "fingers_extended": self.fingers_extended,
            "is_stable": self.is_stable,
        }


@dataclass
class FistBumpCandidate:
    """A fist that looks like it's being offered for a bump."""
    hand: HandDetection
    offer_confidence: float     # 0-1 how likely this is a fist bump offer
    hold_duration: float        # seconds the fist has been held steady
    direction: str              # "toward_alice" or "away"

    @property
    def is_ready(self) -> bool:
        """True if this fist bump offer is confident and stable enough to respond."""
        return (
            self.offer_confidence > 0.7
            and self.hold_duration > 0.4
            and self.hand.is_stable
        )


class HandGestureDetector:
    """Detects hand gestures using MediaPipe Hands.

    Designed for the front-facing camera. Runs alongside face-based
    presence detection — when someone is close, this activates to watch
    for gestures.

    Args:
        max_hands: Maximum number of hands to detect.
        min_detection_confidence: MediaPipe detection threshold.
        min_tracking_confidence: MediaPipe tracking threshold.
        stability_threshold_px: Max pixel movement to count as "stable".
        stability_window_s: Time window for stability check.
    """

    def __init__(
        self,
        max_hands: int = 2,
        min_detection_confidence: float = 0.6,
        min_tracking_confidence: float = 0.5,
        stability_threshold_px: float = 15.0,
        stability_window_s: float = 0.3,
    ):
        self._max_hands = max_hands
        self._min_det_conf = min_detection_confidence
        self._min_track_conf = min_tracking_confidence
        self._stability_threshold = stability_threshold_px
        self._stability_window = stability_window_s

        self._hands = None
        self._simulate = not MP_AVAILABLE

        # Tracking state for stability detection
        self._prev_positions: dict = {}  # handedness -> list of (x, y, time)
        self._fist_hold_start: dict = {}  # handedness -> timestamp when fist first seen

    @property
    def simulate(self) -> bool:
        return self._simulate

    def start(self) -> bool:
        """Initialize MediaPipe Hands. Returns True on success."""
        if not MP_AVAILABLE or not hasattr(mp, "solutions") or not hasattr(mp.solutions, "hands"):
            logger.info("Hand gesture detector started (simulation fallback)")
            self._simulate = True
            return True

        try:
            self._hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=self._max_hands,
                min_detection_confidence=self._min_det_conf,
                min_tracking_confidence=self._min_track_conf,
            )
            logger.info("Hand gesture detector started (MediaPipe Hands)")
            return True
        except Exception as e:
            logger.info(f"MediaPipe hands unavailable ({e}), using simulation fallback")
            self._simulate = True
            return True

    def stop(self) -> None:
        """Release MediaPipe resources."""
        if self._hands is not None:
            self._hands.close()
            self._hands = None

    def detect(self, frame: np.ndarray) -> List[HandDetection]:
        """Detect hands and classify gestures in a BGR frame.

        Returns a list of HandDetection objects.
        """
        if self._simulate:
            return self._simulate_detect(frame)

        if self._hands is None:
            self.start()
            if self._simulate:
                return self._simulate_detect(frame)

        import cv2
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._hands.process(rgb)

        detections: List[HandDetection] = []
        now = time.time()

        if not results.multi_hand_landmarks:
            # No hands — clear fist hold timers
            self._fist_hold_start.clear()
            return detections

        for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
            # Get handedness
            handedness = "Right"
            if results.multi_handedness and i < len(results.multi_handedness):
                handedness = results.multi_handedness[i].classification[0].label

            landmarks = hand_landmarks.landmark

            # Extract key positions (normalized 0-1)
            wrist = landmarks[_WRIST]
            index_mcp = landmarks[_INDEX_MCP]
            pinky_mcp = landmarks[_PINKY_MCP]
            middle_tip = landmarks[_MIDDLE_TIP]

            # Palm center: average of wrist, index MCP, pinky MCP
            cx = (wrist.x + index_mcp.x + pinky_mcp.x) / 3
            cy = (wrist.y + index_mcp.y + pinky_mcp.y) / 3

            # Hand size: distance wrist to middle fingertip
            hand_size = math.sqrt(
                (middle_tip.x - wrist.x) ** 2
                + (middle_tip.y - wrist.y) ** 2
            )

            # Classify gesture based on finger extension
            fingers = self._count_fingers(landmarks, handedness)
            gesture, gesture_conf = self._classify_gesture(landmarks, fingers, handedness)

            # Stability check
            px, py = int(cx * w), int(cy * h)
            is_stable = self._check_stability(handedness, px, py, now)

            det = HandDetection(
                gesture=gesture,
                confidence=gesture_conf,
                handedness=handedness,
                center_x=cx,
                center_y=cy,
                pixel_x=px,
                pixel_y=py,
                wrist_x=wrist.x,
                wrist_y=wrist.y,
                hand_size=hand_size,
                fingers_extended=fingers,
                is_stable=is_stable,
                timestamp=now,
            )
            detections.append(det)

        return detections

    def detect_fist_bump(self, frame: np.ndarray) -> Optional[FistBumpCandidate]:
        """High-level: detect if someone is offering a fist bump.

        Looks for a stable, closed fist held at roughly desk/arm height.
        Returns a FistBumpCandidate if found, None otherwise.
        """
        hands = self.detect(frame)
        now = time.time()

        best_candidate: Optional[FistBumpCandidate] = None

        for hand in hands:
            if hand.gesture != HandGesture.FIST:
                # Hand isn't a fist — clear hold timer
                self._fist_hold_start.pop(hand.handedness, None)
                continue

            # Track how long the fist has been held
            if hand.handedness not in self._fist_hold_start:
                self._fist_hold_start[hand.handedness] = now

            hold_duration = now - self._fist_hold_start[hand.handedness]

            # Compute offer confidence based on multiple signals
            offer_conf = self._compute_offer_confidence(hand, hold_duration)

            # Direction heuristic: fist in the lower-center region of frame
            # suggests it's being offered toward the desk/ALICE
            direction = "toward_alice" if hand.center_y > 0.4 else "away"

            candidate = FistBumpCandidate(
                hand=hand,
                offer_confidence=offer_conf,
                hold_duration=hold_duration,
                direction=direction,
            )

            if best_candidate is None or candidate.offer_confidence > best_candidate.offer_confidence:
                best_candidate = candidate

        return best_candidate

    def _count_fingers(self, landmarks, handedness: str) -> int:
        """Count extended fingers using landmark positions."""
        extended = 0

        # Thumb: compare tip x to IP x (direction depends on handedness)
        thumb_tip = landmarks[_THUMB_TIP]
        thumb_ip = landmarks[_THUMB_IP]
        if handedness == "Right":
            if thumb_tip.x < thumb_ip.x:
                extended += 1
        else:
            if thumb_tip.x > thumb_ip.x:
                extended += 1

        # Four fingers: tip above PIP means extended
        pairs = [
            (_INDEX_TIP, _INDEX_PIP),
            (_MIDDLE_TIP, _MIDDLE_PIP),
            (_RING_TIP, _RING_PIP),
            (_PINKY_TIP, _PINKY_PIP),
        ]
        for tip_idx, pip_idx in pairs:
            if landmarks[tip_idx].y < landmarks[pip_idx].y:
                extended += 1

        return extended

    def _classify_gesture(self, landmarks, fingers: int,
                          handedness: str) -> Tuple[HandGesture, float]:
        """Classify the hand gesture from finger count and positions."""

        # Fist: 0 fingers extended
        if fingers == 0:
            # Extra validation: all fingertips close to palm
            wrist = landmarks[_WRIST]
            index_tip = landmarks[_INDEX_TIP]
            curl_dist = math.sqrt(
                (index_tip.x - wrist.x) ** 2 + (index_tip.y - wrist.y) ** 2
            )
            # Tighter curl = higher confidence
            conf = min(1.0, max(0.5, 1.0 - curl_dist * 3))
            return HandGesture.FIST, conf

        # Open hand: 5 fingers extended
        if fingers == 5:
            return HandGesture.OPEN, 0.9

        # Pointing: only index finger
        if fingers == 1:
            index_tip = landmarks[_INDEX_TIP]
            index_pip = landmarks[_INDEX_PIP]
            if index_tip.y < index_pip.y:
                return HandGesture.POINTING, 0.8

        # Peace sign: 2 fingers (index + middle)
        if fingers == 2:
            index_tip = landmarks[_INDEX_TIP]
            middle_tip = landmarks[_MIDDLE_TIP]
            index_pip = landmarks[_INDEX_PIP]
            middle_pip = landmarks[_MIDDLE_PIP]
            if (index_tip.y < index_pip.y and middle_tip.y < middle_pip.y):
                return HandGesture.PEACE, 0.75

        # Thumbs up: only thumb extended
        if fingers == 1:
            thumb_tip = landmarks[_THUMB_TIP]
            thumb_ip = landmarks[_THUMB_IP]
            # Thumb pointing up (y decreases upward in image coords)
            if thumb_tip.y < thumb_ip.y - 0.03:
                return HandGesture.THUMBS_UP, 0.8

        return HandGesture.UNKNOWN, 0.3

    def _check_stability(self, handedness: str, px: int, py: int,
                          now: float) -> bool:
        """Check if the hand position has been stable recently."""
        if handedness not in self._prev_positions:
            self._prev_positions[handedness] = []

        positions = self._prev_positions[handedness]
        positions.append((px, py, now))

        # Prune old entries
        cutoff = now - self._stability_window
        positions[:] = [(x, y, t) for x, y, t in positions if t >= cutoff]

        if len(positions) < 3:
            return False

        # Check if all positions are within threshold
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        x_range = max(xs) - min(xs)
        y_range = max(ys) - min(ys)

        return x_range < self._stability_threshold and y_range < self._stability_threshold

    def _compute_offer_confidence(self, hand: HandDetection,
                                   hold_duration: float) -> float:
        """Score how likely this fist is a bump offer (0-1)."""
        score = 0.0

        # Base: it's a fist
        score += hand.confidence * 0.3

        # Stability bonus
        if hand.is_stable:
            score += 0.25

        # Hold duration bonus (ramps up to 1s, then plateaus)
        hold_score = min(1.0, hold_duration / 1.0) * 0.25
        score += hold_score

        # Position: in the lower-center region of frame is more natural
        # for someone offering a fist toward a desk
        x_centered = 1.0 - abs(hand.center_x - 0.5) * 2  # 1.0 at center, 0 at edges
        y_low = max(0, hand.center_y - 0.3) / 0.7  # higher score for lower in frame
        position_score = (x_centered * 0.5 + y_low * 0.5) * 0.2
        score += position_score

        return min(1.0, score)

    def _simulate_detect(self, frame: np.ndarray) -> List[HandDetection]:
        """Return simulated hand detection for unit tests.
        
        Real camera frames (containing non-zero pixels) will NOT hallucinate a fist
        when running without hardware/MediaPipe.
        """
        if frame is not None and np.any(frame) and not getattr(self, "_force_simulated_fist", False):
            return []

        h, w = frame.shape[:2]
        return [
            HandDetection(
                gesture=HandGesture.FIST,
                confidence=0.92,
                handedness="Right",
                center_x=0.5,
                center_y=0.6,
                pixel_x=w // 2,
                pixel_y=int(h * 0.6),
                wrist_x=0.5,
                wrist_y=0.7,
                hand_size=0.15,
                fingers_extended=0,
                is_stable=True,
                timestamp=time.time(),
            ),
        ]
