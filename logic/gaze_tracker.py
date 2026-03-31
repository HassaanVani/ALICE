"""Gaze tracking — ALICE watches you.

Smoothly orients the arm toward the most interesting target: the user's face,
a curious object, or an ambient scan. The arm never snaps — it drifts with
an exponential moving average, producing the uncanny sense that she's alive
and paying attention.

Target priority: face > curiosity target > last interesting object > idle scan.
"""

import logging
import math
import time
from dataclasses import dataclass
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from hardware.dynamics import MovementDynamics

logger = logging.getLogger("GazeTracker")


@dataclass
class GazeTarget:
    """What ALICE is looking at right now."""
    target_type: str          # "face", "object", "scan", "idle"
    label: str                # "user", object label, or ""
    angles: Tuple[float, ...] # target j1-j4
    priority: float           # 0.0-1.0
    timestamp: float = 0.0


class GazeTracker:
    """Smooth gaze tracking that makes the arm follow points of interest.

    The tracker maintains a smoothed target that the arm drifts toward.
    It never commands the arm directly — it provides target angles that
    the idle loop or dynamics system can apply.

    Usage:
        gaze = GazeTracker()
        gaze.update_face({"center_x": 640, "center_y": 400, ...})
        target = gaze.get_target()
        # Apply target.angles via dynamics
    """

    # Camera frame dimensions (front-facing, used for face mapping)
    FRAME_WIDTH = 1280.0
    FRAME_HEIGHT = 720.0

    # Joint mapping ranges for face tracking
    # Face at left edge of frame → j1 = +MAX_J1, right edge → -MAX_J1
    MAX_J1_FACE = 40.0   # degrees base rotation range for tracking
    MAX_J2_FACE = 15.0   # degrees shoulder range for vertical tracking

    # Neutral "looking forward" position
    NEUTRAL_ANGLES = (0.0, 10.0, 0.0, 0.0)

    # Smoothing — lower = smoother/slower tracking
    DEFAULT_ALPHA = 0.06

    # Face tracking timeout — stop tracking if no face update in this long
    FACE_TIMEOUT = 2.0

    # Idle scan parameters
    SCAN_AMPLITUDE = 25.0  # degrees
    SCAN_PERIOD = 6.0      # seconds for one full sweep

    def __init__(self, alpha: float = None, face_priority: float = 0.8):
        self._alpha = alpha or self.DEFAULT_ALPHA
        self._face_priority = face_priority
        self._llm_interpreter = None

        # Current smoothed target angles
        self._current = list(self.NEUTRAL_ANGLES)

        # Raw targets by source
        self._face_target: Optional[Tuple[float, ...]] = None
        self._face_time: float = 0.0

        self._curiosity_target: Optional[Tuple[float, ...]] = None
        self._curiosity_label: str = ""

        self._interest_target: Optional[Tuple[float, ...]] = None

        # Scan phase for idle behavior
        self._scan_phase: float = 0.0
        self._last_tick: float = 0.0

    def set_llm_interpreter(self, interp) -> None:
        """Attach LLM interpreter for dynamic scan modulation."""
        self._llm_interpreter = interp

    def update_face(self, face_info: dict) -> None:
        """Feed face detection data.

        Args:
            face_info: dict with 'center_x', 'center_y', 'distance_cm'.
                       Pixel coordinates in the front camera frame.
        """
        cx = face_info.get("center_x", self.FRAME_WIDTH / 2)
        cy = face_info.get("center_y", self.FRAME_HEIGHT / 2)

        # Map pixel position to joint angles
        # Face at center → 0°. Face at left edge → positive j1 (turn left).
        norm_x = (cx / self.FRAME_WIDTH) - 0.5   # -0.5 to 0.5
        norm_y = (cy / self.FRAME_HEIGHT) - 0.5  # -0.5 to 0.5

        j1 = -norm_x * 2 * self.MAX_J1_FACE  # invert: face on left → arm turns left
        j2 = self.NEUTRAL_ANGLES[1] - norm_y * 2 * self.MAX_J2_FACE  # face high → look up

        self._face_target = (j1, j2, self.NEUTRAL_ANGLES[2], self.NEUTRAL_ANGLES[3])
        self._face_time = time.time()

    def update_objects(self, detections: list) -> None:
        """Feed YOLO detections for glancing at interesting objects.

        Takes the detection with highest confidence and stores it as an
        interest point the idle scan can drift toward.
        """
        if not detections:
            return

        # Pick highest confidence detection
        best = max(detections, key=lambda d: getattr(d, 'confidence', 0.0))
        if hasattr(best, 'center_x') and hasattr(best, 'center_y'):
            # Map from overhead camera coords to approximate gaze angles
            # This is rough — calibration would improve it
            self._interest_target = self._pixel_to_gaze(
                best.center_x, best.center_y
            )

    def set_curiosity_target(self, label: str, pixel_x: int, pixel_y: int) -> None:
        """Curiosity engine requests ALICE look at a specific object."""
        self._curiosity_target = self._pixel_to_gaze(pixel_x, pixel_y)
        self._curiosity_label = label

    def clear_curiosity_target(self) -> None:
        """Curiosity examination complete."""
        self._curiosity_target = None
        self._curiosity_label = ""

    def get_target(self) -> GazeTarget:
        """Return the current smoothed gaze target.

        Priority: face > curiosity > interest point > idle scan.
        """
        now = time.time()
        dt = now - self._last_tick if self._last_tick > 0 else 0.1
        self._last_tick = now
        self._scan_phase += dt

        # Determine raw target by priority
        raw_target: Tuple[float, ...]
        target_type: str
        label: str
        priority: float

        face_fresh = (self._face_target is not None and
                      now - self._face_time < self.FACE_TIMEOUT)

        if face_fresh:
            raw_target = self._face_target
            target_type = "face"
            label = "user"
            priority = self._face_priority
        elif self._curiosity_target is not None:
            raw_target = self._curiosity_target
            target_type = "object"
            label = self._curiosity_label
            priority = 0.6
        elif self._interest_target is not None:
            raw_target = self._interest_target
            target_type = "object"
            label = ""
            priority = 0.3
        else:
            # Idle scan — sinusoidal sweep, modulated by LLM
            scan_amp = self.SCAN_AMPLITUDE
            scan_per = self.SCAN_PERIOD
            if self._llm_interpreter is not None:
                scan_amp *= self._llm_interpreter.modifiers.scn
                scan_per *= self._llm_interpreter.modifiers.per
            scan_j1 = scan_amp * math.sin(
                2 * math.pi * self._scan_phase / scan_per
            )
            raw_target = (scan_j1, self.NEUTRAL_ANGLES[1],
                          self.NEUTRAL_ANGLES[2], self.NEUTRAL_ANGLES[3])
            target_type = "scan"
            label = ""
            priority = 0.1

        # Smooth toward raw target with exponential moving average
        for i in range(4):
            self._current[i] += self._alpha * (raw_target[i] - self._current[i])

        return GazeTarget(
            target_type=target_type,
            label=label,
            angles=tuple(self._current),
            priority=priority,
            timestamp=now,
        )

    async def apply(self, dynamics: "MovementDynamics") -> None:
        """Move the arm toward the current gaze target.

        Replaces idle_micro_motion when gaze tracking is active.
        Uses direct arm control at low speed for smooth tracking.
        """
        target = self.get_target()
        dynamics.arm.move_to(target.angles, speed=15)

    def _pixel_to_gaze(self, px: float, py: float,
                       frame_w: float = 1920, frame_h: float = 1080) -> Tuple[float, ...]:
        """Rough mapping from overhead camera pixel coords to gaze angles.

        This is approximate — proper calibration would use the CalibrationManager.
        But for "look at that object" it's good enough.
        """
        norm_x = (px / frame_w) - 0.5
        norm_y = (py / frame_h) - 0.5

        j1 = -norm_x * 2 * 50.0  # wider range for overhead camera
        j2 = 10.0 - norm_y * 2 * 20.0

        return (j1, j2, 0.0, 0.0)

    def reset(self) -> None:
        """Reset to neutral gaze."""
        self._current = list(self.NEUTRAL_ANGLES)
        self._face_target = None
        self._curiosity_target = None
        self._interest_target = None
        self._curiosity_label = ""
