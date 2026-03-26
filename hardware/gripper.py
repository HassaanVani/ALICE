"""Gripper abstraction — ABC + adapters + ParallelGripper for Elephant Robotics."""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("Gripper")


@dataclass
class GripPreset:
    """Preset grip parameters for a known object class."""
    name: str
    grip_value: int       # 0 (fully closed) to 100 (fully open) for pymycobot
    approach_speed: int = 50
    hold_verify_ms: int = 200


GRIP_PRESETS = {
    "cup": GripPreset("cup", grip_value=60, approach_speed=30),
    "pen": GripPreset("pen", grip_value=80, approach_speed=50),
    "book": GripPreset("book", grip_value=40, approach_speed=30),
    "tissue": GripPreset("tissue", grip_value=90, approach_speed=70),
    "phone": GripPreset("phone", grip_value=75, approach_speed=40),
    "default": GripPreset("default", grip_value=70, approach_speed=50),
}


class Gripper(ABC):
    @abstractmethod
    def open(self) -> bool:
        ...

    @abstractmethod
    def close(self) -> bool:
        ...

    @abstractmethod
    def set_position(self, position: float) -> bool:
        """Set gripper position from 0.0 (fully open) to 1.0 (fully closed)."""
        ...

    @abstractmethod
    def get_position(self) -> float:
        ...

    @property
    @abstractmethod
    def is_proportional(self) -> bool:
        """True if gripper supports proportional control."""
        ...


class MagnetGripperAdapter(Gripper):
    """Wraps existing MagnetDriver as a Gripper — binary only (threshold at 0.5)."""

    def __init__(self, magnet_driver):
        self._magnet = magnet_driver
        self._position = 0.0

    def open(self) -> bool:
        self._position = 0.0
        return self._magnet.off()

    def close(self) -> bool:
        self._position = 1.0
        return self._magnet.on()

    def set_position(self, position: float) -> bool:
        position = max(0.0, min(1.0, position))
        self._position = position
        if position >= 0.5:
            return self._magnet.on()
        else:
            return self._magnet.off()

    def get_position(self) -> float:
        return self._position

    @property
    def is_proportional(self) -> bool:
        return False


class SuctionGripperAdapter(Gripper):
    """Wraps SuctionDriver as a Gripper — binary only (threshold at 0.5)."""

    def __init__(self, suction_driver):
        self._pump = suction_driver
        self._position = 0.0

    def open(self) -> bool:
        self._position = 0.0
        return self._pump.off()

    def close(self) -> bool:
        self._position = 1.0
        return self._pump.on()

    def set_position(self, position: float) -> bool:
        position = max(0.0, min(1.0, position))
        self._position = position
        if position >= 0.5:
            return self._pump.on()
        else:
            return self._pump.off()

    def get_position(self) -> float:
        return self._position

    @property
    def is_proportional(self) -> bool:
        return False


class ServoGripper(Gripper):
    """Servo-based gripper — maps position to servo angle range."""

    def __init__(self, port: str = None, min_angle: float = 0, max_angle: float = 180,
                 simulate: bool = True):
        self._port = port
        self._min_angle = min_angle
        self._max_angle = max_angle
        self._simulate = simulate
        self._position = 0.0
        self._serial = None

    def connect(self) -> bool:
        if self._simulate:
            return True
        try:
            import serial
            self._serial = serial.Serial(self._port, 115200, timeout=1)
            return True
        except Exception:
            return False

    def open(self) -> bool:
        return self.set_position(0.0)

    def close(self) -> bool:
        return self.set_position(1.0)

    def set_position(self, position: float) -> bool:
        self._position = max(0.0, min(1.0, position))
        angle = self._min_angle + self._position * (self._max_angle - self._min_angle)

        if self._simulate:
            return True

        if not self._serial or not self._serial.is_open:
            return False

        try:
            cmd = f"GRIP:{int(angle)}\n"
            self._serial.write(cmd.encode())
            self._serial.flush()
            return True
        except Exception:
            return False

    def get_position(self) -> float:
        return self._position

    @property
    def is_proportional(self) -> bool:
        return True


