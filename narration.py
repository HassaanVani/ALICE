"""LLM narration service — async Gemini commentary with pyttsx3 TTS."""

import asyncio
import logging
import os
import time
from typing import Optional

logger = logging.getLogger("Narration")


class NarrationService:
    """Async loop that monitors state changes and produces voice narration."""

    def __init__(self, enabled: bool = False, voice_rate: int = 175,
                 min_interval: int = 8, model: str = "gemini-pro"):
        self.enabled = enabled
        self.voice_rate = voice_rate
        self.min_interval = min_interval
        self.model_name = model

        self._last_narration_time: float = 0.0
        self._running = False
        self._tts_engine = None
        self._genai_model = None
        self._state_manager = None
        self._last_mode: Optional[str] = None

    def set_state_manager(self, state_manager) -> None:
        self._state_manager = state_manager

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
        api_key = os.environ.get("ALICE_GEMINI_KEY")
        if not api_key:
            logger.warning("ALICE_GEMINI_KEY not set — narration LLM disabled")
            return False
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._genai_model = genai.GenerativeModel(self.model_name)
            logger.info(f"Gemini model '{self.model_name}' initialized")
            return True
        except Exception as e:
            logger.warning(f"Gemini init failed: {e}")
            return False

    async def start(self) -> None:
        """Start the narration monitoring loop."""
        if not self.enabled:
            logger.info("Narration disabled")
            return

        self._init_tts()
        self._init_llm()
        self._running = True

        logger.info("Narration service started")

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

        state = self._state_manager.state
        prompt = self._build_prompt(state)
        if not prompt:
            return

        text = await self._generate_text(prompt)
        if text:
            self._last_narration_time = now
            await self._speak(text)

    def _build_prompt(self, state) -> Optional[str]:
        """Build a mode-specific prompt from current state."""
        from narration_prompts import (
            chimp_sort_prompt, tetris_prompt, puppeteer_prompt,
            calibration_prompt, mode_switch_prompt
        )

        # Check for mode switch
        if self._last_mode is not None and self._last_mode != state.mode:
            self._last_mode = state.mode
            return mode_switch_prompt(self._last_mode, state.mode)

        self._last_mode = state.mode

        if state.mode == "chimp":
            return chimp_sort_prompt(
                sort_state=state.sort_state,
                blocks_placed=len([b for b in state.detected_blocks
                                   if b.get("in_sorted_zone", False)]),
                total_blocks=16,
                duration=0.0,
                move_count=0,
            )
        elif state.mode == "tetris":
            return tetris_prompt(
                score=state.tetris_score,
                lines_cleared=0,
                level=1,
                game_over=False,
            )
        elif state.mode == "puppeteer":
            return puppeteer_prompt(
                state=state.puppeteer_state,
                arm_angles=list(state.arm_position),
                recording=False,
            )
        elif state.mode == "calibrate":
            return calibration_prompt(
                points_collected=0,
                transform_ready=False,
            )
        return None

    async def _generate_text(self, prompt: str) -> Optional[str]:
        """Generate narration text using Gemini."""
        if not self._genai_model:
            # Fallback: return a static message
            return None

        try:
            response = await asyncio.to_thread(
                self._genai_model.generate_content, prompt
            )
            return response.text.strip() if response and response.text else None
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return None

    async def _speak(self, text: str) -> None:
        """Speak text using pyttsx3 in a thread."""
        logger.info(f"Narrating: {text}")
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
