"""Tests for voice_input.py — command parsing, STT, and service lifecycle."""

import asyncio
from unittest.mock import MagicMock, AsyncMock

import numpy as np
import pytest

from voice_input import (
    CommandParser, ParsedCommand, WhisperSTT,
    VoiceInputService, AudioCapture,
    WHISPER_AVAILABLE, SD_AVAILABLE,
)


class TestCommandParser:
    @pytest.fixture
    def parser(self):
        return CommandParser()

    # --- hand_over ---
    def test_pass_me_the_marker(self, parser):
        cmd = parser.parse("pass me the marker")
        assert cmd.action == "hand_over"
        assert cmd.source_label == "marker"

    def test_give_me_my_pen(self, parser):
        cmd = parser.parse("give me my pen")
        assert cmd.action == "hand_over"
        assert cmd.source_label == "pen"

    def test_hand_me_that_cup(self, parser):
        cmd = parser.parse("hand me that cup")
        assert cmd.action == "hand_over"
        assert cmd.source_label == "cup"

    # --- fetch ---
    def test_get_the_book(self, parser):
        cmd = parser.parse("get the book")
        assert cmd.action == "fetch"
        assert cmd.source_label == "book"

    def test_grab_my_phone(self, parser):
        cmd = parser.parse("grab my phone")
        assert cmd.action == "fetch"
        assert cmd.source_label == "phone"

    def test_bring_me_the_scissors(self, parser):
        cmd = parser.parse("bring me the scissors")
        assert cmd.action == "fetch"
        assert cmd.source_label == "scissors"

    # --- move_near ---
    def test_move_cup_near_laptop(self, parser):
        cmd = parser.parse("move the cup near my laptop")
        assert cmd.action == "move_near"
        assert cmd.source_label == "cup"
        assert cmd.target_label == "laptop"

    def test_put_pen_next_to_book(self, parser):
        cmd = parser.parse("put the pen next to the book")
        assert cmd.action == "move_near"
        assert cmd.source_label == "pen"
        assert cmd.target_label == "book"

    def test_place_phone_beside_cup(self, parser):
        cmd = parser.parse("place my phone beside the cup")
        assert cmd.action == "move_near"
        assert cmd.source_label == "phone"
        assert cmd.target_label == "cup"

    def test_move_by(self, parser):
        cmd = parser.parse("move the marker by the laptop")
        assert cmd.action == "move_near"
        assert cmd.source_label == "marker"
        assert cmd.target_label == "laptop"

    # --- throw_away ---
    def test_throw_away_cup(self, parser):
        cmd = parser.parse("throw away the cup")
        assert cmd.action == "throw_away"
        assert cmd.source_label == "cup"

    def test_toss_wrapper(self, parser):
        cmd = parser.parse("toss the wrapper")
        assert cmd.action == "throw_away"
        assert cmd.source_label == "wrapper"

    def test_trash_this(self, parser):
        cmd = parser.parse("trash my tissue")
        assert cmd.action == "throw_away"
        assert cmd.source_label == "tissue"

    def test_get_rid_of(self, parser):
        cmd = parser.parse("get rid of the napkin")
        assert cmd.action == "throw_away"
        assert cmd.source_label == "napkin"

    # --- organize ---
    def test_clean_desk(self, parser):
        cmd = parser.parse("clean the desk")
        assert cmd.action == "organize"

    def test_tidy_up(self, parser):
        cmd = parser.parse("tidy up")
        assert cmd.action == "organize"

    def test_organize(self, parser):
        cmd = parser.parse("organize the table")
        assert cmd.action == "organize"

    # --- nudge ---
    def test_push_cup_left(self, parser):
        cmd = parser.parse("push the cup to the left")
        assert cmd.action == "nudge"
        assert cmd.source_label == "cup"
        assert cmd.target_label == "left"

    # --- unknown ---
    def test_unknown_command(self, parser):
        cmd = parser.parse("what's the weather like")
        assert cmd.action == "unknown"

    def test_empty_string(self, parser):
        cmd = parser.parse("")
        assert cmd.action == "unknown"

    # --- label cleaning ---
    def test_clean_label_strips_articles(self, parser):
        assert parser._clean_label("the marker") == "marker"
        assert parser._clean_label("my pen") == "pen"
        assert parser._clean_label("a cup") == "cup"

    def test_clean_label_strips_punctuation(self, parser):
        assert parser._clean_label("marker.") == "marker"
        assert parser._clean_label("cup!") == "cup"


