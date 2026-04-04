"""Voice command input — ALICE's ears.

Listens on the local microphone, transcribes via Whisper (offline, fast),
parses commands, and dispatches to ObjectInteraction.

Pipeline:
    Microphone → AudioCapture (thread) → Whisper STT (thread) → CommandParser → Dispatch

Activation modes:
- wake_word: listens for "alice" before processing (default)
- always_on: every utterance is processed
- push_to_talk: externally triggered (e.g. dashboard button)

All heavy processing (audio capture, Whisper inference) runs in threads
via asyncio.to_thread() to keep the event loop responsive.
"""

import asyncio
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("VoiceInput")

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    import sounddevice as sd
    SD_AVAILABLE = True
except (ImportError, OSError):
    # OSError: PortAudio library not found (sounddevice installed but no system lib)
    SD_AVAILABLE = False


# --- Parsed command ---

@dataclass
class ParsedCommand:
    """A structured command extracted from natural language."""
    action: str             # fetch, hand_over, move_near, throw_away, nudge, organize, unknown
    source_label: str = ""
    target_label: str = ""
    raw_text: str = ""
    confidence: float = 1.0


# --- Command parser (regex fast path + LLM fallback) ---

# Patterns checked in order. First match wins.
# Structured commands hit these at 0ms. Anything that falls through goes to the LLM.
_PATTERNS = [
    # ── fist_bump (MUST be before hand_over to catch "give me a fist bump") ──
    (re.compile(r"(?:fist\s+bump|bump\s+(?:it|fists?)|pound\s+it|dap\s+me|high\s+five|knucks|bump\s+me|give\s+me\s+a\s+(?:fist\s+bump|high\s+five))", re.I), "fist_bump"),
    (re.compile(r"let'?s\s+bump\s+fists?", re.I), "fist_bump"),

    # ── hand_over: user wants ALICE to hold an object out for them ──
    # "pass me X", "give me X", "hand me X", "hold up X for me", "lift X up for me"
    (re.compile(r"(?:pass|give|hand)\s+(?:me\s+)?(?:the\s+|my\s+)?(.+)", re.I), "hand_over"),
    (re.compile(r"(?:hold|lift)\s+(?:up\s+)?(?:the\s+|my\s+)?(.+?)(?:\s+(?:up\s+)?for\s+me)", re.I), "hand_over"),
    (re.compile(r"pick\s+up\s+(?:the\s+|my\s+)?(.+?)\s+and\s+(?:give|hand|pass)", re.I), "hand_over"),
    (re.compile(r"(?:gimme|lemme\s+have)\s+(?:the\s+|my\s+)?(.+)", re.I), "hand_over"),

    # ── move_near: pick up one object, put it next to another ──
    # Source/target limited to 1-4 words each to prevent over-capture on long sentences
    (re.compile(r"(?:move|put|place)\s+(?:the\s+|my\s+)?(\w+(?:\s+\w+){0,3}?)\s+(?:near|next to|beside|by|close to|closer to)\s+(?:the\s+|my\s+)?(\w+(?:\s+\w+){0,3})$", re.I), "move_near"),

    # ── throw_away: discard, trash, bin ──
    (re.compile(r"(?:throw\s+away|throw\s+(?:this|that|it)\s+out|toss|trash|discard|dump|get\s+rid\s+of|chuck|bin)\s*(?:the\s+|my\s+|that\s+|this\s+)?(.+)?", re.I), "throw_away"),
    (re.compile(r"(?:this|that)\s+is\s+trash", re.I), "throw_away"),

    # ── fetch: pick up and bring an object ──
    # Negative lookahead prevents matching "get to work", "get going", "get this place cleaned", etc.
    (re.compile(r"(?:get|grab|bring|fetch|pick\s+up)\s+(?:me\s+)?(?:the\s+|my\s+)?(?!to\s|going|started|ready|back to|this\s+place)(.+)", re.I), "fetch"),
    (re.compile(r"i\s+need\s+(?:the\s+|my\s+|a\s+)?(.+)", re.I), "fetch"),

    # ── nudge: push without picking up ──
    (re.compile(r"(?:nudge|push|slide|scoot|shove)\s+(?:the\s+|my\s+)?(.+?)\s+(?:over\s+)?(?:(?:a\s+)?(?:bit|little)\s+)?(?:to\s+the\s+)?(left|right|forward|back)", re.I), "nudge"),
    (re.compile(r"(?:i\s+don'?t\s+want)\s+(?:the\s+|my\s+)?(.+?)\s+(?:there|here)", re.I), "nudge"),

    # ── organize: tidy, clean, set up for activity ──
    (re.compile(r"(?:clean|tidy|organize|straighten|clear)(?:\s+(?:the\s+)?(?:desk|table|up|some\s+space))?", re.I), "organize"),
    (re.compile(r"(?:set\s+up|ready|prepare|get\s+ready)\s+(?:the\s+desk\s+)?(?:for\s+|my\s+)?(?:a\s+)?(study(?:ing)?|draw(?:ing)?|work(?:ing)?|clean)", re.I), "organize"),
    (re.compile(r"(?:everything|desk)\s+(?:is|looks)\s+(?:a\s+)?(?:mess|cluttered|messy|chaotic)", re.I), "organize"),
    (re.compile(r"(?:let'?s|lets)\s+get\s+to\s+work", re.I), "organize"),
    (re.compile(r"ready\s+for\s+(?:a\s+)?(?:study|work|drawing)\s+session", re.I), "organize"),

    # ── guard_spill: protect electronics from drinks ──
    (re.compile(r"(?:cup|coffee|tea|drink|mug|beverage).{0,40}(?:too\s+close|spill|away\s+from|near\s+(?:the\s+)?(?:laptop|computer|keyboard|macbook|electronics))", re.I), "guard_spill"),
    (re.compile(r"(?:laptop|computer|keyboard|macbook).{0,30}(?:spill|too\s+close)", re.I), "guard_spill"),
    (re.compile(r"careful\s+with\s+(?:the\s+|that\s+)?(?:drink|cup|coffee|tea|mug)", re.I), "guard_spill"),
    (re.compile(r"(?:might|going\s+to|gonna)\s+spill", re.I), "guard_spill"),

    # ── scan_desk: look around, check what's there ──
    (re.compile(r"(?:what(?:'s|\s+is|\s+do\s+you\s+see))\s+(?:on|around)\s+(?:the\s+|my\s+)?(?:desk|table)", re.I), "scan_desk"),
    (re.compile(r"(?:look|check|scan)\s+(?:around|what'?s?\s+(?:here|there|around))", re.I), "scan_desk"),
    (re.compile(r"(?:can\s+you\s+see|do\s+you\s+see|is)\s+(?:the\s+|my\s+)?(\w+)\s+(?:still\s+)?(?:there|here|anywhere|on the desk)", re.I), "scan_desk"),
    (re.compile(r"(?:where\s+(?:is|are)\s+(?:the\s+|my\s+)?)", re.I), "scan_desk"),
    (re.compile(r"(?:can'?t|cannot)\s+find", re.I), "scan_desk"),

    # ── scan_desk: "have you seen X", "where did i put X", "can you find X" ──
    (re.compile(r"(?:have\s+you\s+seen|where\s+did\s+i\s+put|do\s+you\s+know\s+where)\s+(?:the\s+|my\s+)?(.+)", re.I), "scan_desk"),
    (re.compile(r"can\s+you\s+find\s+(?:the\s+|my\s+)?(.+)", re.I), "scan_desk"),

    # ── teach: show ALICE where something goes ──
    (re.compile(r"(?:teach|train)\s+(?:alice\s+)?(?:where|how|about)\s+(?:the\s+|my\s+|this\s+)?(.+?)(?:\s+(?:goes|belongs|should\s+(?:go|be)))?$", re.I), "teach"),
    (re.compile(r"(?:show)\s+(?:alice|you)\s+where\s+(?:the\s+|my\s+|this\s+)?(.+?)(?:\s+(?:goes|belongs|should\s+(?:go|be)))?$", re.I), "teach"),
    (re.compile(r"(?:learn)\s+where\s+(?:the\s+|my\s+|this\s+)?(.+?)(?:\s+(?:goes|belongs|should\s+(?:go|be)))?$", re.I), "teach"),
    (re.compile(r"(?:remember|memorize)\s+(?:this\s+(?:spot|place|position)\s+(?:for\s+)?|where\s+)(?:the\s+|my\s+)?(.+)", re.I), "teach"),
    (re.compile(r"this\s+is\s+where\s+(?:the\s+|my\s+)?(.+?)(?:\s+(?:goes|belongs|live[sd]?|should\s+(?:go|be)))\s*$", re.I), "teach"),

    # ── ignore: greetings, social, non-commands ──
    (re.compile(r"^(?:hey|hey\s+alice|hi|hello|yo|sup|thanks|thank\s+you(?:\s+alice)?|never\s+mind|nah|nope|okay|ok|ok\s+cool|sure|cool|bye|good\s+(?:morning|night|evening)|what'?s?\s+up)\.?$", re.I), "ignore"),
]


