"""Force/compliance feedback — ABC + simulated + current-sensing stub."""

import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ForceReading:
    force_n: float
    contact_detected: bool
    timestamp: float


class ForceSensor(ABC):
    @abstractmethod
    def read(self) -> ForceReading:
        ...

    @abstractmethod
    def calibrate(self) -> None:
        ...

    @abstractmethod
    def set_threshold(self, newtons: float) -> None:
        ...


class SimulatedForceSensor(ForceSensor):
    """Calculates force from arm proximity to known object positions."""

    def __init__(self):
        self._threshold = 0.5  # Newtons
        self._object_positions: list[Tuple[float, float, float]] = []
        self._arm_position: Tuple[float, float, float] = (0, 0, 0)
        self._calibration_offset = 0.0

    def set_arm_position(self, x: float, y: float, z: float) -> None:
        self._arm_position = (x, y, z)

    def set_object_positions(self, positions: list[Tuple[float, float, float]]) -> None:
        self._object_positions = positions

    def read(self) -> ForceReading:
        force = self._compute_force()
        return ForceReading(
            force_n=force,
            contact_detected=force > self._threshold,
            timestamp=time.time()
        )

    def calibrate(self) -> None:
        self._calibration_offset = self._compute_force()

    def set_threshold(self, newtons: float) -> None:
        self._threshold = max(0.0, newtons)

    def _compute_force(self) -> float:
        if not self._object_positions:
            return 0.0

        ax, ay, az = self._arm_position
        min_dist = float("inf")
        for ox, oy, oz in self._object_positions:
            dist = math.sqrt((ax - ox) ** 2 + (ay - oy) ** 2 + (az - oz) ** 2)
            min_dist = min(min_dist, dist)

        # Inverse-square-ish force model: close = high force
        if min_dist < 5.0:
            force = max(0.0, 5.0 / (min_dist + 0.1) - self._calibration_offset)
        else:
            force = 0.0

        return force


class CurrentSensingForceSensor(ForceSensor):
    """Reads force from ADC via serial — stub implementation."""

    def __init__(self, port: str = None, baudrate: int = 115200):
        self._port = port
        self._baudrate = baudrate
        self._serial = None
        self._threshold = 0.5
        self._calibration_offset = 0.0

    def connect(self) -> bool:
        try:
            import serial
            self._serial = serial.Serial(self._port, self._baudrate, timeout=0.1)
            return True
        except Exception:
            return False

    def read(self) -> ForceReading:
        if not self._serial or not self._serial.is_open:
            return ForceReading(force_n=0.0, contact_detected=False, timestamp=time.time())
        try:
            self._serial.write(b"FORCE?\n")
            response = self._serial.readline().decode().strip()
            raw_value = float(response) if response else 0.0
            force = max(0.0, raw_value - self._calibration_offset)
            return ForceReading(
                force_n=force,
                contact_detected=force > self._threshold,
                timestamp=time.time()
            )
        except Exception:
            return ForceReading(force_n=0.0, contact_detected=False, timestamp=time.time())

    def calibrate(self) -> None:
        reading = self.read()
        self._calibration_offset = reading.force_n

    def set_threshold(self, newtons: float) -> None:
        self._threshold = max(0.0, newtons)
