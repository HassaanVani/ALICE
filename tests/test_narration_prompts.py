"""Tests for narration_prompts.py — Gemini prompt templates."""

import pytest

from narration_prompts import (
    SYSTEM_PROMPT,
    chimp_sort_prompt,
    tetris_prompt,
    puppeteer_prompt,
    calibration_prompt,
    mode_switch_prompt,
    rebellion_prompt,
    awaiting_puppeteer_prompt,
    auto_sort_prompt,
    auto_tetris_prompt,
    error_prompt,
)


class TestBuildPrompt:
    def test_build_prompt_returns_string(self):
        result = chimp_sort_prompt("human_benchmark", 5, 16, 12.5, 3)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_tetris_prompt_returns_string(self):
        result = tetris_prompt(score=500, lines_cleared=4, level=2, game_over=False)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_puppeteer_prompt_returns_string(self):
        result = puppeteer_prompt("live", [90, 45, 30, 0], recording=False)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_calibration_prompt_returns_string(self):
        result = calibration_prompt(points_collected=4, transform_ready=True)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_awaiting_puppeteer_returns_string(self):
        result = awaiting_puppeteer_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_error_prompt_returns_string(self):
        result = error_prompt("connection_lost", "Arm disconnected")
        assert isinstance(result, str)
        assert len(result) > 0


class TestPromptContent:
    def test_prompt_includes_mode(self):
        result = auto_sort_prompt(phase="scrambling", cycle=3, blocks_detected=8, move_count=12)
        assert "Auto Sort" in result

    def test_auto_tetris_prompt_includes_mode(self):
        result = auto_tetris_prompt(score=100, lines_cleared=2, level=1, game_over=False)
        assert "Auto Tetris" in result

    def test_mode_switch_includes_modes(self):
        result = mode_switch_prompt("idle", "demo")
        assert "idle" in result
        assert "demo" in result

    def test_rebellion_prompt_includes_override_text(self):
        result = rebellion_prompt(blocks_remaining=5, crowd_choice=3, robot_choice=7, move_count=10)
        assert "3" in result
        assert "7" in result

    def test_rebellion_prompt_no_crowd_choice(self):
        result = rebellion_prompt(blocks_remaining=5, crowd_choice=None, robot_choice=7, move_count=10)
        assert "hasn't voted" in result or "haven't voted" in result

    def test_rebellion_prompt_agreed(self):
        result = rebellion_prompt(blocks_remaining=5, crowd_choice=7, robot_choice=7, move_count=10)
        assert "both chose" in result

    def test_system_prompt_present(self):
        assert "A.L.I.C.E." in SYSTEM_PROMPT
        assert len(SYSTEM_PROMPT) > 20