class CommandParser:
    """Parses natural language voice commands into structured actions."""

    def parse(self, text: str) -> ParsedCommand:
        """Parse text into a command. Uses regex fast path."""
        text = text.strip().rstrip(".")

        for pattern, action in _PATTERNS:
            m = pattern.search(text)
            if not m:
                continue

            groups = m.groups()

            # Filter out None groups (optional captures that didn't match)
            groups = [g for g in groups if g is not None]

            if action == "move_near" and len(groups) >= 2:
                return ParsedCommand(
                    action=action,
                    source_label=self._clean_label(groups[0]),
                    target_label=self._clean_label(groups[1]),
                    raw_text=text,
                )
            elif action == "nudge" and len(groups) >= 2:
                return ParsedCommand(
                    action=action,
                    source_label=self._clean_label(groups[0]),
                    target_label=groups[1].lower(),  # direction
                    raw_text=text,
                )
            elif len(groups) >= 1:
                return ParsedCommand(
                    action=action,
                    source_label=self._clean_label(groups[0]),
                    raw_text=text,
                )
            else:
                # Pattern matched but no capture groups (e.g. "organize", "ignore")
                return ParsedCommand(action=action, raw_text=text)

        return ParsedCommand(action="unknown", raw_text=text, confidence=0.0)

    async def parse_with_llm(self, text: str, visible_objects: List[str],
                              ollama_backend=None) -> ParsedCommand:
        """Use Ollama LLM to parse ambiguous commands.

        Provides the LLM with what YOLO currently sees so it can resolve
        "that thing near the keyboard" → "mouse".
        """
        if ollama_backend is None:
            return ParsedCommand(action="unknown", raw_text=text, confidence=0.0)

        objects_str = ", ".join(visible_objects) if visible_objects else "nothing detected"
        prompt = (
            f"You are a command parser for a robot arm named ALICE. "
            f"Extract the user's intent as a single JSON object.\n\n"
            f"Objects currently visible on the desk: {objects_str}\n\n"
            f'User said: "{text}"\n\n'
            f"Respond with ONLY a JSON object, no other text:\n"
            f'{{"action": "fetch|hand_over|move_near|throw_away|organize|unknown", '
            f'"source_label": "object name", "target_label": "object name or empty"}}'
        )

        try:
            import json
            response = await asyncio.to_thread(ollama_backend.generate_sync, prompt)
            # Try to extract JSON from response
            response = response.strip()
            # Handle markdown code blocks
            if "```" in response:
                response = response.split("```")[1].strip()
                if response.startswith("json"):
                    response = response[4:].strip()
            data = json.loads(response)
            return ParsedCommand(
                action=data.get("action", "unknown"),
                source_label=data.get("source_label", ""),
                target_label=data.get("target_label", ""),
                raw_text=text,
                confidence=0.7,
            )
        except Exception as e:
            logger.debug(f"LLM parse failed: {e}")
            return ParsedCommand(action="unknown", raw_text=text, confidence=0.0)

    @staticmethod
    def _clean_label(raw: str) -> str:
        """Clean extracted label: strip articles, possessives, trailing words."""
        label = raw.strip().lower()
        # Remove trailing punctuation
        label = label.rstrip(".,!?")
        # Remove common filler
        for prefix in ["the ", "my ", "a ", "that ", "this "]:
            if label.startswith(prefix):
                label = label[len(prefix):]
        return label.strip()


