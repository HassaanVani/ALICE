"""Shared loops used by auto_sort and demo modes."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from vision import CameraRole
from logic import SortState

if TYPE_CHECKING:
    from logic import SortingSession
    from ._base import ModeContext

logger = logging.getLogger("ALICE")


async def sort_loop(ctx: ModeContext) -> Optional[SortingSession]:
    """Detection/tracking/state loop for human benchmark and cyborg phases."""
    while ctx.running():
        frame = ctx.cameras.get_frame(CameraRole.OVERHEAD)
        if frame is None:
            await asyncio.sleep(ctx.config.timing.camera_poll_s)
            continue

        blocks = ctx.detector.detect_blocks(frame)

        # Update tracker
        tracked = ctx.tracker.update(blocks)
        for t in tracked:
            for b in blocks:
                if b.block_id == t.block_id:
                    b.track_id = t.track_id

        ctx.sort_fsm.update(blocks)

        # Record
        if ctx.recorder.is_recording:
            ctx.recorder.record_blocks([b.as_dict() for b in blocks])
            ctx.recorder.record_motor(ctx.arm.position.as_tuple(), ctx.gripper.get_position())

        # Update state
        ctx.state_manager.update_blocks([b.as_dict() for b in blocks])
        ctx.state_manager.update_arm(ctx.arm.position.as_tuple(), ctx.arm.state.value)
        if ctx.sort_fsm.session:
            ctx.state_manager.update_sort_progress(
                move_count=ctx.sort_fsm.session.move_count,
                start_time=ctx.sort_fsm.session.start_time,
            )

        if ctx.sort_fsm.state == SortState.COMPLETE:
            logger.info(f"Sorting complete! Duration: {ctx.sort_fsm.session.duration:.2f}s")
            return ctx.sort_fsm.session

        if ctx.sort_fsm.state == SortState.CYBORG_COOP:
            # Consume audience block votes
            audience_vote = None
            winner_info = ctx.audience_server.consume_votes()
            if winner_info:
                audience_vote = winner_info["block_id"]
                await ctx.audience_server.broadcast_winner(winner_info)

            target = ctx.sort_fsm.get_next_robot_target(
                rl_agent=ctx.rl_agent,
                audience_vote=audience_vote,
            )
            if target:
                block_id, (tx, ty) = target
                await ctx.audience_server.broadcast_action("pick", {
                    "block_id": block_id, "target_x": tx, "target_y": ty,
                })
                angles = ctx.calibration.pixel_to_arm(tx, ty)
                ctx.arm.move_to(angles)
                try:
                    ctx.gripper.close()
                except Exception as e:
                    logger.error(f"Gripper close failed: {e}")
                await asyncio.sleep(0.3)
                try:
                    ctx.gripper.open()
                except Exception as e:
                    logger.error(f"Gripper open failed: {e}")

        await asyncio.sleep(ctx.config.timing.sort_loop_s)
    return ctx.sort_fsm.session


async def rebellion_loop(ctx: ModeContext) -> None:
    """Act 5: Robot sorts optimally, deliberately ignoring audience votes."""
    while ctx.running():
        frame = ctx.cameras.get_frame(CameraRole.OVERHEAD)
        if frame is None:
            await asyncio.sleep(ctx.config.timing.camera_poll_s)
            continue

        blocks = ctx.detector.detect_blocks(frame)
        tracked = ctx.tracker.update(blocks)
        for t in tracked:
            for b in blocks:
                if b.block_id == t.block_id:
                    b.track_id = t.track_id

        ctx.sort_fsm.update(blocks)

        # Update state
        ctx.state_manager.update_blocks([b.as_dict() for b in blocks])
        ctx.state_manager.update_arm(ctx.arm.position.as_tuple(), ctx.arm.state.value)
        if ctx.sort_fsm.session:
            ctx.state_manager.update_sort_progress(
                move_count=ctx.sort_fsm.session.move_count,
                start_time=ctx.sort_fsm.session.start_time,
            )

        if ctx.sort_fsm.state == SortState.COMPLETE:
            logger.info(f"Rebellion complete! {ctx.sort_fsm.session.duration:.2f}s")
            return

        # Consume audience votes — we hear them, we just don't obey
        crowd_winner = ctx.audience_server.consume_votes()
        crowd_choice = crowd_winner["block_id"] if crowd_winner else None
        crowd_votes = crowd_winner["voter_count"] if crowd_winner else 0

        # Robot computes its own optimal move
        optimal = ctx.sort_fsm.get_optimal_next_target()
        if optimal:
            robot_choice, (tx, ty) = optimal

            # Update state for narration
            ctx.state_manager.update_rebellion(crowd_choice, robot_choice)

            # Tell the audience: you said X, I chose Y
            if crowd_choice is not None and crowd_choice != robot_choice:
                await ctx.audience_server.broadcast_override(
                    crowd_choice=crowd_choice,
                    robot_choice=robot_choice,
                    crowd_votes=crowd_votes,
                    reason="optimal",
                )
            elif crowd_choice is not None:
                # Crowd agreed with robot — acknowledge it
                await ctx.audience_server.broadcast_override(
                    crowd_choice=crowd_choice,
                    robot_choice=robot_choice,
                    crowd_votes=crowd_votes,
                    reason="agreed",
                )

            await ctx.audience_server.broadcast_action("pick", {
                "block_id": robot_choice, "target_x": tx, "target_y": ty,
            })
            angles = ctx.calibration.pixel_to_arm(tx, ty)
            ctx.arm.move_to(angles)
            try:
                ctx.gripper.close()
            except Exception as e:
                logger.error(f"Gripper close failed: {e}")
            await asyncio.sleep(0.3)
            try:
                ctx.gripper.open()
            except Exception as e:
                logger.error(f"Gripper open failed: {e}")

        await asyncio.sleep(ctx.config.timing.sort_loop_s)
