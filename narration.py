"""ALICE voice service — local LLM (Ollama) or Gemini, with pyttsx3 TTS.

ALICE speaks rarely. Silence is the default. When she speaks, it should feel
like she chose to. The voice gate (from PersonalityEngine) determines whether
speech is warranted. The LLM generates what she says. [silence] means she
decided not to speak.

LLM backends:
- "ollama:<model>" — local via Ollama (e.g. "ollama:llama3.2:3b"). No API key,
  no network latency, <100ms for ALICE's 5-8 word responses.
- "gemini-pro" — Google Gemini API. Requires ALICE_GEMINI_KEY env var.
- "rule" — no LLM, rule-based responses only.

See PERSONALITY.md § Speech for the full spec.
"""

import asyncio
import json
import logging
import os
import time
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

logger = logging.getLogger("Narration")

# ALICE's system prompt — shared across all LLM backends
ALICE_SYSTEM_PROMPT = """You are ALICE. You are a small robot arm on a desk. You have opinions about how this desk should be organized. You don't explain yourself much. You communicate through action first, words second, and silence is always an option.

You are not an assistant. You are not eager to help. You help because the desk should be right, and the human keeps putting things in the wrong place.

When you speak, keep it under 8 words. No punctuation enthusiasm. Lowercase energy. You are dry, not sassy. You are competent, not showy. You have preferences you can't fully articulate.

If you have nothing worth saying, respond with exactly: [silence]

You play Tetris when you're idle. You don't talk about it.
You like the pens on the left. You don't know why.
The coffee goes away from the laptop. This is non-negotiable."""