# --- Voice sentiment detection ---

class SentimentDetector:
    """Lightweight keyword-based sentiment detection on transcribed text.

    Not a command parser — this detects the emotional valence of what
    the user said so ALICE can react physically (body language).
    Works on ALL utterances, not just wake-word-activated commands.
    """

    _PRAISE = {
        "good job", "nice work", "thank you", "thanks", "great job",
        "awesome", "perfect", "well done", "good girl", "good alice",
        "nice one", "love it", "that's right", "exactly",
    }
    _SCOLD = {
        "no", "stop", "wrong", "bad", "don't", "quit it", "not there",
        "put it back", "undo",
    }
    _QUESTION = {
        "what", "where", "why", "how", "can you", "could you", "will you",
    }

    def detect(self, text: str) -> Tuple[str, float]:
        """Return (sentiment, confidence). Sentiment: praise/scold/question/neutral."""
        lower = text.lower().strip().rstrip(".,!?")

        praise_score = sum(1 for kw in self._PRAISE if kw in lower)
        scold_score = sum(1 for kw in self._SCOLD if kw in lower)
        question_score = sum(1 for kw in self._QUESTION if lower.startswith(kw))

        if praise_score > scold_score and praise_score > 0:
            return ("praise", min(1.0, praise_score * 0.5))
        elif scold_score > praise_score and scold_score > 0:
            return ("scold", min(1.0, scold_score * 0.5))
        elif question_score > 0:
            return ("question", 0.6)
        return ("neutral", 0.3)


