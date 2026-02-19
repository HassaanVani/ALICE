import asyncio
import logging
import threading
import time
import math
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("ArmController")

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class ArmState(Enum):
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    MOVING = "moving"
    ERROR = "error"


@dataclass
class ArmPosition:
    base: float = 90.0
    shoulder: float = 90.0
    elbow: float = 90.0
    wrist_pitch: float = 90.0
    wrist_roll: float = 90.0
    
    def as_tuple(self) -> Tuple[float, ...]:
        return (self.base, self.shoulder, self.elbow, self.wrist_pitch, self.wrist_roll)
    
    @classmethod
    def from_tuple(cls, angles: Tuple[float, ...]) -> "ArmPosition":
        return cls(*angles[:5])


class ArmController:
    AXIS_COUNT = 5
    ANGLE_MIN = 0.0
    ANGLE_MAX = 180.0
    HOME_POSITION = ArmPosition(90, 90, 90, 90, 90)
    
    MAX_RECONNECT_ATTEMPTS = 5
    RECONNECT_BASE_DELAY = 0.5

    def __init__(self, port: str = None, baudrate: int = 115200, simulate: bool = False,
                 serial_lock: Optional[threading.Lock] = None):
        if port is None:
            from .port_config import get_serial_port
            port = get_serial_port("arm")
        self.port = port
        self.baudrate = baudrate
        self.simulate = simulate or not SERIAL_AVAILABLE
        self._serial: Optional[serial.Serial] = None
        self._serial_lock = serial_lock or threading.Lock()
        self._state = ArmState.DISCONNECTED
        self._current_position = ArmPosition()
        self._target_position = ArmPosition()
        self._reconnect_attempts = 0
    
    @property
    def state(self) -> ArmState:
        return self._state
    
    @property
    def position(self) -> ArmPosition:
        return self._current_position
    
    @property
    def is_connected(self) -> bool:
        return self._state != ArmState.DISCONNECTED
    
    def connect(self) -> bool:
        if self.simulate:
            self._state = ArmState.IDLE
            self._current_position = ArmPosition()
            return True

        try:
            if self._serial and self._serial.is_open:
                self._serial.close()
            self._serial = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino reset
            self._state = ArmState.IDLE
            self._current_position = ArmPosition()
            self._reconnect_attempts = 0
            logger.info(f"Connected on {self.port}")
            return True
        except serial.SerialException as e:
            self._state = ArmState.ERROR
            logger.error(f"Connection failed: {e}")
            return False

    def reconnect(self) -> bool:
        if self.simulate:
            return True
        if self._reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
            logger.error(f"Reconnect failed after {self.MAX_RECONNECT_ATTEMPTS} attempts")
            return False

        self._reconnect_attempts += 1
        delay = self.RECONNECT_BASE_DELAY * (2 ** (self._reconnect_attempts - 1))
        logger.info(f"Reconnect attempt {self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS} in {delay:.1f}s")
        time.sleep(delay)
        return self.connect()
    
    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None
        self._state = ArmState.DISCONNECTED
    
    def home(self) -> bool:
        return self.move_to(self.HOME_POSITION.as_tuple())
    
    def move_to(self, angles: Tuple[float, ...], speed: float = 1.0) -> bool:
        if self._state == ArmState.DISCONNECTED:
            return False
        
        if len(angles) != self.AXIS_COUNT:
            raise ValueError(f"Expected {self.AXIS_COUNT} angles, got {len(angles)}")
        
        clamped = tuple(
            max(self.ANGLE_MIN, min(self.ANGLE_MAX, a)) for a in angles
        )
        self._target_position = ArmPosition.from_tuple(clamped)
        self._state = ArmState.MOVING
        
        if self.simulate:
            self._simulate_movement(speed)
        else:
            self._send_command(clamped)
        
        self._current_position = self._target_position
        self._state = ArmState.IDLE
        return True
    
    async def move_to_async(self, angles: Tuple[float, ...], speed: float = 1.0) -> bool:
        if self._state == ArmState.DISCONNECTED:
            return False

        if len(angles) != self.AXIS_COUNT:
            raise ValueError(f"Expected {self.AXIS_COUNT} angles, got {len(angles)}")

        clamped = tuple(
            max(self.ANGLE_MIN, min(self.ANGLE_MAX, a)) for a in angles
        )
        self._target_position = ArmPosition.from_tuple(clamped)
        self._state = ArmState.MOVING

        if self.simulate:
            self._current_position = self._target_position
        else:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._send_command, clamped)

        self._current_position = self._target_position
        self._state = ArmState.IDLE
        return True

    def move_axis(self, axis: int, angle: float) -> bool:
        if axis < 0 or axis >= self.AXIS_COUNT:
            raise ValueError(f"Invalid axis: {axis}")

        current = list(self._current_position.as_tuple())
        current[axis] = angle
        return self.move_to(tuple(current))

    def _simulate_movement(self, speed: float) -> None:
        steps = int(20 / speed)
        delay = 0.01

        start = self._current_position.as_tuple()
        end = self._target_position.as_tuple()

        for i in range(steps):
            t = (i + 1) / steps
            t = t * t * (3 - 2 * t)  # Smoothstep
            interpolated = tuple(s + (e - s) * t for s, e in zip(start, end))
            self._current_position = ArmPosition.from_tuple(interpolated)
            time.sleep(delay)

    def _send_command(self, angles: Tuple[float, ...]) -> None:
        with self._serial_lock:
            if not self._serial or not self._serial.is_open:
                if not self.reconnect():
                    return

            cmd = ",".join(f"{int(a)}" for a in angles) + "\n"
            try:
                self._serial.write(cmd.encode())
                self._serial.flush()

                response = self._serial.readline().decode().strip()
                if response != "OK":
                    logger.warning(f"Unexpected response: {response}")
            except serial.SerialException as e:
                logger.error(f"Serial write failed: {e}")
                self._state = ArmState.ERROR
                self.reconnect()
    
    def set_compliant(self, enabled: bool) -> None:
        """Put arm into compliant (torque-off) mode for kinesthetic teaching."""
        if self.simulate:
            logger.info(f"Compliance {'enabled' if enabled else 'disabled'} (simulated)")
            return

        with self._serial_lock:
            if not self._serial or not self._serial.is_open:
                return

            try:
                cmd = f"TORQUE:{'0' if enabled else '1'}\n"
                self._serial.write(cmd.encode())
                self._serial.flush()
                logger.info(f"Compliance {'enabled' if enabled else 'disabled'}")
            except Exception as e:
                logger.error(f"Failed to set compliance: {e}")

    def __enter__(self) -> "ArmController":
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.disconnect()
