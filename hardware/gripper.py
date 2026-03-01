"""Gripper abstraction — ABC + MagnetGripperAdapter + ServoGripper stub."""

from abc import ABC, abstractmethod
from typing import Optional


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


def create_gripper(gripper_type: str = "suction", magnet_driver=None,
                   suction_driver=None, **kwargs) -> Gripper:
    """Factory for gripper creation based on config."""
    if gripper_type == "suction" and suction_driver is not None:
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
