"""Tests for recording.py — SessionRecorder and SessionPlayer."""

import gzip
import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from recording import SessionRecorder, SessionPlayer, RecordedFrame


@pytest.fixture
def recorder(tmp_path):
    return SessionRecorder(output_dir=str(tmp_path))


class TestSessionRecorder:
    def test_start_creates_file(self, recorder, tmp_path):
        path = recorder.start("test_session")
        assert path.exists()
        recorder.stop()

    def test_is_recording(self, recorder):
        assert recorder.is_recording is False
        recorder.start()
        assert recorder.is_recording is True
        recorder.stop()
        assert recorder.is_recording is False

    def test_record_blocks(self, recorder):
        recorder.start()
        recorder.record_blocks([{"block_id": 1, "center": [100, 200]}])
        path = recorder.stop()
        assert recorder.frame_count == 1

        with gzip.open(path, "rt") as f:
            line = f.readline()
            data = json.loads(line)
            assert data["type"] == "blocks"

    def test_record_motor(self, recorder):
        recorder.start()
        recorder.record_motor((90, 90, 90, 90, 90), 0.0)
        recorder.stop()
        assert recorder.frame_count == 1

    def test_record_neural(self, recorder):
        recorder.start()
        recorder.record_neural({"conv1": {"mean": 0.5, "std": 0.1}})
        recorder.stop()
        assert recorder.frame_count == 1

    def test_record_state(self, recorder):
        recorder.start()
        recorder.record_state({"mode": "idle", "timestamp": 123.0})
        recorder.stop()
        assert recorder.frame_count == 1

    def test_no_write_when_not_recording(self, recorder):
        recorder.record_blocks([])
        assert recorder.frame_count == 0

    def test_stop_returns_path(self, recorder):
        recorder.start("my_session")
        path = recorder.stop()
        assert path is not None
        assert "my_session" in str(path)

    def test_stop_when_not_recording_returns_none(self, recorder):
        assert recorder.stop() is None


class TestSessionPlayer:
    def test_set_speed(self):
        player = SessionPlayer(Path("dummy"), speed=2.0)
        player.set_speed(5.0)
        assert player._speed == 5.0
        player.set_speed(0.05)
        assert player._speed == 0.1  # clamped

    def test_stop(self):
        player = SessionPlayer(Path("dummy"))
        player._playing = True
        player.stop()
        assert player.is_playing is False