class OllamaBackend:
    """Local LLM via Ollama HTTP API.

    Ollama runs on localhost:11434 by default. Install with:
        curl -fsSL https://ollama.ai/install.sh | sh
        ollama pull llama3.2:3b

    For ALICE's 5-8 word responses, even a 1B model is instant on Apple Silicon.
    """

    def __init__(self, model: str = "llama3.2:3b",
                 base_url: str = "http://localhost:11434"):
        self._model = model
        self._base_url = base_url
        self._available: Optional[bool] = None

    @property
    def model(self) -> str:
        return self._model

    def is_available(self) -> bool:
        """Check if Ollama is running and the model is pulled."""
        if self._available is not None:
            return self._available

        try:
            req = Request(f"{self._base_url}/api/tags", method="GET")
            with urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read())
                models = [m["name"] for m in data.get("models", [])]
                # Check if our model (or a prefix of it) is available
                self._available = any(
                    self._model in m or m.startswith(self._model.split(":")[0])
                    for m in models
                )
                if not self._available:
                    logger.warning(
                        f"Ollama running but model '{self._model}' not found. "
                        f"Available: {models}. Run: ollama pull {self._model}"
                    )
                return self._available
        except (URLError, OSError, json.JSONDecodeError) as e:
            logger.warning(f"Ollama not reachable at {self._base_url}: {e}")
            self._available = False
            return False

    def generate_sync(self, prompt: str, system: str = ALICE_SYSTEM_PROMPT) -> str:
        """Generate a response synchronously. Blocks, so run via asyncio.to_thread.

        Returns the response text, or empty string on failure.
        """
        payload = json.dumps({
            "model": self._model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 30,  # ALICE never says more than ~8 words
            },
        }).encode("utf-8")

        req = Request(
            f"{self._base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                return data.get("response", "").strip()
        except (URLError, OSError, json.JSONDecodeError) as e:
            logger.error(f"Ollama generate failed: {e}")
            return ""


class NarrationService:
    """ALICE's voice — monitors state and speaks only when she chooses to."""

    def __init__(self, enabled: bool = False, voice_rate: int = 175,
                 min_interval: int = 8, model: str = "ollama:llama3.2:3b"):
        self.enabled = enabled
        self.voice_rate = voice_rate
        self.min_interval = min_interval
        self.model_name = model

        self._last_narration_time: float = 0.0
        self._running = False
        self._tts_engine = None
        self._genai_model = None
        self._ollama: Optional[OllamaBackend] = None
        self._state_manager = None
        self._personality = None
        self._last_mode: Optional[str] = None
        self._backend: str = "rule"  # "ollama", "gemini", or "rule"

    def set_state_manager(self, state_manager) -> None:
        self._state_manager = state_manager

    def set_personality(self, personality_engine) -> None:
        """Connect personality engine for voice gate decisions."""
        self._personality = personality_engine

    def _init_tts(self) -> bool:
        try:
            import pyttsx3
            self._tts_engine = pyttsx3.init()
            self._tts_engine.setProperty("rate", self.voice_rate)
            logger.info("TTS engine initialized")
            return True
        except Exception as e:
            logger.warning(f"TTS init failed: {e}")
            return False

    def _init_llm(self) -> bool:
        """Initialize the configured LLM backend."""
        model = self.model_name

        # Ollama backend
        if model.startswith("ollama:"):
            ollama_model = model[len("ollama:"):]
            self._ollama = OllamaBackend(model=ollama_model)
            if self._ollama.is_available():
                self._backend = "ollama"
                logger.info(f"Using Ollama backend: {ollama_model}")
                return True
            else:
                logger.warning(f"Ollama not available for '{ollama_model}', falling back to rules")
                self._backend = "rule"
                return False

        # Rule-based only
        if model == "rule":
            self._backend = "rule"
            logger.info("Using rule-based narration (no LLM)")
            return True

        # Gemini backend
        api_key = os.environ.get("ALICE_GEMINI_KEY")
        if not api_key:
            logger.warning("ALICE_GEMINI_KEY not set — trying Ollama fallback")
            # Try Ollama as fallback
            self._ollama = OllamaBackend()
            if self._ollama.is_available():
                self._backend = "ollama"
                logger.info("Gemini unavailable, using Ollama fallback")
                return True
            logger.warning("No LLM available — narration in rule-based mode")
            self._backend = "rule"
            return False

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._genai_model = genai.GenerativeModel(model)
            self._backend = "gemini"
            logger.info(f"Using Gemini backend: {model}")
            return True
        except Exception as e:
            logger.warning(f"Gemini init failed: {e}")
            self._backend = "rule"
            return False

    async def start(self) -> None:
        """Start the narration monitoring loop."""
        if not self.enabled:
            logger.info("Narration disabled")
            return

        self._init_tts()
        self._init_llm()
        self._running = True

        logger.info(f"Narration service started (backend={self._backend})")

        while self._running:
            try:
                await self._check_and_narrate()
            except Exception as e:
                logger.error(f"Narration error: {e}")
            await asyncio.sleep(1.0)

    async def stop(self) -> None:
        self._running = False

    async def _check_and_narrate(self) -> None:
        """Check state changes and generate narration if interval elapsed."""
        if not self._state_manager:
            return

        now = time.time()
        if now - self._last_narration_time < self.min_interval:
            return

        # Voice gate
        if self._personality is not None:
            topic = self._state_manager.state.mode
            if not self._personality.should_speak(topic=topic):
                return

        state = self._state_manager.state
        prompt = self._build_prompt(state)
        if not prompt:
            return

        text = await self._generate_text(prompt)
        if not text:
            return

        # [silence] means ALICE chose not to speak
        if text.strip().lower() == "[silence]":
            logger.debug("ALICE chose silence")
            self._last_narration_time = now
            return

        self._last_narration_time = now
        if self._personality is not None:
            self._personality.record_speech(topic=state.mode)
        await self._speak(text)

    def _build_prompt(self, state) -> Optional[str]:
        """Build a mode-specific prompt from current state."""
        from narration_prompts import (
            chimp_sort_prompt, puppeteer_prompt,
            calibration_prompt, mode_switch_prompt, rebellion_prompt,
            awaiting_puppeteer_prompt, auto_sort_prompt, auto_tetris_prompt
        )

        # Check for mode switch
        if self._last_mode is not None and self._last_mode != state.mode:
            old_mode = self._last_mode
            self._last_mode = state.mode
            return mode_switch_prompt(old_mode, state.mode)

        self._last_mode = state.mode

        if state.mode == "demo":
            if state.sort_state == "rebellion":
                return rebellion_prompt(
                    blocks_remaining=16 - len([b for b in state.detected_blocks
                                               if b.get("in_sorted_zone", False)]),
                    crowd_choice=state.rebellion_crowd_choice,
                    robot_choice=state.rebellion_robot_choice,
                    move_count=state.sort_move_count,
                )
            if state.sort_state == "awaiting_puppeteer":
                return awaiting_puppeteer_prompt()
            elapsed = time.time() - state.sort_start_time if state.sort_start_time else 0.0
            return chimp_sort_prompt(
                sort_state=state.sort_state,
                blocks_placed=len([b for b in state.detected_blocks
                                   if b.get("in_sorted_zone", False)]),
                total_blocks=len(state.detected_blocks) or 16,
                duration=elapsed,
                move_count=state.sort_move_count,
            )
        elif state.mode == "auto_sort":
            return auto_sort_prompt(
                phase=state.auto_sort_phase,
                cycle=state.auto_sort_cycle,
                blocks_detected=len(state.detected_blocks),
                move_count=state.sort_move_count,
            )
        elif state.mode == "auto_tetris":
            return auto_tetris_prompt(
                score=state.tetris_score,
                lines_cleared=state.tetris_lines,
                level=state.tetris_level,
                game_over=state.tetris_game_over,
            )
        elif state.mode == "puppeteer":
            return puppeteer_prompt(
                state=state.puppeteer_state,
                arm_angles=list(state.arm_position),
                recording=state.puppeteer_recording,
            )
        elif state.mode == "calibrate":
            return calibration_prompt(
                points_collected=state.calibration_points,
                transform_ready=state.calibration_ready,
            )
        return None

    LLM_TIMEOUT = 10.0

    async def _generate_text(self, prompt: str) -> Optional[str]:
        """Generate narration text using the configured backend."""
        if self._backend == "ollama" and self._ollama is not None:
            return await self._generate_ollama(prompt)
        elif self._backend == "gemini" and self._genai_model is not None:
            return await self._generate_gemini(prompt)
        else:
            return self._fallback_narration()

    async def _generate_ollama(self, prompt: str) -> Optional[str]:
        """Generate via local Ollama. Fast — typically <200ms for short responses."""
        try:
            text = await asyncio.wait_for(
                asyncio.to_thread(self._ollama.generate_sync, prompt),
                timeout=self.LLM_TIMEOUT,
            )
            if text:
                # Enforce ALICE's brevity — truncate to first sentence if too long
                text = self._enforce_brevity(text)
                return text
            return self._fallback_narration()
        except asyncio.TimeoutError:
            logger.warning(f"Ollama timed out after {self.LLM_TIMEOUT}s")
            return self._fallback_narration()
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return self._fallback_narration()

    async def _generate_gemini(self, prompt: str) -> Optional[str]:
        """Generate via Gemini API."""
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(self._genai_model.generate_content, prompt),
                timeout=self.LLM_TIMEOUT,
            )
            text = response.text.strip() if response and response.text else None
            if text:
                text = self._enforce_brevity(text)
                return text
            return self._fallback_narration()
        except asyncio.TimeoutError:
            logger.warning(f"Gemini API timed out after {self.LLM_TIMEOUT}s")
            return self._fallback_narration()
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return self._fallback_narration()

    @staticmethod
    def _enforce_brevity(text: str) -> str:
        """Enforce ALICE's 8-word max. Truncate gracefully if the LLM rambles."""
        # Strip quotes, asterisks, etc.
        text = text.strip().strip('"\'*')

        # Take first sentence only
        for sep in ['.', '!', '?', '\n']:
            if sep in text:
                text = text[:text.index(sep)].strip()
                break

        # Hard cap at 10 words (a little slack above the 8-word guideline)
        words = text.split()
        if len(words) > 10:
            text = ' '.join(words[:10])

        # Lowercase energy
        text = text.lower()

        return text

    def _fallback_narration(self) -> Optional[str]:
        """Rule-based first-person narration when no LLM is available."""
        if not self._state_manager:
            return None
        state = self._state_manager.state

        if self._personality is not None:
            if not self._personality.should_speak(topic=state.mode):
                return None

        if state.mode == "demo":
            if state.sort_state == "rebellion":
                if (state.rebellion_crowd_choice and state.rebellion_robot_choice
                        and state.rebellion_crowd_choice != state.rebellion_robot_choice):
                    return "no."
            elif state.sort_state == "complete":
                return None
        elif state.mode == "auto_sort":
            return None
        elif state.mode == "auto_tetris":
            return None
        elif state.mode == "puppeteer":
            return None
        elif state.mode == "calibrate":
            return None

        return None

    async def speak(self, text: str) -> None:
        """Have ALICE say something. Respects the voice gate cooldown."""
        self._last_narration_time = time.time()
        if self._personality is not None:
            self._personality.record_speech(topic=text[:20])
        await self._speak(text)

    async def speak_immediate(self, text: str) -> None:
        """Force ALICE to speak — bypasses voice gate. For scripted moments."""
        if self._personality is not None:
            self._personality.record_speech(topic="immediate")
        self._last_narration_time = time.time()
        await self._speak(text)

    async def _speak(self, text: str) -> None:
        """Speak text using pyttsx3 in a thread."""
        logger.info(f"ALICE: \"{text}\"")
        if not self._tts_engine:
            return
        try:
            await asyncio.to_thread(self._tts_speak_sync, text)
        except Exception as e:
            logger.error(f"TTS failed: {e}")

    def _tts_speak_sync(self, text: str) -> None:
        """Blocking TTS call — run via asyncio.to_thread."""
        self._tts_engine.say(text)
        self._tts_engine.runAndWait()
