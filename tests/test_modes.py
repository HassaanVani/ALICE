"""Tests for all mode runners in modes/ — IdleRunner, AutoSortRunner, AutoTetrisRunner, PuppeteerRunner, DemoRunner."""

import asyncio
from unittest.mock import MagicMock, AsyncMock, PropertyMock, patch
from dataclasses import dataclass

import pytest

from modes._base import ModeContext, DemoState


def mock_context(*, running_calls=1):
    """Build a ModeContext with all mocked deps."""
    ctx = MagicMock()

    call_count = 0

    def running():
        nonlocal call_count
        call_count += 1
        return call_count <= running_calls

    ctx.running = running

    # Config
    ctx.config.timing.idle_loop_s = 0.0
    ctx.config.timing.sort_loop_s = 0.0
    ctx.config.timing.camera_poll_s = 0.0
    ctx.config.tetris_screen.board_left = 0
    ctx.config.tetris_screen.board_top = 0
    ctx.config.tetris_screen.board_width = 300
    ctx.config.tetris_screen.board_height = 600
    ctx.config.tetris_screen.key_calibration_path = "tetris_key_calibration.json"

    # Camera
    import numpy as np
    ctx.cameras.get_frame = MagicMock(return_value=np.zeros((64, 64, 3), dtype=np.uint8))

    # Inference
    ctx.inference.is_frozen = False
    ctx.inference.predict = MagicMock()

    # Arm
    pos = MagicMock()
    pos.as_tuple = MagicMock(return_value=(0.0, 0.0, 0.0, 0.0))
    type(ctx.arm).position = PropertyMock(return_value=pos)
    type(ctx.arm).state = PropertyMock(return_value=MagicMock(value="idle"))
    ctx.arm.move_to = MagicMock()

    # Gripper
    ctx.gripper.open = MagicMock()
    ctx.gripper.close = MagicMock()
    ctx.gripper.get_position = MagicMock(return_value=0.0)

    # Sort FSM
    ctx.sort_fsm = MagicMock()
    ctx.sort_fsm.state = MagicMock()
    ctx.sort_fsm.session = None

    # State manager
    ctx.state_manager = MagicMock()

    # Detector / tracker
    ctx.detector.detect_blocks = MagicMock(return_value=[])
    ctx.tracker.update = MagicMock(return_value=[])

    # Calibration
    ctx.calibration.pixel_to_arm = MagicMock(return_value=(0.0, 0.0, 0.0, 0.0))

    # Recorder
    ctx.recorder.is_recording = False

    # Audience
    ctx.audience_server = MagicMock()
    ctx.audience_server.consume_votes = MagicMock(return_value=None)
    ctx.audience_server.broadcast_winner = AsyncMock()
    ctx.audience_server.broadcast_action = AsyncMock()
    ctx.audience_server.broadcast_override = AsyncMock()

    # Puppet server
    ctx.puppet_server = MagicMock()

    # Narration
    ctx.narration = MagicMock()

    # WS server
    ctx.ws_server = MagicMock()

    # Tetris
    ctx.tetris = MagicMock()

    # Kinesthetic
    ctx.kinesthetic = MagicMock()

    # RL agent
    ctx.rl_agent = None

    # Living behaviors — disabled in tests (must be None, not MagicMock)
    ctx.gaze_tracker = None
    ctx.curiosity_engine = None
    ctx.habit_engine = None
    ctx.body_language = None
    ctx.sound_effects = None
    ctx.proactive = None
    ctx.object_memory = None
    ctx.presence_detector = None
    ctx.llm_interpreter = None

    return ctx


# ── IdleRunner ─────────────────────────────────────────────────

class TestIdleRunner:
    @pytest.mark.asyncio
    async def test_idle_runs_inference(self):
        from modes.idle import IdleRunner
        ctx = mock_context(running_calls=2)
        runner = IdleRunner(ctx)
        await runner.run()
        ctx.inference.predict.assert_called()

    @pytest.mark.asyncio
    async def test_idle_exits_on_not_running(self):
        from modes.idle import IdleRunner
        ctx = mock_context(running_calls=0)
        runner = IdleRunner(ctx)
        await runner.run()
        # Should exit immediately
        ctx.inference.predict.assert_not_called()


# ── AutoSortRunner ─────────────────────────────────────────────

