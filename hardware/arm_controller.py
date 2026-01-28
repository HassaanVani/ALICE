import time
import math
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum

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
    
    def __init__(self, port: str = "COM3", baudrate: int = 115200, simulate: bool = False):
        self.port = port
        self.baudrate = baudrate
        self.simulate = simulate or not SERIAL_AVAILABLE
        self._serial: Optional[serial.Serial] = None
        self._state = ArmState.DISCONNECTED
        self._current_position = ArmPosition()
        self._target_position = ArmPosition()
    
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
            self._serial = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino reset
            self._state = ArmState.IDLE
            self._current_position = ArmPosition()
            return True
        except Exception as e:
            self._state = ArmState.ERROR
            print(f"[ArmController] Connection failed: {e}")
            return False
    
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
        if not self._serial or not self._serial.is_open:
            return
        
        cmd = ",".join(f"{int(a)}" for a in angles) + "\n"
        self._serial.write(cmd.encode())
        self._serial.flush()
        
        response = self._serial.readline().decode().strip()
        if response != "OK":
            print(f"[ArmController] Unexpected response: {response}")
    
    def __enter__(self) -> "ArmController":
        self.connect()
        return self
    
    def __exit__(self, *args) -> None:
        self.disconnect()