class TestCommandParserLLM:
    @pytest.mark.asyncio
    async def test_llm_parse_with_mock(self):
        parser = CommandParser()
        mock_ollama = MagicMock()
        mock_ollama.generate_sync = MagicMock(
            return_value='{"action": "hand_over", "source_label": "mouse", "target_label": ""}'
        )
        cmd = await parser.parse_with_llm(
            "hand me that thing near the keyboard",
            ["cup", "laptop", "mouse", "keyboard"],
            mock_ollama,
        )
        assert cmd.action == "hand_over"
        assert cmd.source_label == "mouse"

    @pytest.mark.asyncio
    async def test_llm_parse_no_ollama(self):
        parser = CommandParser()
        cmd = await parser.parse_with_llm("do something", [], None)
        assert cmd.action == "unknown"

    @pytest.mark.asyncio
    async def test_llm_parse_bad_json(self):
        parser = CommandParser()
        mock_ollama = MagicMock()
        mock_ollama.generate_sync = MagicMock(return_value="not json at all")
        cmd = await parser.parse_with_llm("do something", [], mock_ollama)
        assert cmd.action == "unknown"


class TestWhisperSTT:
    def test_not_loaded_initially(self):
        stt = WhisperSTT()
        assert stt.is_loaded is False

    def test_transcribe_empty_when_not_loaded(self):
        stt = WhisperSTT()
        result = stt.transcribe_sync(np.zeros(16000, dtype=np.float32))
        assert result == ""


class TestVoiceInputService:
    def test_disabled_by_default(self):
        svc = VoiceInputService()
        assert svc._enabled is False

    @pytest.mark.asyncio
    async def test_start_when_disabled(self):
        svc = VoiceInputService()
        # Should return immediately without error
        await svc.start()
        assert svc._running is False

    @pytest.mark.asyncio
    async def test_stop(self):
        svc = VoiceInputService()
        await svc.stop()
        assert svc._running is False

    def test_set_dependencies(self):
        svc = VoiceInputService()
        mock = MagicMock()
        svc.set_interaction(mock)
        svc.set_personality(mock)
        svc.set_state_manager(mock)
        svc.set_camera_getter(lambda: None)
        svc.set_interrupt_callback(mock)
        assert svc._interaction is mock

    def test_get_visible_objects_no_camera(self):
        svc = VoiceInputService()
        assert svc._get_visible_objects() == []

    def test_get_visible_objects_with_sim_yolo(self):
        from vision.yolo_detector import YoloDetector
        svc = VoiceInputService()
        yolo = YoloDetector()
        yolo._simulate = True
        svc.set_yolo(yolo)
        svc.set_camera_getter(lambda: np.zeros((480, 640, 3), dtype=np.uint8))
        objects = svc._get_visible_objects()
        assert len(objects) >= 1
        assert "cup" in objects


class TestParsedCommand:
    def test_fields(self):
        cmd = ParsedCommand(
            action="move_near", source_label="cup",
            target_label="laptop", raw_text="move cup near laptop",
        )
        assert cmd.action == "move_near"
        assert cmd.source_label == "cup"
        assert cmd.target_label == "laptop"

    def test_defaults(self):
        cmd = ParsedCommand(action="unknown")
        assert cmd.source_label == ""
        assert cmd.confidence == 1.0
