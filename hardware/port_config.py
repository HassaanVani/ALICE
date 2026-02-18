import os
import sys
import glob
from typing import Optional


PLATFORM_DEFAULTS = {
    "darwin": {
        "arm": "/dev/tty.usbmodem*",
        "magnet": "/dev/tty.usbmodem*",
        "imu": "/dev/tty.usbmodem*",
    },
    "linux": {
        "arm": "/dev/ttyACM0",
        "magnet": "/dev/ttyACM0",
        "imu": "/dev/ttyACM1",
    },
    "win32": {
        "arm": "COM3",
        "magnet": "COM3",
        "imu": "COM4",
    },
}

ENV_VARS = {
    "arm": "ALICE_ARM_PORT",
    "magnet": "ALICE_MAGNET_PORT",
    "imu": "ALICE_IMU_PORT",
}


def get_serial_port(device: str) -> str:
    """Resolve a serial port for the given device.

    Checks environment variables first, then falls back to platform-appropriate
    defaults. For macOS glob patterns, returns the first matching port.
    """
    env_var = ENV_VARS.get(device)
    if env_var:
        env_val = os.environ.get(env_var)
        if env_val:
            return env_val

    platform = sys.platform
    defaults = PLATFORM_DEFAULTS.get(platform, PLATFORM_DEFAULTS["linux"])
    default_port = defaults.get(device, defaults.get("arm", "/dev/ttyACM0"))

    if "*" in default_port:
        matches = sorted(glob.glob(default_port))
        if matches:
            return matches[0]
        return default_port.replace("*", "0")

    return default_port


def list_serial_ports() -> list[str]:
    """List available serial ports on the system."""
    try:
        from serial.tools import list_ports
        return [p.device for p in list_ports.comports()]
    except ImportError:
        return []
