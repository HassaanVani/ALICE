"""Teaching mode reframe — "Show ALICE where things go."

Wraps kinesthetic teaching so that when a user physically guides the arm
to place an object, ALICE learns that position as a preference in her
object memory. This replaces the generic "record a motion" framing with
a desk-assistant framing: you're teaching ALICE your preferences.
"""

import logging
import time
from typing import Optional, Tuple

logger = logging.getLogger("Teaching")


class TeachingSession:
    """A session where the user teaches ALICE object positions by guiding the arm.

    Usage:
        session = TeachingSession(kinesthetic_teacher, object_memory, calibration)
        session.start("cup")       # user is teaching where the cup goes
        # ... user guides arm to position ...
        session.record_position()  # saves current arm position as preference
        session.stop()
    """

    def __init__(self, kinesthetic_teacher, object_memory=None, calibration=None):
        self._teacher = kinesthetic_teacher
        self._memory = object_memory
        self._calibration = calibration
        self._current_label: Optional[str] = None
        self._active = False
        self._positions_taught: int = 0

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def current_label(self) -> Optional[str]:
        return self._current_label

    @property
    def positions_taught(self) -> int:
        return self._positions_taught

    def start(self, object_label: str) -> None:
        """Begin a teaching session for a specific object.

        Puts the arm in compliant mode so the user can guide it.
        """
        self._current_label = object_label
        self._active = True
        self._teacher.start(name=f"teach_{object_label}")
        logger.info(f"Teaching started: show ALICE where '{object_label}' goes")

    def record_position(self, arm_position: Optional[Tuple[float, ...]] = None) -> bool:
        """Record the current arm position as a preferred position for the object.

        If arm_position is not provided, reads from the arm controller.
        Returns True if recorded successfully.
        """
        if not self._active or self._current_label is None:
            return False

        if arm_position is None:
            arm_position = self._teacher._arm.position.as_tuple()

        # Convert arm angles to approximate workspace position
        # (rough conversion — proper FK + calibration would be more accurate)
        pos_cm = (
            arm_position[0] * 0.5,   # base rotation → x
            arm_position[1] * 0.5,   # shoulder → y
            0.0,                      # desk surface
        )

        object_id = f"{self._current_label}_0"

        if self._memory:
            self._memory.observe(object_id, self._current_label, pos_cm)
            self._memory.record_placement(object_id, pos_cm)
            logger.info(
                f"Taught: '{self._current_label}' belongs at "
                f"({pos_cm[0]:.1f}, {pos_cm[1]:.1f}, {pos_cm[2]:.1f}) cm"
            )
        else:
            logger.info(f"Position recorded (no memory): {arm_position}")

        self._positions_taught += 1
        return True

    def stop(self) -> dict:
        """End the teaching session. Returns summary."""
        motion = self._teacher.stop()
        self._active = False

        summary = {
            "label": self._current_label,
            "positions_taught": self._positions_taught,
            "motion_frames": len(motion.frames) if motion else 0,
        }

        if self._memory and self._memory.needs_save:
            self._memory.save()

        logger.info(f"Teaching complete: {summary}")
        self._current_label = None
        return summary
