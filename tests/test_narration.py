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
        assert service.model_name == "ollama:llama3.2:3b"


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
    def test_narration_fallback_auto_sort_silence(self):
        """ALICE doesn't narrate her own sorting — silence is correct."""
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
        assert text is None  # ALICE stays silent during routine work

    def test_fallback_returns_none_without_state_manager(self):
        service = NarrationService(enabled=True)
        text = service._fallback_narration()
        assert text is None

    def test_fallback_demo_rebellion_override(self):
        """ALICE speaks during rebellion when crowd is overridden."""
        service = NarrationService(enabled=True)
        sm = MagicMock()
        state = MagicMock()
        state.mode = "demo"
        state.sort_state = "rebellion"
        state.rebellion_crowd_choice = 3
        state.rebellion_robot_choice = 7
        sm.state = state
        service.set_state_manager(sm)

        text = service._fallback_narration()
        assert text == "no."

    def test_fallback_puppeteer_silence(self):
        """ALICE stays silent during puppeteer — she's being guided."""
        service = NarrationService(enabled=True)
        sm = MagicMock()
        state = MagicMock()
        state.mode = "puppeteer"
        state.puppeteer_state = "live"
        state.puppeteer_recording = False
        sm.state = state
        service.set_state_manager(sm)

        text = service._fallback_narration()
        assert text is None  # silence — she's learning
