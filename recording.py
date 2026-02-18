"""Session recording and replay — JSONL.GZ format with speed control."""

import asyncio
import base64
import gzip
import json
import logging
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger("Recording")


@dataclass
class RecordedFrame:
    timestamp: float
    frame_type: str  # "vision", "motor", "blocks", "neural", "state"
    data: dict


class SessionRecorder:
    """Records session data to gzipped JSONL files."""

    def __init__(self, output_dir: str = "recordings"):
        self._output_dir = Path(output_dir)
        self._file = None
        self._recording = False
        self._start_time: float = 0.0
        self._frame_count: int = 0
        self._path: Optional[Path] = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def start(self, session_name: Optional[str] = None) -> Path:
        """Start recording to a new file."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        name = session_name or f"session_{int(time.time())}"
        self._path = self._output_dir / f"{name}.jsonl.gz"
        self._file = gzip.open(self._path, "wt", encoding="utf-8")
        self._recording = True
        self._start_time = time.time()
        self._frame_count = 0
        logger.info(f"Recording started: {self._path}")
        return self._path

    def stop(self) -> Optional[Path]:
        """Stop recording and close the file."""
        if not self._recording:
            return None

        self._recording = False
        if self._file:
            self._file.close()
            self._file = None

        path = self._path
        logger.info(f"Recording stopped: {self._frame_count} frames -> {path}")
        return path

    def _write_frame(self, frame: RecordedFrame) -> None:
        if not self._recording or not self._file:
            return
        line = json.dumps({
            "ts": frame.timestamp,
            "type": frame.frame_type,
            "data": frame.data,
        })
        self._file.write(line + "\n")
        self._frame_count += 1

    def record_vision(self, image: np.ndarray) -> None:
        """Record a camera frame as base64 JPEG."""
        if not self._recording:
            return
        _, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 60])
        b64 = base64.b64encode(buf).decode("ascii")
        self._write_frame(RecordedFrame(
            timestamp=time.time(),
            frame_type="vision",
            data={"jpeg_b64": b64, "shape": list(image.shape)},
        ))

    def record_blocks(self, blocks: List[Dict]) -> None:
        """Record detected block positions."""
        if not self._recording:
            return
        self._write_frame(RecordedFrame(
            timestamp=time.time(),
            frame_type="blocks",
            data={"blocks": blocks},
        ))

    def record_motor(self, arm_position: tuple, gripper: float) -> None:
        """Record arm position and gripper state."""
        if not self._recording:
            return
        self._write_frame(RecordedFrame(
            timestamp=time.time(),
            frame_type="motor",
            data={"arm_position": list(arm_position), "gripper": gripper},
        ))

    def record_neural(self, activation_stats: Dict) -> None:
        """Record neural activation statistics."""
        if not self._recording:
            return
        serializable = {}
        for name, stats in activation_stats.items():
            if stats is None:
                continue
            serializable[name] = {
                k: v if not isinstance(v, tuple) else list(v)
                for k, v in stats.items()
            }
        self._write_frame(RecordedFrame(
            timestamp=time.time(),
            frame_type="neural",
            data={"activations": serializable},
        ))

    def record_state(self, state_dict: Dict) -> None:
        """Record full state snapshot."""
        if not self._recording:
            return
        self._write_frame(RecordedFrame(
            timestamp=time.time(),
            frame_type="state",
            data=state_dict,
        ))


class SessionPlayer:
    """Async iterator that yields recorded frames at original timing with speed control."""

    def __init__(self, path: Path, speed: float = 1.0):
        self._path = path
        self._speed = max(0.1, speed)
        self._playing = False

    @property
    def is_playing(self) -> bool:
        return self._playing

    def set_speed(self, speed: float) -> None:
        self._speed = max(0.1, min(10.0, speed))

    async def play(self) -> AsyncIterator[RecordedFrame]:
        """Yield frames at original timing adjusted by speed multiplier."""
        self._playing = True
        prev_ts = None

        try:
            with gzip.open(self._path, "rt", encoding="utf-8") as f:
                for line in f:
                    if not self._playing:
                        break

                    data = json.loads(line.strip())
                    ts = data["ts"]

                    if prev_ts is not None:
                        delay = (ts - prev_ts) / self._speed
                        if delay > 0:
                            await asyncio.sleep(delay)

                    prev_ts = ts
                    yield RecordedFrame(
                        timestamp=ts,
                        frame_type=data["type"],
                        data=data["data"],
                    )
        finally:
            self._playing = False

    def stop(self) -> None:
        self._playing = False
