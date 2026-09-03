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


async def pick_and_inspect(arm, gripper, calibration, pick_px: Tuple[int, int],
                           inspect_duration: float = 1.5,
                           config: Optional[PickPlaceConfig] = None) -> bool:
    """Pick up a small object, lift it to examine it inquisitively, and gently return it."""
    cfg = config or PickPlaceConfig()

    try:
        if gripper:
            gripper.open()
            await asyncio.sleep(cfg.release_delay)

        # 1. Move above pick position
        above = calibration.pixel_to_arm(pick_px[0], pick_px[1], cfg.z_safe)
        arm.move_to(above)
        await asyncio.sleep(cfg.move_delay)

        # 2. Lower to surface
        at_pick = calibration.pixel_to_arm(pick_px[0], pick_px[1], cfg.z_pick)
        arm.move_to(at_pick)
        await asyncio.sleep(cfg.move_delay)

        # 3. Grab
        if gripper:
            gripper.close()
            await asyncio.sleep(cfg.grab_delay)

        # 4. Lift up for inspection
        lift = calibration.pixel_to_arm(pick_px[0], pick_px[1], cfg.z_lift)
        arm.move_to(lift)
        await asyncio.sleep(cfg.move_delay)

        # 5. Inquisitive hold & head tilt
        tilted = (lift[0], lift[1], lift[2], lift[3] + 12.0)
        arm.move_to(tilted, speed=25)
        await asyncio.sleep(inspect_duration)

        # 6. Lower back to surface
        arm.move_to(at_pick, speed=30)
        await asyncio.sleep(cfg.move_delay)

        # 7. Release
        if gripper:
            gripper.open()
            await asyncio.sleep(cfg.release_delay)

        # 8. Retract
        arm.move_to(above, speed=40)
        await asyncio.sleep(cfg.move_delay)
        return True
    except Exception as e:
        logger.error(f"pick_and_inspect failed: {e}")
        if gripper:
            gripper.open()
        return False


async def nudge_object(arm, calibration, obj_px: Tuple[int, int],
                       nudge_dx: int = 25, nudge_dy: int = 0,
                       config: Optional[PickPlaceConfig] = None) -> bool:
    """Gently poke or nudge an object horizontally and retreat to observe."""
    cfg = config or PickPlaceConfig()

    try:
        # Move above start
        above = calibration.pixel_to_arm(obj_px[0] - nudge_dx, obj_px[1] - nudge_dy, cfg.z_safe)
        arm.move_to(above)
        await asyncio.sleep(cfg.move_delay)

        # Lower to contact height
        contact_start = calibration.pixel_to_arm(obj_px[0] - nudge_dx, obj_px[1] - nudge_dy, cfg.z_pick + 10.0)
        arm.move_to(contact_start, speed=30)
        await asyncio.sleep(cfg.move_delay)

        # Push / nudge forward
        contact_end = calibration.pixel_to_arm(obj_px[0] + nudge_dx, obj_px[1] + nudge_dy, cfg.z_pick + 10.0)
        arm.move_to(contact_end, speed=35)
        await asyncio.sleep(0.3)

        # Retract back and up to observe
        arm.move_to(above, speed=40)
        await asyncio.sleep(cfg.move_delay)
        return True
    except Exception as e:
        logger.error(f"nudge_object failed: {e}")
        return False