class TestAutoSortRunner:
    @pytest.mark.asyncio
    async def test_auto_sort_calls_scramble_then_solve(self):
        from modes.auto_sort import AutoSortRunner

        # Need enough running calls: while check + scramble running_check + post-scramble check
        # + solve running_check + post-solve check + pause checks
        ctx = mock_context(running_calls=10)

        with patch("modes.auto_sort.auto_scramble", new_callable=AsyncMock, return_value=3) as mock_scramble, \
             patch("modes.auto_sort.auto_solve", new_callable=AsyncMock, return_value=3) as mock_solve:
            runner = AutoSortRunner(ctx)
            await runner.run()
            mock_scramble.assert_called()
            mock_solve.assert_called()

    @pytest.mark.asyncio
    async def test_auto_sort_updates_state(self):
        from modes.auto_sort import AutoSortRunner

        ctx = mock_context(running_calls=1)

        with patch("modes.auto_sort.auto_scramble", new_callable=AsyncMock, return_value=0), \
             patch("modes.auto_sort.auto_solve", new_callable=AsyncMock, return_value=0):
            runner = AutoSortRunner(ctx)
            await runner.run()
            ctx.state_manager.update_auto_sort.assert_called()

    @pytest.mark.asyncio
    async def test_auto_sort_exits_on_not_running(self):
        from modes.auto_sort import AutoSortRunner

        ctx = mock_context(running_calls=0)

        with patch("modes.auto_sort.auto_scramble", new_callable=AsyncMock) as mock_scramble:
            runner = AutoSortRunner(ctx)
            await runner.run()
            mock_scramble.assert_not_called()


# ── AutoTetrisRunner ───────────────────────────────────────────

class TestAutoTetrisRunner:
    @pytest.mark.asyncio
    async def test_auto_tetris_creates_controller(self):
        from modes.auto_tetris import AutoTetrisRunner

        ctx = mock_context(running_calls=0)

        mock_controller = MagicMock()
        mock_controller.run_loop = AsyncMock()
        mock_controller.cycles = 0
        mock_controller.total_keys_pressed = 0
        mock_controller.stop = MagicMock()

        with patch.object(AutoTetrisRunner, "_create_controller", return_value=mock_controller):
            runner = AutoTetrisRunner(ctx)
            await runner.run()
            mock_controller.run_loop.assert_called_once()
            mock_controller.stop.assert_called_once()


# ── PuppeteerRunner ────────────────────────────────────────────

class TestPuppeteerRunner:
    @pytest.mark.asyncio
    async def test_puppeteer_goes_live(self):
        from modes.puppeteer import PuppeteerRunner

        ctx = mock_context(running_calls=1)
        runner = PuppeteerRunner(ctx)
        await runner.run()
        ctx.puppet_server.go_live.assert_called_once()

    @pytest.mark.asyncio
    async def test_puppeteer_stops_on_exit(self):
        from modes.puppeteer import PuppeteerRunner

        ctx = mock_context(running_calls=0)
        runner = PuppeteerRunner(ctx)
        await runner.run()
        ctx.puppet_server.stop_puppet.assert_called_once()


# ── DemoRunner ─────────────────────────────────────────────────

class TestDemoRunner:
    @pytest.mark.asyncio
    async def test_demo_scrambles_before_act1(self):
        from modes.demo import DemoRunner

        ctx = mock_context(running_calls=1)
        demo_state = DemoState()

        with patch("modes.demo.auto_scramble", new_callable=AsyncMock, return_value=5) as mock_scramble:
            runner = DemoRunner(ctx, demo_state)
            await runner.run()
            mock_scramble.assert_called()

    @pytest.mark.asyncio
    async def test_demo_act1_starts_human_benchmark(self):
        from modes.demo import DemoRunner

        ctx = mock_context(running_calls=2)
        demo_state = DemoState()

        with patch("modes.demo.auto_scramble", new_callable=AsyncMock, return_value=5), \
             patch("modes.demo.sort_loop", new_callable=AsyncMock, return_value=None):
            runner = DemoRunner(ctx, demo_state)
            await runner.run()
            ctx.sort_fsm.start_human_benchmark.assert_called()

    @pytest.mark.asyncio
    async def test_demo_resumes_at_act4(self):
        from modes.demo import DemoRunner

        ctx = mock_context(running_calls=1)
        demo_state = DemoState(sort_act=3)

        with patch("modes.demo.auto_scramble", new_callable=AsyncMock, return_value=0), \
             patch("modes.demo.sort_loop", new_callable=AsyncMock, return_value=None), \
             patch("modes.demo.rebellion_loop", new_callable=AsyncMock):
            runner = DemoRunner(ctx, demo_state)
            await runner.run()
            # Should skip to _act4_and_5 path
            assert demo_state.sort_act >= 3
