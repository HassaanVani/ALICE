import logging
import threading
import time
import math
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("ArmController")

try:
    from pymycobot import MyPalletizer260
    PYMYCOBOT_AVAILABLE = True
except ImportError:
    PYMYCOBOT_AVAILABLE = False


class ArmState(Enum):
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    MOVING = "moving"
    ERROR = "error"


@dataclass
class ArmPosition:
    j1: float = 0.0   # base rotation
    j2: float = 0.0   # shoulder
    j3: float = 0.0   # elbow
    j4: float = 0.0   # wrist rotation

    def as_tuple(self) -> Tuple[float, ...]:
        return (self.j1, self.j2, self.j3, self.j4)

    @classmethod
    def from_tuple(cls, angles: Tuple[float, ...]) -> "ArmPosition":
        return cls(*angles[:4])


class ArmController:
    AXIS_COUNT = 4
    JOINT_LIMITS = ((-162, 162), (-2, 90), (-92, 60), (-180, 180))
    HOME_POSITION = ArmPosition(-33, -2, -72, 43)  # "looking at user" — calibrated

    MAX_RECONNECT_ATTEMPTS = 5
    RECONNECT_BASE_DELAY = 0.5

    def __init__(self, port: str = None, baudrate: int = 115200, simulate: bool = False,
                 serial_lock: Optional[threading.Lock] = None,
                 wifi_ip: Optional[str] = None, wifi_port: int = 9000):
        if port is None:
            from .port_config import get_serial_port
            port = get_serial_port("arm")
        self.port = port
        self.baudrate = baudrate
        self.simulate = simulate or not PYMYCOBOT_AVAILABLE
        self._mc: Optional["MyPalletizer260"] = None
        self._serial_lock = serial_lock or threading.Lock()
        self._state = ArmState.DISCONNECTED
        self._current_position = ArmPosition()
        self._target_position = ArmPosition()
        self._reconnect_attempts = 0
        self._wifi_ip = wifi_ip
        self._wifi_port = wifi_port
        self._connection_type: Optional[str] = None  # "serial" or "wifi"

    @property
    def state(self) -> ArmState:
        return self._state

    @property
    def position(self) -> ArmPosition:
        if not self.simulate and self._mc is not None and self._state != ArmState.DISCONNECTED:
            try:
                angles = self._mc.get_angles()
                if angles and len(angles) >= self.AXIS_COUNT:
                    self._current_position = ArmPosition.from_tuple(tuple(angles))
            except Exception:
                pass
        return self._current_position

    @property
    def is_connected(self) -> bool:
        return self._state != ArmState.DISCONNECTED

    @property
    def cobot(self) -> Optional["MyPalletizer260"]:
        """Expose the underlying MyPalletizer260 instance for shared use (e.g. suction pump)."""
        return self._mc

    def connect(self) -> bool:
        if self.simulate:
            self._state = ArmState.IDLE
            self._current_position = ArmPosition()
            return True

        # Try serial first (support /dev/tty and /dev/cu on macOS)
        ports_to_try = [self.port] if self.port else []
        if self.port and self.port.startswith("/dev/tty."):
            ports_to_try.append(self.port.replace("/dev/tty.", "/dev/cu."))
        elif self.port and self.port.startswith("/dev/cu."):
            ports_to_try.append(self.port.replace("/dev/cu.", "/dev/tty."))

        for p in ports_to_try:
            try:
                self._mc = MyPalletizer260(p, self.baudrate)
                time.sleep(1.5)
                # Verify the connection actually works (M5Stack boot/sync retry)
                angles = None
                for _ in range(4):
                    angles = self._mc.get_angles()
                    if angles and angles != -1 and isinstance(angles, list) and len(angles) >= 4:
                        break
                    time.sleep(0.4)

                if angles and angles != -1 and isinstance(angles, list) and len(angles) >= 4:
                    self._state = ArmState.IDLE
                    self._current_position = ArmPosition.from_tuple(tuple(angles[:4]))
                    self._reconnect_attempts = 0
                    self._connection_type = "serial"
                    self.port = p
                    logger.info(f"Connected via serial on {p} (angles={angles[:4]})")
                    return True
                else:
                    logger.warning(f"Serial port {p} opened but arm not responding")
                    try:
                        self._mc.close() if hasattr(self._mc, 'close') else None
                    except Exception:
                        pass
                    self._mc = None
            except Exception as e:
                logger.warning(f"Serial connection on {p} failed: {e}")
                self._mc = None

        # Fall back to WiFi if configured
        if self._wifi_ip:
            try:
                from pymycobot.mypalletizersocket import MyPalletizerSocket
                self._mc = MyPalletizerSocket(self._wifi_ip, self._wifi_port)
                time.sleep(1)
                angles = self._mc.get_angles()
                if angles != -1 and angles is not None:
                    self._state = ArmState.IDLE
                    self._current_position = ArmPosition()
                    self._reconnect_attempts = 0
                    self._connection_type = "wifi"
                    logger.info(f"Connected via WiFi on {self._wifi_ip}:{self._wifi_port}")
                    return True
                else:
                    logger.warning("WiFi socket opened but arm not responding")
                    self._mc = None
            except Exception as e:
                logger.warning(f"WiFi connection failed: {e}")
                self._mc = None

        self._state = ArmState.ERROR
        logger.error("All connection methods failed")
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
        if self._mc is not None:
            try:
                self._mc.close() if hasattr(self._mc, 'close') else None
            except Exception:
                pass
        self._mc = None
        self._state = ArmState.DISCONNECTED

    def home(self) -> bool:
        return self.move_to(self.HOME_POSITION.as_tuple())

    def _clamp_angles(self, angles: Tuple[float, ...]) -> Tuple[float, ...]:
        """Clamp each joint angle to its per-joint limits."""
        clamped = []
        for i, a in enumerate(angles):
            lo, hi = self.JOINT_LIMITS[i]
            clamped.append(max(lo, min(hi, a)))
        return tuple(clamped)

    def move_to(self, angles: Tuple[float, ...], speed: float = 50) -> bool:
        if self._state == ArmState.DISCONNECTED:
            return False

        if len(angles) != self.AXIS_COUNT:
            raise ValueError(f"Expected {self.AXIS_COUNT} angles, got {len(angles)}")

        clamped = self._clamp_angles(angles)
        self._target_position = ArmPosition.from_tuple(clamped)
        self._state = ArmState.MOVING

        if self.simulate:
            self._simulate_movement(speed)
        else:
            self._send_angles(clamped, speed)

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
        steps = max(1, int(20 / max(speed / 50, 0.1)))
        delay = 0.01

        start = self._current_position.as_tuple()
        end = self._target_position.as_tuple()

        for i in range(steps):
            t = (i + 1) / steps
            t = t * t * (3 - 2 * t)  # Smoothstep
            interpolated = tuple(s + (e - s) * t for s, e in zip(start, end))
            self._current_position = ArmPosition.from_tuple(interpolated)
            time.sleep(delay)

    def _send_angles(self, angles: Tuple[float, ...], speed: float) -> None:
        with self._serial_lock:
            if self._mc is None:
                if not self.reconnect():
                    return

            try:
                # speed for pymycobot: 0-100
                sp = max(0, min(100, int(speed)))
                self._mc.send_angles(list(angles), sp)
            except Exception as e:
                logger.error(f"send_angles failed: {e}")
                self._state = ArmState.ERROR
                self.reconnect()

    def set_compliant(self, enabled: bool) -> None:
        """Put arm into compliant (torque-off) mode for kinesthetic teaching."""
        if self.simulate:
            logger.info(f"Compliance {'enabled' if enabled else 'disabled'} (simulated)")
            return

        with self._serial_lock:
            if self._mc is None:
                return

            try:
                if enabled:
                    self._mc.release_all_servos()
                else:
                    self._mc.power_on()
                logger.info(f"Compliance {'enabled' if enabled else 'disabled'}")
            except Exception as e:
                logger.error(f"Failed to set compliance: {e}")

    def __enter__(self) -> "ArmController":
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.disconnect()
