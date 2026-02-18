"""Shared arm routines — pick-and-place, auto-scramble, auto-solve.

These are the physical primitives used by auto_sort, demo mode, and any future
mode that needs the arm to move blocks autonomously.
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from vision.aruco_detector import BlockData

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


def _random_position(bounds: Tuple[int, int, int, int],
                     existing: List[Tuple[int, int]],
                     min_spacing: int = 60) -> Tuple[int, int]:
    """Generate a random (x, y) within bounds that doesn't overlap existing positions."""
    x_min, y_min, w, h = bounds
    for _ in range(100):
        x = random.randint(x_min + 30, x_min + w - 30)
        y = random.randint(y_min + 30, y_min + h - 30)
        if all(abs(x - ex) > min_spacing or abs(y - ey) > min_spacing
               for ex, ey in existing):
            return (x, y)
    # Fallback — just return something
    return (x_min + w // 2, y_min + h // 2)


async def auto_scramble(arm, gripper, calibration, detector, camera_getter,
                        workspace_bounds: Tuple[int, int, int, int] = (100, 50, 600, 250),
                        config: Optional[PickPlaceConfig] = None,
                        running_check=None) -> int:
    """Detect all blocks via ArUco, then pick each and place at a random position.

    Args:
        camera_getter: callable returning a camera frame (numpy array)
        workspace_bounds: (x, y, width, height) for random placement area
        running_check: callable returning False to abort early

    Returns:
        Number of blocks scrambled.
    """
    frame = camera_getter()
    if frame is None:
        logger.warning("No camera frame for scramble")
        return 0

    blocks = detector.detect_blocks(frame)
    if not blocks:
        logger.warning("No blocks detected for scramble")
        return 0

    logger.info(f"Scrambling {len(blocks)} blocks")
    placed: List[Tuple[int, int]] = []
    count = 0

    for block in blocks:
        if running_check and not running_check():
            break

        target = _random_position(workspace_bounds, placed)
        placed.append(target)

        success = await pick_and_place(
            arm, gripper, calibration,
            pick_px=(block.center_x, block.center_y),
            place_px=target,
            config=config,
        )
        if success:
            count += 1
            logger.debug(f"Scrambled block {block.block_id} to {target}")

    logger.info(f"Scramble complete: {count}/{len(blocks)} blocks moved")
    return count


async def auto_solve(arm, gripper, calibration, detector, camera_getter,
                     sort_fsm, config: Optional[PickPlaceConfig] = None,
                     running_check=None) -> int:
    """Iteratively solve: re-detect blocks, pick current position, place at sorted position.

    Uses sort_fsm.get_optimal_next_target() each cycle.

    Returns:
        Number of moves executed.
    """
    moves = 0

    while True:
        if running_check and not running_check():
            break

        # Re-detect blocks each cycle
        frame = camera_getter()
        if frame is None:
            await asyncio.sleep(0.05)
            continue

        blocks = detector.detect_blocks(frame)
        sort_fsm.update(blocks)

        from logic.sort_logic import SortState
        if sort_fsm.state == SortState.COMPLETE:
            logger.info(f"Auto-solve complete in {moves} moves")
            break

        target = sort_fsm.get_optimal_next_target()
        if target is None:
            # All blocks in position or none detected
            logger.info("No more targets — solve done")
            break

        block_id, (tx, ty) = target

        # Find current position of this block
        current_pos = None
        for b in blocks:
            if b.block_id == block_id:
                current_pos = (b.center_x, b.center_y)
                break

        if current_pos is None:
            await asyncio.sleep(0.05)
            continue

        success = await pick_and_place(
            arm, gripper, calibration,
            pick_px=current_pos,
            place_px=(tx, ty),
            config=config,
        )
        if success:
            moves += 1
            logger.debug(f"Solved block {block_id}: {current_pos} -> ({tx}, {ty})")

        await asyncio.sleep(0.05)

    return moves
