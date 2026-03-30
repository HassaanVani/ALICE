"""Sound effects via servo micro-oscillations — ALICE's voice comes from her body.

Instead of playing audio through a speaker, ALICE makes sounds by rapidly
oscillating her servos in patterns that produce audible vibrations. Different
patterns produce different "voices": chirps, buzzes, hums, whirrs.

The sounds ARE ALICE moving. They come from her body, not an external source.
"""

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from hardware.arm_controller import ArmController
    from hardware.dynamics import MovementDynamics

logger = logging.getLogger("SoundEffects")


class SoundCategory(Enum):
    ACKNOWLEDGE = "acknowledge"    # short chirp — "I heard you"
    CURIOUS = "curious"            # rising sweep — "what's that?"
    SATISFIED = "satisfied"        # two-note settle — "done"
    ANNOYED = "annoyed"            # low rumble — "again?"
    STARTLED = "startled"          # quick jolt — "whoa"
    THINKING = "thinking"          # slow wobble — processing
    HAPPY = "happy"                # ascending bounces — pleased
    SAD = "sad"                    # descending droop — deflated
    EXAMINING = "examining"        # scanning oscillation
    GREETING = "greeting"          # quick double-chirp — "hey"


@dataclass
class ServoPattern:
    """A servo vibration pattern that produces an audible sound.

    Each pattern defines a sequence of rapid micro-movements on one or more
    joints. The amplitude, frequency, and duration shape the sound character.
    """
    joint: int                     # which joint to oscillate (0-3)
    amplitude_deg: float           # oscillation amplitude in degrees
    frequency_hz: float            # oscillation frequency
    duration_s: float              # how long to oscillate
    sweep_to_hz: Optional[float] = None  # if set, sweep frequency from start to this
    ramp_in: float = 0.05          # seconds to ramp amplitude up (avoids click)
    ramp_out: float = 0.05         # seconds to ramp amplitude down
    repeat: int = 1                # repeat the pattern N times
    gap_s: float = 0.0             # gap between repeats


# Pattern library — each category maps to a servo vibration recipe
PATTERNS = {
    SoundCategory.ACKNOWLEDGE: [
        ServoPattern(joint=3, amplitude_deg=1.5, frequency_hz=12, duration_s=0.15),
    ],
    SoundCategory.CURIOUS: [
        # Rising frequency sweep on wrist
        ServoPattern(joint=3, amplitude_deg=2.0, frequency_hz=6, duration_s=0.3,
                     sweep_to_hz=14),
    ],
    SoundCategory.SATISFIED: [
        # Two settling taps
        ServoPattern(joint=1, amplitude_deg=1.0, frequency_hz=10, duration_s=0.12,
                     repeat=2, gap_s=0.1),
    ],
    SoundCategory.ANNOYED: [
        # Low slow rumble on base
        ServoPattern(joint=0, amplitude_deg=1.5, frequency_hz=4, duration_s=0.4),
    ],
    SoundCategory.STARTLED: [
        # Quick jolt on shoulder
        ServoPattern(joint=1, amplitude_deg=3.0, frequency_hz=15, duration_s=0.1,
                     ramp_in=0.0),
    ],
    SoundCategory.THINKING: [
        # Slow wobble on wrist
        ServoPattern(joint=3, amplitude_deg=1.0, frequency_hz=3, duration_s=0.6),
    ],
    SoundCategory.HAPPY: [
        # Three ascending bounces on shoulder
        ServoPattern(joint=1, amplitude_deg=1.5, frequency_hz=8, duration_s=0.1,
                     repeat=3, gap_s=0.08),
    ],
    SoundCategory.SAD: [
        # Descending sweep on shoulder
        ServoPattern(joint=1, amplitude_deg=1.5, frequency_hz=10, duration_s=0.35,
                     sweep_to_hz=3),
    ],
    SoundCategory.EXAMINING: [
        # Scanning oscillation on base
        ServoPattern(joint=0, amplitude_deg=2.0, frequency_hz=5, duration_s=0.4,
                     sweep_to_hz=8),
    ],
    SoundCategory.GREETING: [
        # Quick double chirp on wrist
        ServoPattern(joint=3, amplitude_deg=2.0, frequency_hz=12, duration_s=0.1,
                     repeat=2, gap_s=0.08),
    ],
}

