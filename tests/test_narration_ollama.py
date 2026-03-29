"""Tests for narration.py — Ollama backend, brevity enforcement, backend selection."""

import pytest
from unittest.mock import patch, MagicMock

from narration import NarrationService, OllamaBackend, ALICE_SYSTEM_PROMPT


class TestOllamaBackend:
    def test_model_property(self):
        backend = OllamaBackend(model="phi3:mini")
        assert backend.model == "phi3:mini"

    def test_is_available_returns_false_when_unreachable(self):
        backend = OllamaBackend(base_url="http://localhost:99999")
        assert backend.is_available() is False

    def test_is_available_caches_result(self):
        backend = OllamaBackend(base_url="http://localhost:99999")
        backend.is_available()  # first call
        # Second call should use cache, not hit network again
        assert backend._available is False
        assert backend.is_available() is False

    def test_generate_sync_returns_empty_on_failure(self):
        backend = OllamaBackend(base_url="http://localhost:99999")
        result = backend.generate_sync("test prompt")
        assert result == ""


class TestBrevityEnforcement:
    def test_truncates_long_response(self):
        text = "I think this response is way too long and should definitely be truncated to something shorter"
        result = NarrationService._enforce_brevity(text)
        assert len(result.split()) <= 10

    def test_takes_first_sentence(self):
        text = "not that. I don't like it there."
        result = NarrationService._enforce_brevity(text)
        assert result == "not that"

    def test_lowercases(self):
        text = "TOLD YOU"
        result = NarrationService._enforce_brevity(text)
        assert result == "told you"

    def test_strips_quotes(self):
        text = '"fine."'
        result = NarrationService._enforce_brevity(text)
        assert result == "fine"

    def test_strips_asterisks(self):
        text = "*sighs* okay"
        result = NarrationService._enforce_brevity(text)
        assert "okay" in result

    def test_short_response_unchanged(self):
        text = "no"
        result = NarrationService._enforce_brevity(text)
        assert result == "no"

    def test_empty_string(self):
        result = NarrationService._enforce_brevity("")
        assert result == ""


class TestBackendSelection:
    def test_rule_backend(self):
        svc = NarrationService(model="rule")
        svc._init_llm()
        assert svc._backend == "rule"

    def test_ollama_prefix_parsed(self):
        svc = NarrationService(model="ollama:phi3:mini")
        # Will fail to connect but should attempt ollama
        svc._init_llm()
        # Should fall back to rule since ollama isn't running in tests
        assert svc._backend in ("ollama", "rule")

    def test_gemini_without_key_tries_ollama_then_rule(self):
        # No ALICE_GEMINI_KEY set
        import os
        old = os.environ.pop("ALICE_GEMINI_KEY", None)
        try:
            svc = NarrationService(model="gemini-pro")
            svc._init_llm()
            assert svc._backend in ("ollama", "rule")
        finally:
            if old is not None:
                os.environ["ALICE_GEMINI_KEY"] = old

    def test_default_model_is_ollama(self):
        svc = NarrationService()
        assert svc.model_name.startswith("ollama:")


class TestSystemPrompt:
    def test_system_prompt_has_key_phrases(self):
        assert "under 8 words" in ALICE_SYSTEM_PROMPT
        assert "[silence]" in ALICE_SYSTEM_PROMPT
        assert "not an assistant" in ALICE_SYSTEM_PROMPT
        assert "Tetris" in ALICE_SYSTEM_PROMPT
        assert "coffee" in ALICE_SYSTEM_PROMPT.lower()


class TestNarrationServiceInit:
    def test_enabled_flag(self):
        svc = NarrationService(enabled=False)
        assert svc.enabled is False

    def test_min_interval(self):
        svc = NarrationService(min_interval=15)
        assert svc.min_interval == 15

    @pytest.mark.asyncio
    async def test_speak_logs(self, caplog):
        svc = NarrationService()
        import logging
        with caplog.at_level(logging.INFO, logger="Narration"):
            await svc.speak("told you")
        assert 'ALICE: "told you"' in caplog.text

    @pytest.mark.asyncio
    async def test_speak_immediate(self):
        svc = NarrationService()
        from logic.personality import PersonalityEngine
        personality = PersonalityEngine()
        svc.set_personality(personality)
        await svc.speak_immediate("fine")
        assert personality._state.last_speech_topic == "immediate"