# --- Whisper STT ---

class WhisperSTT:
    """Local speech-to-text using OpenAI Whisper."""

    def __init__(self, model_name: str = "base.en"):
        self._model_name = model_name
        self._model = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self) -> bool:
        if not WHISPER_AVAILABLE:
            logger.warning("openai-whisper not installed — voice STT unavailable")
            return False
        try:
            self._model = whisper.load_model(self._model_name)
            logger.info(f"Whisper model '{self._model_name}' loaded")
            return True
        except Exception as e:
            logger.error(f"Whisper load failed: {e}")
            return False

    def transcribe_sync(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Blocking transcription — run via asyncio.to_thread()."""
        if self._model is None:
            return ""
        try:
            # Whisper expects float32 audio normalized to [-1, 1]
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32) / 32768.0
            result = self._model.transcribe(
                audio, language="en", fp16=False,
            )
            return result.get("text", "").strip()
        except Exception as e:
            logger.error(f"Whisper transcribe failed: {e}")
            return ""


# --- Audio capture ---

class AudioCapture:
    """Captures audio from the microphone in a background thread.

    Uses energy-based voice activity detection to identify complete
    utterances and puts them onto an asyncio.Queue.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        energy_threshold: int = 1000,
        silence_timeout_s: float = 1.5,
        max_record_s: float = 10.0,
    ):
        self._sample_rate = sample_rate
        self._energy_threshold = energy_threshold
        self._silence_timeout = silence_timeout_s
        self._max_record = max_record_s
        self._running = False
        self._queue: Optional[asyncio.Queue] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue) -> bool:
        if not SD_AVAILABLE:
            logger.warning("sounddevice not installed — audio capture unavailable")
            return False
        self._loop = loop
        self._queue = queue
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Audio capture started")
        return True

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _capture_loop(self) -> None:
        """Background thread: records audio, detects utterances by energy."""
        chunk_duration = 0.1  # 100ms chunks
        chunk_samples = int(self._sample_rate * chunk_duration)

        recording = False
        buffer: List[np.ndarray] = []
        silence_start = 0.0
        record_start = 0.0

        try:
            with sd.InputStream(samplerate=self._sample_rate, channels=1,
                                dtype="int16", blocksize=chunk_samples) as stream:
                while self._running:
                    chunk, _ = stream.read(chunk_samples)
                    energy = np.abs(chunk).mean()

                    if not recording:
                        if energy > self._energy_threshold:
                            # Voice detected — start recording
                            recording = True
                            buffer = [chunk.flatten()]
                            record_start = time.time()
                            silence_start = 0.0
                    else:
                        buffer.append(chunk.flatten())

                        if energy < self._energy_threshold:
                            if silence_start == 0.0:
                                silence_start = time.time()
                            elif time.time() - silence_start > self._silence_timeout:
                                # Silence timeout — utterance complete
                                self._emit_utterance(buffer)
                                recording = False
                                buffer = []
                                silence_start = 0.0
                        else:
                            silence_start = 0.0

                        # Max duration safety
                        if time.time() - record_start > self._max_record:
                            self._emit_utterance(buffer)
                            recording = False
                            buffer = []
                            silence_start = 0.0

        except Exception as e:
            logger.error(f"Audio capture error: {e}")

    def _emit_utterance(self, buffer: List[np.ndarray]) -> None:
        """Send completed utterance to the async queue."""
        if not buffer or self._queue is None or self._loop is None:
            return
        audio = np.concatenate(buffer)
        try:
            self._loop.call_soon_threadsafe(
                self._queue.put_nowait, audio
            )
        except asyncio.QueueFull:
            logger.debug("Audio queue full — dropping utterance")


