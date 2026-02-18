"""Kinesthetic teaching — put arm in compliant mode, record joint angles."""

import logging
import time
from typing import Optional, List

from .puppet_ik import TeachingFrame, LearnedMotion

logger = logging.getLogger("Kinesthetic")


class KinestheticTeacher:
    """Records joint angles while arm is in compliant mode at 50ms intervals."""

    RECORD_INTERVAL_MS = 50
    MAX_FRAMES = 6000  # 5 minutes

    def __init__(self, arm_controller):
        self._arm = arm_controller
        self._recording = False
        self._current_motion: Optional[LearnedMotion] = None
        self._last_record_time: float = 0.0

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self, name: str = "kinesthetic_motion") -> None:
        """Enable compliant mode and start recording."""
        self._arm.set_compliant(True)
        self._current_motion = LearnedMotion(name=name, created_at=time.time())
        self._recording = True
        self._last_record_time = 0.0
        logger.info(f"Kinesthetic teaching started: {name}")

    def stop(self) -> Optional[LearnedMotion]:
        """Disable compliant mode and return the recorded motion."""
        self._arm.set_compliant(False)
        self._recording = False

        motion = self._current_motion
        self._current_motion = None

        if motion and motion.frames:
            logger.info(f"Kinesthetic teaching stopped: {motion.name} ({len(motion.frames)} frames)")
            return motion

        logger.warning("Kinesthetic teaching stopped with no frames recorded")
        return None

    def update(self) -> Optional[TeachingFrame]:
        """Call periodically to record a frame if interval has elapsed."""
        if not self._recording or not self._current_motion:
            return None

        if len(self._current_motion.frames) >= self.MAX_FRAMES:
            logger.warning(f"Max frames ({self.MAX_FRAMES}) reached")
            return None

        now = time.time() * 1000
        if now - self._last_record_time < self.RECORD_INTERVAL_MS:
            return None

        # Read current joint positions from the arm
        angles = self._arm.position.as_tuple()
        world_pos = (0.0, 0.0, 0.0)  # Approximate — FK would be needed for accuracy

        frame = TeachingFrame(
            timestamp=time.time(),
            world_pos=world_pos,
            joint_angles=angles,
            gripper_state=False,  # No gripper state during kinesthetic
        )

        self._current_motion.frames.append(frame)
        self._last_record_time = now
        return frame