# Map emotional states to sound categories
_EMOTION_TO_SOUND = {
    "content": None,               # silence is the default
    "curious": SoundCategory.CURIOUS,
    "annoyed": SoundCategory.ANNOYED,
    "focused": None,               # flow state — don't interrupt
    "reluctant": SoundCategory.ANNOYED,
    "satisfied": SoundCategory.SATISFIED,
    "startled": SoundCategory.STARTLED,
    "playful": SoundCategory.HAPPY,
}


class SoundEffects:
    """Produces sounds via servo micro-oscillations.

    Usage:
        sfx = SoundEffects(arm, enabled=True)
        await sfx.play(SoundCategory.CURIOUS)
    """

    def __init__(self, arm: "ArmController" = None, enabled: bool = True,
                 intensity: float = 1.0):
        self._arm = arm
        self._enabled = enabled
        self._intensity = max(0.0, min(1.0, intensity))  # scales amplitude
        self._playing = False
        self._last_play_time: float = 0.0
        self._min_interval: float = 0.3  # don't overlap sounds

    @property
    def enabled(self) -> bool:
        return self._enabled and self._arm is not None

    def set_arm(self, arm: "ArmController") -> None:
        self._arm = arm

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def set_intensity(self, intensity: float) -> None:
        self._intensity = max(0.0, min(1.0, intensity))

    async def play(self, category: SoundCategory) -> bool:
        """Play a servo vibration pattern. Returns True if played."""
        if not self.enabled or self._playing:
            return False

        now = time.time()
        if now - self._last_play_time < self._min_interval:
            return False

        patterns = PATTERNS.get(category)
        if not patterns:
            return False

        self._playing = True
        self._last_play_time = now

        try:
            for pattern in patterns:
                await self._execute_pattern(pattern)
            return True
        except Exception as e:
            logger.debug(f"Sound effect error: {e}")
            return False
        finally:
            self._playing = False

    async def play_for_emotion(self, emotion: str) -> bool:
        """Play the sound mapped to an emotional state."""
        category = _EMOTION_TO_SOUND.get(emotion)
        if category is None:
            return False
        return await self.play(category)

    async def _execute_pattern(self, pattern: ServoPattern) -> bool:
        """Execute a single servo vibration pattern."""
        if self._arm is None:
            return False

        base_pos = self._arm.position.as_tuple()
        center = base_pos[pattern.joint]
        amplitude = pattern.amplitude_deg * self._intensity

        for rep in range(pattern.repeat):
            if rep > 0 and pattern.gap_s > 0:
                await asyncio.sleep(pattern.gap_s)

            start_time = time.time()
            elapsed = 0.0

            while elapsed < pattern.duration_s:
                elapsed = time.time() - start_time
                t = elapsed / pattern.duration_s if pattern.duration_s > 0 else 1.0

                # Frequency (with optional sweep)
                if pattern.sweep_to_hz is not None:
                    freq = pattern.frequency_hz + (pattern.sweep_to_hz - pattern.frequency_hz) * t
                else:
                    freq = pattern.frequency_hz

                # Amplitude envelope (ramp in/out)
                env = 1.0
                if elapsed < pattern.ramp_in and pattern.ramp_in > 0:
                    env = elapsed / pattern.ramp_in
                elif (pattern.duration_s - elapsed) < pattern.ramp_out and pattern.ramp_out > 0:
                    env = (pattern.duration_s - elapsed) / pattern.ramp_out

                # Oscillation
                offset = amplitude * env * math.sin(2 * math.pi * freq * elapsed)

                # Build target angles — only modify the target joint
                target = list(base_pos)
                target[pattern.joint] = center + offset
                self._arm.move_to(tuple(target), speed=100)

                # Yield to event loop — servo update rate
                await asyncio.sleep(0.01)

        # Return to original position
        self._arm.move_to(base_pos, speed=80)
        return True
