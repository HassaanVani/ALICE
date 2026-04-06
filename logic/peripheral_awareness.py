"""Peripheral awareness — ALICE notices you without looking directly at you.

The front camera is ALICE's peripheral vision. It passively watches for
interesting events: a fist offered, a wave, someone new arriving, a hand
reaching across the desk. When it catches something, it doesn't interrupt
what ALICE is doing. Instead, it schedules a "glance" — a natural moment
in her existing motion where the arm sweeps slightly further, letting
the arm-mounted camera catch a quick look at the user.

The glance is the key behavior. She doesn't stop organizing to stare at
you. She finds a moment during a retract or a scan where turning a bit
further is natural, grabs a frame with her real eyes (arm camera), and
decides whether to engage.

This is how you look at someone you care about without them noticing.
You don't stop what you're doing. You find excuses to look their way.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Tuple

logger = logging.getLogger("PeripheralAwareness")


class PeripheralEvent(Enum):
    """Something interesting detected in peripheral vision."""
    FIST_OFFERED = "fist_offered"
    HAND_WAVE = "hand_wave"
    REACHING = "reaching"
    NEW_PERSON = "new_person"
    PERSON_LEFT = "person_left"


@dataclass
class Glance:
    """A scheduled glance — ALICE will look when the moment is right."""
    event: PeripheralEvent
    detected_at: float
    confidence: float
    expires_at: float          # glance window — if she misses it, it's gone
    pixel_hint: Optional[Tuple[int, int]] = None  # where in the front frame
    executed: bool = False

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at


class PeripheralAwareness:
    """Monitors the front camera for interesting events and schedules glances.

    The front camera runs presence detection + hand detection passively.
    When something interesting is spotted, a Glance is queued. The idle
    loop (or any movement routine) checks for pending glances and executes
    them during natural motion pauses.

    Usage:
        pa = PeripheralAwareness()
        pa.set_hand_detector(hand_detector)

        # Called every tick from idle loop with front camera frame
        pa.update(front_frame, presence_info)

        # Called during natural motion pauses
        glance = pa.get_pending_glance()
        if glance:
            frame = arm_camera_getter()
            result = pa.execute_glance(glance, frame)
    """

    # How long a glance opportunity stays valid (seconds)
    GLANCE_WINDOW = 4.0

    # Minimum time between glances (don't be creepy)
    GLANCE_COOLDOWN = 8.0

    # Minimum time between peripheral scans (don't burn CPU)
    SCAN_INTERVAL = 0.5

    def __init__(self):
        self._hand_detector = None
        self._pending_glance: Optional[Glance] = None
        self._last_glance_time: float = 0.0
        self._last_scan_time: float = 0.0

        # Callbacks — fired when a glance confirms something
        self._on_fist_confirmed: Optional[Callable] = None
        self._on_wave_confirmed: Optional[Callable] = None

    def set_hand_detector(self, detector) -> None:
        self._hand_detector = detector

    def set_on_fist_confirmed(self, callback: Callable) -> None:
        """Called when a glance confirms a fist bump offer."""
        self._on_fist_confirmed = callback

    def set_on_wave_confirmed(self, callback: Callable) -> None:
        """Called when a glance confirms a wave/greeting."""
        self._on_wave_confirmed = callback

    @property
    def has_pending_glance(self) -> bool:
        if self._pending_glance is None:
            return False
        if self._pending_glance.expired or self._pending_glance.executed:
            self._pending_glance = None
            return False
        return True

    def update(self, front_frame, presence_info=None) -> None:
        """Feed a front camera frame. Detects interesting events peripherally.

        Called every tick from the idle loop. Lightweight — skips if scanned recently.
        """
        now = time.time()

        # Rate limit peripheral scans
        if now - self._last_scan_time < self.SCAN_INTERVAL:
            return
        self._last_scan_time = now

        # Don't queue if we already have a pending glance or on cooldown
        if self.has_pending_glance:
            return
        if now - self._last_glance_time < self.GLANCE_COOLDOWN:
            return

        if front_frame is None:
            return

        # Check for hand gestures in peripheral vision
        if self._hand_detector is not None:
            try:
                result = self._hand_detector.detect(front_frame)
                if result is not None:
                    gesture = getattr(result, 'gesture', None)
                    if gesture == 'fist':
                        self._queue_glance(PeripheralEvent.FIST_OFFERED, 0.7)
                        return
                    elif gesture in ('open', 'wave'):
                        self._queue_glance(PeripheralEvent.HAND_WAVE, 0.5)
                        return
            except Exception:
                pass

        # Check for new presence (someone just sat down)
        if presence_info is not None:
            if (presence_info.detected and
                    presence_info.closest_distance < 80.0):
                # Someone is close — worth a glance if we haven't looked recently
                self._queue_glance(PeripheralEvent.NEW_PERSON, 0.3)

    def _queue_glance(self, event: PeripheralEvent, confidence: float) -> None:
        now = time.time()
        self._pending_glance = Glance(
            event=event,
            detected_at=now,
            confidence=confidence,
            expires_at=now + self.GLANCE_WINDOW,
        )
        logger.debug(f"Peripheral: queued glance for {event.value} (conf={confidence:.1f})")

    def get_pending_glance(self) -> Optional[Glance]:
        """Check if there's a glance waiting. Called during natural motion pauses."""
        if not self.has_pending_glance:
            return None
        return self._pending_glance

    def execute_glance(self, glance: Glance, arm_frame) -> Optional[PeripheralEvent]:
        """Execute a glance — process the arm camera frame to confirm the event.

        Called after the arm has swept toward the user. The arm camera
        is now pointed roughly at them. Check if the peripheral detection
        was real.

        Returns the confirmed event, or None if it was a false positive.
        """
        glance.executed = True
        self._last_glance_time = time.time()
        self._pending_glance = None

        if arm_frame is None:
            return None

        # Confirm with arm camera (higher quality, direct view)
        if glance.event == PeripheralEvent.FIST_OFFERED:
            if self._hand_detector is not None:
                try:
                    result = self._hand_detector.detect(arm_frame)
                    if result is not None and getattr(result, 'gesture', None) == 'fist':
                        logger.info("Peripheral: fist bump confirmed by arm camera")
                        if self._on_fist_confirmed:
                            self._on_fist_confirmed()
                        return PeripheralEvent.FIST_OFFERED
                except Exception:
                    pass

        elif glance.event == PeripheralEvent.HAND_WAVE:
            if self._hand_detector is not None:
                try:
                    result = self._hand_detector.detect(arm_frame)
                    if result is not None and getattr(result, 'gesture', None) in ('open', 'wave'):
                        logger.info("Peripheral: wave confirmed by arm camera")
                        if self._on_wave_confirmed:
                            self._on_wave_confirmed()
                        return PeripheralEvent.HAND_WAVE
                except Exception:
                    pass

        elif glance.event == PeripheralEvent.NEW_PERSON:
            # New person doesn't need arm camera confirmation —
            # front camera presence is sufficient
            return PeripheralEvent.NEW_PERSON

        return None

    def reset(self) -> None:
        """Clear pending glances."""
        self._pending_glance = None