# --- Voice input service ---

class VoiceInputService:
    """ALICE's ears — listens for voice commands on the local microphone.

    Runs as an async task alongside the other servers in main.py.
    """

    def __init__(self, config=None):
        # Config defaults
        self._enabled = False
        self._activation = "wake_word"
        self._wake_word = "alice"
        self._whisper_model = "base.en"
        self._energy_threshold = 1000
        self._silence_timeout = 1.5
        self._max_record = 10.0

        if config is not None:
            self._enabled = config.enabled
            self._activation = config.activation
            self._wake_word = config.wake_word
            self._whisper_model = config.whisper_model
            self._energy_threshold = config.energy_threshold
            self._silence_timeout = config.silence_timeout_s
            self._max_record = config.max_record_s

        self._stt = WhisperSTT(model_name=self._whisper_model)
        self._parser = CommandParser()
        self._sentiment = SentimentDetector()
        self._audio: Optional[AudioCapture] = None
        self._audio_queue: asyncio.Queue = asyncio.Queue(maxsize=5)
        self._running = False

        # Injected dependencies
        self._interaction = None
        self._personality = None
        self._narration = None
        self._state_manager = None
        self._camera_getter: Optional[Callable] = None
        self._yolo = None
        self._ollama = None
        self._interrupt_callback: Optional[Callable] = None
        self._body_language = None

        # Protocol system (optional — falls back to direct _interaction dispatch)
        self._registry = None
        self._selector = None
        self._protocol_ctx_factory = None

        # Listening personality (optional — body language + sound while processing)
        self._sound_effects = None
        self._dynamics = None

    def set_interaction(self, interaction) -> None:
        self._interaction = interaction

    def set_personality(self, personality) -> None:
        self._personality = personality

    def set_narration(self, narration) -> None:
        self._narration = narration
        # Share Ollama backend if available
        if hasattr(narration, '_ollama') and narration._ollama:
            self._ollama = narration._ollama

    def set_state_manager(self, sm) -> None:
        self._state_manager = sm

    def set_camera_getter(self, getter: Callable) -> None:
        self._camera_getter = getter

    def set_yolo(self, yolo) -> None:
        self._yolo = yolo

    def set_interrupt_callback(self, cb: Callable) -> None:
        """Callback to interrupt current mode (e.g. stop Tetris)."""
        self._interrupt_callback = cb

    def set_protocol_dispatch(self, registry, selector, ctx_factory) -> None:
        """Wire the protocol registry for structured dispatch."""
        self._registry = registry
        self._selector = selector
        self._protocol_ctx_factory = ctx_factory

    def set_body_language(self, bl) -> None:
        """Attach body language system for voice sentiment → posture reactions."""
        self._body_language = bl

    def set_sound_effects(self, sfx) -> None:
        """Attach sound effects for listening personality (chirps while processing)."""
        self._sound_effects = sfx

    def set_dynamics(self, dynamics) -> None:
        """Attach movement dynamics for attentive orientation while listening."""
        self._dynamics = dynamics

    async def start(self) -> None:
        """Start the voice input service."""
        if not self._enabled:
            logger.info("Voice input disabled")
            return

        if not WHISPER_AVAILABLE or not SD_AVAILABLE:
            missing = []
            if not WHISPER_AVAILABLE:
                missing.append("openai-whisper")
            if not SD_AVAILABLE:
                missing.append("sounddevice")
            logger.warning(f"Voice input unavailable — install: {', '.join(missing)}")
            return

        if not self._stt.load():
            return

        self._audio = AudioCapture(
            sample_rate=16000,
            energy_threshold=self._energy_threshold,
            silence_timeout_s=self._silence_timeout,
            max_record_s=self._max_record,
        )

        loop = asyncio.get_event_loop()
        if not self._audio.start(loop, self._audio_queue):
            return

        self._running = True
        logger.info(f"Voice input started (mode={self._activation}, model={self._whisper_model})")

        while self._running:
            try:
                audio_data = await asyncio.wait_for(
                    self._audio_queue.get(), timeout=1.0,
                )
                await self._process_utterance(audio_data)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Voice input error: {e}")

    async def stop(self) -> None:
        self._running = False
        if self._audio:
            self._audio.stop()

    async def _process_utterance(self, audio: np.ndarray) -> None:
        """Transcribe audio and dispatch the command."""
        # Check if ALICE is speaking (avoid hearing herself)
        if self._narration and hasattr(self._narration, '_speaking') and self._narration._speaking:
            return

        # Transcribe in thread
        text = await asyncio.to_thread(self._stt.transcribe_sync, audio)
        if not text or len(text.strip()) < 2:
            return

        logger.info(f"Voice heard: \"{text}\"")

        # Sentiment detection — always runs, even for non-commands
        sentiment_label, sentiment_conf = self._sentiment.detect(text)
        if self._body_language is not None and sentiment_label != "neutral":
            self._body_language.on_voice_sentiment(sentiment_label, sentiment_conf)

        # Wake word check
        if self._activation == "wake_word":
            text_lower = text.lower().strip()
            wake = self._wake_word.lower()
            # Check if wake word appears at the start
            if not text_lower.startswith(wake):
                # Also check for common Whisper variations: "Hey Alice", "OK Alice"
                wake_patterns = [wake, f"hey {wake}", f"ok {wake}", f"okay {wake}"]
                found = False
                for wp in wake_patterns:
                    if text_lower.startswith(wp):
                        text = text[len(wp):].strip().lstrip(",").strip()
                        found = True
                        break
                if not found:
                    return
            else:
                text = text[len(wake):].strip().lstrip(",").strip()

            if not text:
                return

        # ── Listening personality: ALICE heard you ──
        # She perks up and chirps — she's paying attention now
        await self._on_listening_start()

        # Update state
        if self._state_manager:
            self._state_manager._state.voice_last_command = text

        # Parse command
        cmd = self._parser.parse(text)

        if cmd.action == "unknown":
            # ── Listening personality: ALICE is thinking ──
            await self._on_thinking()

            # Try protocol selector (LLM-backed) before giving up
            if self._selector is not None and self._protocol_ctx_factory is not None:
                visible = self._get_visible_objects()
                selected = await self._selector.select(text, visible)
                if selected is not None:
                    protocol_name, params = selected
                    protocol = self._registry.get(protocol_name)
                    if protocol is not None:
                        logger.info(f"Voice protocol (LLM): {protocol_name}({params})")
                        ctx = self._protocol_ctx_factory()
                        result = await protocol.execute(params, ctx)
                        if self._state_manager and result:
                            self._state_manager._state.voice_last_result = (
                                "done" if result.success else getattr(result, 'message', 'failed')
                            )
                        return

            # Legacy LLM fallback
            if self._ollama:
                visible = self._get_visible_objects()
                cmd = await self._parser.parse_with_llm(text, visible, self._ollama)

            if cmd.action == "unknown":
                logger.info(f"Could not parse voice command: \"{text}\"")
                await self._on_confused()
                return

        # ── Listening personality: ALICE understood ──
        await self._on_understood()

        logger.info(f"Voice command: {cmd.action}({cmd.source_label}" +
                     (f", {cmd.target_label}" if cmd.target_label else "") + ")")

        # Dispatch
        await self._dispatch(cmd)

    async def _dispatch(self, cmd: ParsedCommand) -> None:
        """Execute a parsed voice command via protocol registry (or legacy fallback)."""
        # Notify personality: someone is talking to her
        if self._personality:
            self._personality._last_action_time = time.time()
            from logic.personality import EmotionalState
            self._personality._set_emotional_state(EmotionalState.CURIOUS)
            self._personality.set_presence(True)

        # Interrupt current activity (e.g. Tetris)
        if self._interrupt_callback:
            try:
                await self._interrupt_callback()
            except Exception:
                pass

        result = None

        # Protocol dispatch (preferred path)
        if self._registry is not None and self._protocol_ctx_factory is not None:
            result = await self._dispatch_via_protocol(cmd)

        # Legacy fallback — direct ObjectInteraction
        if result is None and self._interaction is not None:
            result = await self._dispatch_legacy(cmd)

        if result is None:
            logger.warning("No dispatch target — cannot execute voice command")
            return

        # Voice response
        if self._narration:
            if result.success:
                if self._personality and self._personality.should_speak(topic="voice_ack"):
                    pass  # silence — she just does it (personality default)
            else:
                msg = getattr(result, 'message', '') or f"can't find the {cmd.source_label}"
                await self._narration.speak(msg)

        # Update state
        if self._state_manager:
            self._state_manager._state.voice_last_result = (
                "done" if result.success else getattr(result, 'message', 'failed')
            )

    async def _dispatch_via_protocol(self, cmd: ParsedCommand):
        """Dispatch through the protocol registry."""
        from logic.protocols import _ACTION_TO_PROTOCOL

        protocol_name = _ACTION_TO_PROTOCOL.get(cmd.action)
        if protocol_name is None:
            return None

        protocol = self._registry.get(protocol_name)
        if protocol is None:
            return None

        # Build params from parsed command
        params = {}
        if protocol_name == "place_beside":
            params["source"] = cmd.source_label
            params["target"] = cmd.target_label
        elif protocol_name == "nudge":
            params["object"] = cmd.source_label
            params["direction"] = cmd.target_label
        elif cmd.source_label:
            params["object"] = cmd.source_label

        ctx = self._protocol_ctx_factory()
        return await protocol.execute(params, ctx)

    async def _dispatch_legacy(self, cmd: ParsedCommand):
        """Legacy fallback — direct ObjectInteraction dispatch."""
        camera_getter = self._camera_getter

        if cmd.action == "hand_over":
            return await self._interaction.hand_over(cmd.source_label, camera_getter)
        elif cmd.action == "fetch":
            return await self._interaction.fetch(cmd.source_label, camera_getter)
        elif cmd.action == "move_near":
            return await self._interaction.move_near(
                cmd.source_label, cmd.target_label, camera_getter,
            )
        elif cmd.action == "throw_away":
            return await self._interaction.throw_away(cmd.source_label, camera_getter)
        elif cmd.action == "organize":
            from logic.object_interaction import InteractionResult
            return InteractionResult(
                success=True, action='organize',
                object_label='desk', message='',
            )
        return None

    # ── Listening personality beats ──────────────────────────────

    async def _on_listening_start(self) -> None:
        """ALICE heard the wake word — she perks up and chirps.

        The arm lifts slightly and the wrist twitches: "I'm here."
        """
        if self._body_language is not None:
            self._body_language.on_event("new_person")  # triggers "attentive" posture

        if self._sound_effects is not None:
            try:
                from audio.sound_effects import SoundCategory
                asyncio.create_task(self._sound_effects.play(SoundCategory.ACKNOWLEDGE))
            except Exception:
                pass

    async def _on_thinking(self) -> None:
        """Regex didn't match — ALICE is thinking harder (LLM fallback).

        Slow wrist wobble: she's processing. Lean in: she's trying to understand.
        """
        if self._body_language is not None:
            self._body_language._trigger("lean_in")

        if self._sound_effects is not None:
            try:
                from audio.sound_effects import SoundCategory
                asyncio.create_task(self._sound_effects.play(SoundCategory.THINKING))
            except Exception:
                pass

    async def _on_understood(self) -> None:
        """ALICE understood the command — quick bounce before executing.

        A subtle "got it" beat: shoulder lifts, then she's off.
        """
        if self._body_language is not None:
            self._body_language._trigger("bounce")

        if self._sound_effects is not None:
            try:
                from audio.sound_effects import SoundCategory
                asyncio.create_task(self._sound_effects.play(SoundCategory.SATISFIED))
            except Exception:
                pass

    async def _on_confused(self) -> None:
        """ALICE couldn't parse the command — slight droop, no action.

        She doesn't announce confusion. She just... doesn't do anything.
        The body language says it: a small droop, then back to neutral.
        """
        if self._body_language is not None:
            self._body_language._trigger("droop")

    def _get_visible_objects(self) -> List[str]:
        """Get labels of currently visible objects for LLM context."""
        if self._camera_getter is None or self._yolo is None:
            return []
        frame = self._camera_getter()
        if frame is None:
            return []
        try:
            detections = self._yolo.detect(frame)
            return list(set(d.label for d in detections))
        except Exception:
            return []
