"""Tests for narration_prompts.py — ALICE's first-person voice prompts."""

import pytest

from narration_prompts import (
    SYSTEM_PROMPT,
    desk_organize_prompt,
    override_prompt,
    spill_prompt,
    presence_prompt,
    question_prompt,
    tetris_interrupt_prompt,
    mode_switch_prompt,
    error_prompt,
)


class TestSystemPrompt:
    def test_system_prompt_is_first_person(self):
        assert "You are ALICE" in SYSTEM_PROMPT

    def test_system_prompt_enforces_brevity(self):
        assert "8 words" in SYSTEM_PROMPT

    def test_system_prompt_supports_silence(self):
        assert "[silence]" in SYSTEM_PROMPT

    def test_system_prompt_not_eager(self):
        assert "not eager to help" in SYSTEM_PROMPT


class TestPrompts:
    def test_desk_organize_returns_string(self):
        result = desk_organize_prompt("moved", "mug", 0.5, 0)
        assert isinstance(result, str)
        assert len(result) > 0
        assert "mug" in result

    def test_override_prompt_contains_object(self):
        result = override_prompt("tea", 2)
        assert "tea" in result

    def test_override_prompt_streak_context(self):
        result = override_prompt("tea", 3)
        assert "Third" in result or "earned" in result

    def test_spill_prompt_returns_string(self):
        result = spill_prompt("tea", 2)
        assert "spill" in result.lower() or "tea" in result

    def test_presence_prompt_entering(self):
        result = presence_prompt(entering=True)
        assert "sat down" in result or "Tetris" in result

    def test_presence_prompt_leaving(self):
        result = presence_prompt(entering=False)
        assert "[silence]" in result

    def test_question_prompt(self):
        result = question_prompt("Why did you put the pens there?")
        assert "pens" in result

    def test_tetris_interrupt_silence(self):
        result = tetris_interrupt_prompt()
        assert "[silence]" in result

    def test_mode_switch_silence(self):
        result = mode_switch_prompt("idle", "active")
        assert "[silence]" in result
        assert "idle" in result

    def test_error_prompt(self):
        result = error_prompt("connection_lost", "Arm disconnected")
        assert "connection_lost" in result or "Arm disconnected" in result
