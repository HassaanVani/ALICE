"""Shared arm routines — pick-and-place primitive.

Used by object interaction for fetch, hand_over, move_near, throw_away.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger("ArmRoutines")


@dataclass
class PickPlaceConfig:
    """Heights and timing for pick-and-place operations."""
    z_safe: float = 70.0      # clearance height (above obstacles)
    z_pick: float = 0.0       # table surface
    z_lift: float = 50.0      # post-grab lift height
    grab_delay: float = 0.15  # seconds to wait after grab
    release_delay: float = 0.1
    move_delay: float = 0.2   # settle time after moving


async def pick_and_place(arm, gripper, calibration, pick_px: Tuple[int, int],
                         place_px: Tuple[int, int],
                         config: Optional[PickPlaceConfig] = None) -> bool:
    """Move the arm to pick a block at pick_px and place it at place_px.

    Uses calibration.pixel_to_arm(px, py, z) for IK at varying heights.
    Returns True on success.
    """
    cfg = config or PickPlaceConfig()

    try:
        # 1. Move above pick position at safe height
        above_pick = calibration.pixel_to_arm(pick_px[0], pick_px[1], cfg.z_safe)
        arm.move_to(above_pick)
        await asyncio.sleep(cfg.move_delay)

        # 2. Lower to pick height
        at_pick = calibration.pixel_to_arm(pick_px[0], pick_px[1], cfg.z_pick)
        arm.move_to(at_pick)
        await asyncio.sleep(cfg.move_delay)

        # 3. Grab
        gripper.close()
        await asyncio.sleep(cfg.grab_delay)

        # 4. Lift to post-grab height
        lift = calibration.pixel_to_arm(pick_px[0], pick_px[1], cfg.z_lift)
        arm.move_to(lift)
        await asyncio.sleep(cfg.move_delay)

        # 5. Move above place position at safe height
        above_place = calibration.pixel_to_arm(place_px[0], place_px[1], cfg.z_safe)
        arm.move_to(above_place)
        await asyncio.sleep(cfg.move_delay)

        # 6. Lower to place height
        at_place = calibration.pixel_to_arm(place_px[0], place_px[1], cfg.z_pick)
        arm.move_to(at_place)
        await asyncio.sleep(cfg.move_delay)

        # 7. Release
        gripper.open()
        await asyncio.sleep(cfg.release_delay)

        # 8. Retract to safe height
        retract = calibration.pixel_to_arm(place_px[0], place_px[1], cfg.z_safe)
        arm.move_to(retract)
        await asyncio.sleep(cfg.move_delay)

        return True

    except Exception as e:
        logger.error(f"Pick-and-place failed: {e}")
        gripper.open()
        return False


