"""Suction pump driver for MyPalletizer 260 M5Stack — GPIO-based via pymycobot."""

import logging
import threading
import time
from typing import Optional
from enum import Enum

logger = logging.getLogger("SuctionDriver")

try:
    from pymycobot import MyPalletizer260
    PYMYCOBOT_AVAILABLE = True
except ImportError:
    PYMYCOBOT_AVAILABLE = False


class PumpState(Enum):
    OFF = 0
    ON = 1


class SuctionDriver:
    """Controls the suction pump on the MyPalletizer 260 M5Stack.

    The pump is wired to the M5Stack basic output pin (default pin 5).
    Active-low: signal 0 = pump ON, signal 1 = pump OFF.
    """

    def __init__(self, port: str = None, pin: int = 5, simulate: bool = False,
                 serial_lock: Optional[threading.Lock] = None):
        if port is None:
            from .port_config import get_serial_port
            port = get_serial_port("arm")
        self.port = port
        self.pin = pin
        self.simulate = simulate or not PYMYCOBOT_AVAILABLE
        self._mc: Optional["MyPalletizer260"] = None
        self._serial_lock = serial_lock or threading.Lock()
        self._state = PumpState.OFF
        self._shared_cobot = False

    @property
    def state(self) -> PumpState:
        return self._state

    @property
    def is_on(self) -> bool:
        return self._state == PumpState.ON

    def use_shared_cobot(self, mc: "MyPalletizer260",
                         lock: Optional[threading.Lock] = None) -> None:
        """Share the MyPalletizer260 instance from ArmController."""
        self._mc = mc
        self._shared_cobot = True
        if lock is not None:
            self._serial_lock = lock

    def connect(self) -> bool:
        if self.simulate:
            return True

        if self._mc is not None:
            return True

        try:
            self._mc = MyPalletizer260(self.port, 115200)
            return True
        except Exception as e:
            logger.warning(f"Connection failed: {e}")
            return False

    def disconnect(self) -> None:
        if not self._shared_cobot and self._mc is not None:
            try:
                self._mc.close() if hasattr(self._mc, 'close') else None
            except Exception:
                pass
        self._mc = None

    def toggle(self, on: bool) -> bool:
        target_state = PumpState.ON if on else PumpState.OFF

        if self.simulate:
            self._state = target_state
            return True

        with self._serial_lock:
            if self._mc is None:
                return False

            try:
                # Active-low: 0 = pump ON, 1 = pump OFF
                signal = 0 if on else 1
                self._mc.set_basic_output(self.pin, signal)
                self._state = target_state
                return True
            except Exception as e:
                logger.error(f"Toggle failed: {e}")
                return False

    def on(self) -> bool:
        return self.toggle(True)

    def off(self) -> bool:
        return self.toggle(False)

    def pulse(self, duration_ms: int = 100) -> bool:
        if not self.on():
            return False
        time.sleep(duration_ms / 1000)
        return self.off()

    def __enter__(self) -> "SuctionDriver":
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.off()
        self.disconnect()


def toggle_suction(on: bool, driver: Optional[SuctionDriver] = None) -> bool:
    if driver:
        return driver.toggle(on)

    with SuctionDriver(simulate=True) as d:
        return d.toggle(on)
