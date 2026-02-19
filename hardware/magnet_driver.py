import logging
import time
from typing import Optional
from enum import Enum

logger = logging.getLogger("MagnetDriver")

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class MagnetState(Enum):
    OFF = 0
    ON = 1


class MagnetDriver:
    def __init__(self, port: str = None, pin: int = 13, simulate: bool = False):
        if port is None:
            from .port_config import get_serial_port
            port = get_serial_port("magnet")
        self.port = port
        self.pin = pin
        self.simulate = simulate or not SERIAL_AVAILABLE
        self._serial: Optional[serial.Serial] = None
        self._state = MagnetState.OFF
        self._shared_serial = None
    
    @property
    def state(self) -> MagnetState:
        return self._state
    
    @property
    def is_on(self) -> bool:
        return self._state == MagnetState.ON
    
    def use_shared_serial(self, serial_connection: "serial.Serial") -> None:
        self._shared_serial = serial_connection
    
    def connect(self) -> bool:
        if self.simulate:
            return True
        
        if self._shared_serial:
            return True
        
        try:
            self._serial = serial.Serial(self.port, 115200, timeout=1)
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.warning(f"Connection failed: {e}")
            return False
    
    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None
    
    def toggle(self, on: bool) -> bool:
        target_state = MagnetState.ON if on else MagnetState.OFF
        
        if self.simulate:
            self._state = target_state
            return True
        
        serial_conn = self._shared_serial or self._serial
        if not serial_conn or not serial_conn.is_open:
            return False
        
        try:
            cmd = f"MAG:{1 if on else 0}\n"
            serial_conn.write(cmd.encode())
            serial_conn.flush()
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
    
    def __enter__(self) -> "MagnetDriver":
        self.connect()
        return self
    
    def __exit__(self, *args) -> None:
        self.off()
        self.disconnect()


def toggle_magnet(on: bool, driver: Optional[MagnetDriver] = None) -> bool:
    if driver:
        return driver.toggle(on)
    
    with MagnetDriver(simulate=True) as d:
        return d.toggle(on)
