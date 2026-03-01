"""Backward compatibility — re-exports SuctionDriver as MagnetDriver.

The physical electromagnet has been replaced by a suction pump on the
MyPalletizer 260 M5Stack.  All existing imports of MagnetDriver, MagnetState,
and toggle_magnet continue to work unchanged.
"""

from .suction_driver import SuctionDriver as MagnetDriver, PumpState as MagnetState, toggle_suction as toggle_magnet

__all__ = ["MagnetDriver", "MagnetState", "toggle_magnet"]
