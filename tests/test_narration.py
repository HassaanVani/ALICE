"""Tests for narration.py — LLM narration service."""

import time
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from narration import NarrationService


class TestNarrationDisabled:
    @pytest.mark.asyncio
    async def test_narration_disabled_does_nothing(self):
        service = NarrationService(enabled=False)
        # start() should return immediately without setting _running
        await service.start()
        assert service._running is False

    @pytest.mark.asyncio
    async def test_narration_disabled_stop(self):
        service = NarrationService(enabled=False)
        await service.stop()
        assert service._running is False


class TestNarrationSetup:
    def test_narration_set_state_manager(self):
        service = NarrationService(enabled=False)
        sm = MagicMock()
        service.set_state_manager(sm)
        assert service._state_manager is sm

    def test_narration_init_defaults(self):
        service = NarrationService()
        assert service.enabled is False
        assert service.voice_rate == 175
        assert service.min_interval == 8
        assert service.model_name == "gemini-pro"


class TestNarrationInterval:
    @pytest.mark.asyncio
    async def test_narration_respects_min_interval(self):
        service = NarrationService(enabled=True, min_interval=60)
        sm = MagicMock()
        sm.state = MagicMock()
        sm.state.mode = "idle"
        service.set_state_manager(sm)

        # Simulate that we just narrated
        service._last_narration_time = time.time()

        # _check_and_narrate should return early due to interval
        await service._check_and_narrate()
        # No narration should happen (no _generate_text call)

    @pytest.mark.asyncio
    async def test_narration_narrates_after_interval(self):
        service = NarrationService(enabled=True, min_interval=0)
        sm = MagicMock()
        state = MagicMock()
        state.mode = "auto_sort"
        state.auto_sort_phase = "scrambling"
        state.auto_sort_cycle = 1
        state.detected_blocks = []
        state.sort_move_count = 0
        sm.state = state
        service.set_state_manager(sm)
        service._last_narration_time = 0.0
        service._last_mode = "auto_sort"

        # _generate_text is async, so use AsyncMock
        service._generate_text = AsyncMock(return_value=None)

        # Just verify it doesn't error
        await service._check_and_narrate()


class TestNarrationFallback:
    def test_narration_fallback_without_gemini(self):
        service = NarrationService(enabled=True)
        sm = MagicMock()
        state = MagicMock()
        state.mode = "auto_sort"
        state.auto_sort_phase = "scrambling"
        state.auto_sort_cycle = 1
        state.sort_move_count = 5
        sm.state = state
        service.set_state_manager(sm)

        text = service._fallback_narration()
        assert text is not None
        assert isinstance(text, str)
        assert "1" in text  # cycle number

    def test_fallback_returns_none_without_state_manager(self):
        service = NarrationService(enabled=True)
        text = service._fallback_narration()
        assert text is None

    def test_fallback_demo_mode(self):
        service = NarrationService(enabled=True)
        sm = MagicMock()
        state = MagicMock()
        state.mode = "demo"
        state.sort_state = "human_benchmark"
        state.sort_move_count = 3
        state.sort_start_time = time.time() - 10
        sm.state = state
        service.set_state_manager(sm)

        text = service._fallback_narration()
        assert text is not None
        assert "3" in text

    def test_fallback_puppeteer_mode(self):
        service = NarrationService(enabled=True)
        sm = MagicMock()
        state = MagicMock()
        state.mode = "puppeteer"
        state.puppeteer_state = "live"
        state.puppeteer_recording = False
        sm.state = state
        service.set_state_manager(sm)

        text = service._fallback_narration()
        assert text is not None
        assert "live" in text.lower()
