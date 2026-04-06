"""LLM movement interpreter — the model thinks, ALICE's body expresses.

The LLM doesn't replace hardcoded movement protocols. It modulates them.
Every few seconds, the interpreter reads ALICE's full context (mood, desk state,
curiosity, habits, who's present) and outputs a small JSON blob of numeric
multipliers. These multipliers scale the hardcoded defaults — making body
language stronger or softer, movements faster or slower, scans wider or tighter.

When the LLM is unavailable or slow, all modifiers are 1.0 (no change).
The hardcoded systems always run. The LLM just tunes the knobs.

Designed for llama3.2:3b (~2GB) via local Ollama. Prompts are compact
(~100 tokens in, ~40 tokens out), latency target <200ms on Apple Silicon.
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from urllib.request import urlopen, Request
from urllib.error import URLError

if TYPE_CHECKING:
    from logic.personality import PersonalityEngine
    from logic.curiosity import CuriosityEngine
    from logic.gaze_tracker import GazeTracker
    from logic.body_language import BodyLanguage
    from logic.object_memory import ObjectMemory
    from vision.presence import PresenceDetector

logger = logging.getLogger("LLMInterpreter")

# System prompt — extremely compact to minimize token use.
# Includes one example so the 3B model knows the exact output format.
INTERPRETER_SYSTEM = (
    "You modulate a robot arm's movement personality. "
    "Output ONLY a JSON object with float values 0.3-2.0. "
    "Keys: spd(speed) hes(pause) pos(posture) scn(scan_range) "
    "per(scan_slowness) sfx(sound) appr(approach) tilt(head_tilt). "
    "1.0=normal. <1=less, >1=more. No text outside the JSON.\n"
    'Example: {"spd":1.1,"hes":0.8,"pos":1.3,"scn":1.0,"per":1.0,"sfx":0.9,"appr":1.0,"tilt":1.2}'
)


@dataclass
class MovementModifiers:
    """LLM-generated behavior modifiers. All default to 1.0 (no change).

    Each field is a multiplier applied on top of the hardcoded default.
    Clamped to [min_val, max_val] during parsing.
    """
    spd: float = 1.0    # movement speed
    hes: float = 1.0    # hesitation/pause duration
    pos: float = 1.0    # body language overlay strength
    scn: float = 1.0    # idle scan amplitude
    per: float = 1.0    # idle scan period (higher = slower)
    sfx: float = 1.0    # servo sound intensity
    appr: float = 1.0   # curiosity approach speed
    tilt: float = 1.0   # curiosity tilt angle
    timestamp: float = 0.0
    source: str = "default"  # "llm" or "default"

    def to_dict(self) -> dict:
        return {
            "spd": round(self.spd, 2), "hes": round(self.hes, 2),
            "pos": round(self.pos, 2), "scn": round(self.scn, 2),
            "per": round(self.per, 2), "sfx": round(self.sfx, 2),
            "appr": round(self.appr, 2), "tilt": round(self.tilt, 2),
            "source": self.source,
        }


# JSON extraction pattern — finds first {...} in LLM output
_JSON_RE = re.compile(r'\{[^}]+\}')

# All modifier keys
_MOD_KEYS = ("spd", "hes", "pos", "scn", "per", "sfx", "appr", "tilt")


def parse_modifiers(raw: str, min_val: float = 0.3,
                    max_val: float = 2.0) -> MovementModifiers:
    """Parse LLM response into MovementModifiers.

    Extracts the first JSON object from the response, reads numeric values,
    clamps them, and fills missing keys with 1.0. Returns defaults on any error.
    """
    if not raw or not raw.strip():
        return MovementModifiers()

    # Try to extract JSON from anywhere in the response
    match = _JSON_RE.search(raw)
    if not match:
        return MovementModifiers()

    try:
        data = json.loads(match.group())
    except (json.JSONDecodeError, ValueError):
        return MovementModifiers()

    kwargs = {}
    for key in _MOD_KEYS:
        val = data.get(key)
        if val is None:
            continue
        try:
            val = float(val)
            kwargs[key] = max(min_val, min(max_val, val))
        except (TypeError, ValueError):
            pass  # skip non-numeric, use default 1.0

    return MovementModifiers(
        **kwargs,
        timestamp=time.time(),
        source="llm",
    )


class LLMInterpreter:
    """Periodically queries a local LLM to modulate ALICE's movement personality.

    Runs on its own async timer. Reads context from attached systems,
    sends a compact prompt to Ollama, parses the JSON response into
    MovementModifiers. Consumer systems read .modifiers to scale their
    hardcoded parameters.

    Usage:
        interp = LLMInterpreter()
        interp.attach(personality=..., curiosity_engine=..., ...)
        asyncio.create_task(interp.start())

        # In consumer:
        mod = interp.modifiers
        effective_speed *= mod.spd
    """

    def __init__(
        self,
        model: str = "llama3.2:3b",
        base_url: str = "http://localhost:11434",
        interval_s: float = 4.0,
        timeout_s: float = 0.5,
        num_predict: int = 60,
        temperature: float = 0.3,
        min_val: float = 0.3,
        max_val: float = 2.0,
    ):
        self._model = model
        self._base_url = base_url
        self._interval = interval_s
        self._timeout = timeout_s
        self._num_predict = num_predict
        self._temperature = temperature
        self._min_val = min_val
        self._max_val = max_val

        self._modifiers = MovementModifiers()
        self._running = False
        self._available: Optional[bool] = None

        # Attached state sources (read-only references)
        self._personality: Optional["PersonalityEngine"] = None
        self._curiosity: Optional["CuriosityEngine"] = None
        self._gaze: Optional["GazeTracker"] = None
        self._body_language: Optional["BodyLanguage"] = None
        self._object_memory: Optional["ObjectMemory"] = None
        self._presence: Optional["PresenceDetector"] = None

    @property
    def modifiers(self) -> MovementModifiers:
        return self._modifiers

    def attach(
        self,
        personality=None,
        curiosity_engine=None,
        gaze_tracker=None,
        body_language=None,
        object_memory=None,
        presence_detector=None,
    ) -> None:
        """Wire in read-only references to ALICE's subsystems."""
        self._personality = personality
        self._curiosity = curiosity_engine
        self._gaze = gaze_tracker
        self._body_language = body_language
        self._object_memory = object_memory
        self._presence = presence_detector

    def _check_available(self) -> bool:
        """Check if Ollama is running with the right model (cached)."""
        if self._available is not None:
            return self._available

        try:
            req = Request(f"{self._base_url}/api/tags", method="GET")
            with urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read())
                models = [m["name"] for m in data.get("models", [])]
                self._available = any(
                    self._model in m or m.startswith(self._model.split(":")[0])
                    for m in models
                )
                if not self._available:
                    logger.warning(
                        f"Ollama model '{self._model}' not found. "
                        f"Available: {models}"
                    )
                return self._available
        except (URLError, OSError, json.JSONDecodeError):
            self._available = False
            return False

    def _build_context(self) -> str:
        """Build a compact context string from all attached systems (~100 tokens)."""
        parts = []

        if self._personality is not None:
            s = self._personality.state
            parts.append(f"mood:{s.overall_mood:.1f}")
            parts.append(f"emo:{s.emotional_state.value}")
            parts.append(f"idle:{s.idle_duration:.0f}s")
            parts.append(f"overrides:{s.override_streak}")
            parts.append(f"flow:{s.is_in_flow}")
            parts.append(f"opinion:{s.strongest_opinion:.1f}")

        if self._curiosity is not None:
            most = self._curiosity.get_most_curious()
            parts.append(f"curiosity:{self._curiosity.total_curiosity:.1f}")
            if most:
                parts.append(f"curious_about:{most.label}({most.curiosity_level:.1f})")

        if self._object_memory is not None:
            parts.append(f"objects:{self._object_memory.object_count}")

        if self._presence is not None:
            info = self._presence.last_info
            parts.append(f"presence:{'yes' if info.detected else 'no'}")
            if info.detected:
                parts.append(f"distance:{info.closest_distance:.0f}cm")

        if self._gaze is not None:
            target = self._gaze.get_target()
            parts.append(f"gaze:{target.target_type}")
            if target.label:
                parts.append(f"watching:{target.label}")

        if self._body_language is not None:
            posture = self._body_language.current_posture_name
            if posture:
                parts.append(f"posture:{posture}")

        return " ".join(parts) if parts else "idle"

    def _generate_sync(self, prompt: str) -> str:
        """Synchronous Ollama call. Blocks — run via asyncio.to_thread."""
        payload = json.dumps({
            "model": self._model,
            "prompt": prompt,
            "system": INTERPRETER_SYSTEM,
            "stream": False,
            "options": {
                "temperature": self._temperature,
                "top_p": 0.8,
                "num_predict": self._num_predict,
            },
        }).encode("utf-8")

        req = Request(
            f"{self._base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read())
                return data.get("response", "").strip()
        except (URLError, OSError, json.JSONDecodeError) as e:
            logger.debug(f"Ollama query failed: {e}")
            return ""

    async def _query(self) -> MovementModifiers:
        """Build context, query LLM, parse response. Returns defaults on failure."""
        context = self._build_context()

        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(self._generate_sync, context),
                timeout=self._timeout,
            )
        except (asyncio.TimeoutError, Exception) as e:
            logger.debug(f"LLM interpreter timeout/error: {e}")
            return MovementModifiers()

        if not raw:
            return MovementModifiers()

        mods = parse_modifiers(raw, self._min_val, self._max_val)
        logger.debug(f"LLM modifiers: {mods.to_dict()}")
        return mods

    async def start(self) -> None:
        """Main loop — query LLM every interval_s seconds."""
        if not self._check_available():
            logger.warning("LLM interpreter disabled — Ollama not available")
            return

        self._running = True
        logger.info(
            f"LLM movement interpreter started "
            f"(model={self._model}, interval={self._interval}s)"
        )

        # Warmup query to load model into GPU memory
        await self._query()

        while self._running:
            self._modifiers = await self._query()
            await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        self._running = False