class ParallelGripper(Gripper):
    """Elephant Robotics parallel gripper (light) via pymycobot API.

    Uses set_gripper_value(value, speed) where value 0 = fully closed,
    100 = fully open. Supports personality-aware grip speeds through
    ActionOrigin integration.
    """

    def __init__(self, cobot=None, simulate: bool = True, personality=None):
        self._cobot = cobot
        self._simulate = simulate
        self._personality = personality
        self._position = 0.0       # 0.0 = fully open, 1.0 = fully closed (Gripper ABC convention)
        self._last_grip_value = 100  # pymycobot value: 100 = open

    def set_cobot(self, cobot) -> None:
        """Attach or replace the pymycobot instance."""
        self._cobot = cobot

    def _send(self, grip_value: int, speed: int) -> bool:
        """Send grip command to cobot or simulate."""
        grip_value = max(0, min(100, grip_value))
        speed = max(1, min(100, speed))
        self._last_grip_value = grip_value
        # Map pymycobot value (0=closed, 100=open) to Gripper position (0=open, 1=closed)
        self._position = 1.0 - (grip_value / 100.0)

        if self._simulate:
            logger.debug(f"[SIM] set_gripper_value({grip_value}, {speed})")
            return True

        if self._cobot is None:
            logger.warning("ParallelGripper: no cobot attached")
            return False

        try:
            self._cobot.set_gripper_value(grip_value, speed)
            time.sleep(0.05)  # brief settle
            return True
        except Exception as exc:
            logger.error(f"ParallelGripper send failed: {exc}")
            return False

    def _resolve_speed(self, base_speed: int, origin=None) -> int:
        """Apply personality-based speed modifier."""
        if origin is None or self._personality is None:
            return base_speed

        # Lazy import to avoid circular dependency
        from logic.personality import ActionOrigin

        if origin == ActionOrigin.OVERRIDE:
            return max(1, int(base_speed * 0.5))
        elif origin == ActionOrigin.SELF_INITIATED:
            return min(100, int(base_speed * 1.3))
        elif origin == ActionOrigin.CROWD_REQUESTED:
            return max(1, int(base_speed * 0.9))
        else:
            return base_speed

    def open(self) -> bool:
        """Fully open the gripper."""
        return self._send(100, 50)

    def close(self) -> bool:
        """Fully close the gripper."""
        return self._send(0, 50)

    def set_position(self, position: float) -> bool:
        """Set gripper position: 0.0 = fully open, 1.0 = fully closed.

        Maps to pymycobot value where 0 = closed, 100 = open (inverted).
        """
        position = max(0.0, min(1.0, position))
        grip_value = int((1.0 - position) * 100)
        return self._send(grip_value, 50)

    def grip_object(self, object_class: str, origin=None) -> bool:
        """Personality-aware grip using presets.

        Looks up the object_class in GRIP_PRESETS and applies personality-based
        speed modification based on the ActionOrigin.
        """
        preset = GRIP_PRESETS.get(object_class, GRIP_PRESETS["default"])
        speed = self._resolve_speed(preset.approach_speed, origin)
        logger.info(
            f"Gripping '{object_class}' — preset={preset.name}, "
            f"value={preset.grip_value}, speed={speed}"
        )
        ok = self._send(preset.grip_value, speed)
        if ok and preset.hold_verify_ms > 0:
            if not self._simulate:
                time.sleep(preset.hold_verify_ms / 1000.0)
        return ok

    def nudge(self) -> bool:
        """Push motion — close slightly then reopen.

        Used for the tea cup interaction: a gentle bump rather than a full grip.
        """
        logger.info("Nudge: close slightly then reopen")
        ok = self._send(60, 40)
        if ok:
            if not self._simulate:
                time.sleep(0.15)
            ok = self._send(100, 40)
        return ok

    def get_position(self) -> float:
        return self._position

    @property
    def is_proportional(self) -> bool:
        return True


def create_gripper(gripper_type: str = "suction", magnet_driver=None,
                   suction_driver=None, **kwargs) -> Gripper:
    """Factory for gripper creation based on config."""
    if gripper_type == "parallel":
        return ParallelGripper(**kwargs)
    elif gripper_type == "suction" and suction_driver is not None:
        return SuctionGripperAdapter(suction_driver)
    elif gripper_type == "magnet" and magnet_driver is not None:
        return MagnetGripperAdapter(magnet_driver)
    elif gripper_type == "servo":
        gripper = ServoGripper(**kwargs)
        gripper.connect()
        return gripper
    elif suction_driver is not None:
        return SuctionGripperAdapter(suction_driver)
    elif magnet_driver is not None:
        return MagnetGripperAdapter(magnet_driver)
    else:
        raise ValueError(f"Unknown gripper type: {gripper_type}")
