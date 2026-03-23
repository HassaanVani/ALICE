"""Movement Dynamics — wraps ArmController with emotional speed curves and hesitation.

The arm doesn't just move to positions. It moves with *intent*. Fast when ALICE
chooses, slow when she's told, with pauses that read as decision-making.

See PERSONALITY.md § Movement as Emotion for the full spec.
"""

import asyncio
import logging
import math
import time
from typing import Optional, Tuple

from .arm_controller import ArmController, ArmPosition

logger = logging.getLogger("Dynamics")


class MovementDynamics:
    """Wraps ArmController with personality-driven movement modifiers.

    Usage:
        dynamics = MovementDynamics(arm, personality_engine)
        await dynamics.move_to(angles, origin=ActionOrigin.SELF_INITIATED)
        await dynamics.idle_micro_motion()
    """

    BASE_SPEED = 50.0  # arm controller default

    # Idle micro-motion parameters
    MICRO_AMPLITUDE = 2.0    # degrees — subtle
    MICRO_PERIOD = 4.0       # seconds — slow breathing rhythm

    def __init__(self, arm: ArmController, personality=None):
        self._arm = arm
        self._personality = personality
        self._last_micro_time: float = 0.0
        self._micro_phase: float = 0.0
        self._last_interest_angles: Optional[Tuple[float, ...]] = None

    @property
    def arm(self) -> ArmController:
        """Access the underlying arm controller directly when needed."""
        return self._arm

    @property
    def position(self) -> ArmPosition:
        return self._arm.position

    async def move_to(self, angles: Tuple[float, ...],
                      speed: Optional[float] = None,
                      origin=None) -> bool:
        """Move with personality-appropriate speed and hesitation.

        Args:
            angles: Target joint angles.
            speed: Override speed (0-100). If None, uses personality-derived speed.
            origin: ActionOrigin from personality engine — determines feel.
        """
        from logic.personality import ActionOrigin

        if origin is None:
            origin = ActionOrigin.USER_REQUESTED

        # Get personality modifiers
        speed_mult = 1.0
        hesitation = 0.0

        if self._personality is not None:
            speed_mult = self._personality.get_speed_multiplier(origin)
            hesitation = self._personality.get_hesitation(origin)
            self._personality.on_task_start(origin)

        # Apply hesitation — the pause before acting
        if hesitation > 0:
            logger.debug(f"Hesitating {hesitation:.1f}s ({origin.value})")
            await asyncio.sleep(hesitation)

        # Calculate effective speed
        base = speed if speed is not None else self.BASE_SPEED
        effective_speed = max(5, min(100, base * speed_mult))

        logger.debug(
            f"Moving: speed={effective_speed:.0f} "
            f"(base={base:.0f} × {speed_mult:.1f}), origin={origin.value}"
        )

        return self._arm.move_to(angles, speed=effective_speed)

    async def move_to_urgent(self, angles: Tuple[float, ...],
                             speed: float = 90) -> bool:
        """Move fast with no hesitation — for reactive moments (spill cleanup, etc).

        This is the fastest ALICE moves. No personality modifiers, no pause.
        The speed itself IS the personality signal.
        """
        logger.debug(f"Urgent move: speed={speed}")
        return self._arm.move_to(angles, speed=speed)

    async def move_with_settle(self, angles: Tuple[float, ...],
                               settle_time: float = 0.15,
                               origin=None) -> bool:
        """Move, then pause briefly — the 'evaluating her work' beat."""
        success = await self.move_to(angles, origin=origin)
        if success:
            await asyncio.sleep(settle_time)
        return success

    async def idle_micro_motion(self) -> None:
        """Subtle idle scanning — ALICE is never fully still when awake.

        Produces a slow sinusoidal drift on the base joint (j1), oriented
        toward the last point of interest if available.
        """
        now = time.time()
        dt = now - self._last_micro_time if self._last_micro_time else 0.0
        self._last_micro_time = now
        self._micro_phase += dt

        # Sinusoidal drift on base rotation
        offset = self.MICRO_AMPLITUDE * math.sin(
            2 * math.pi * self._micro_phase / self.MICRO_PERIOD
        )

        current = self._arm.position.as_tuple()

        # Bias toward last interest point if available
        base_target = current[0]
        if self._last_interest_angles is not None:
            # Slowly drift toward interest point
            interest_j1 = self._last_interest_angles[0]
            base_target = current[0] + (interest_j1 - current[0]) * 0.02

        target = (base_target + offset, current[1], current[2], current[3])

        # Move slowly — this should be barely perceptible
        self._arm.move_to(target, speed=15)

    def set_interest_point(self, angles: Tuple[float, ...]) -> None:
        """Set the point ALICE's idle scanning should orient toward."""
        self._last_interest_angles = angles

    async def settle_motion(self) -> None:
        """Small settling movement after completing a task — like a sigh.

        A tiny retraction and return, signaling 'done'.
        """
        current = self._arm.position.as_tuple()
        # Slight lift on j2 (shoulder)
        lifted = (current[0], current[1] + 1.5, current[2], current[3])
        self._arm.move_to(lifted, speed=20)
        await asyncio.sleep(0.3)
        # Return
        self._arm.move_to(current, speed=20)
        await asyncio.sleep(0.2)

    def home(self) -> bool:
        """Return to home position."""
        return self._arm.home()
