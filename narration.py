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
        import time
        from narration_prompts import (
            chimp_sort_prompt, tetris_prompt, puppeteer_prompt,
            calibration_prompt, mode_switch_prompt, rebellion_prompt,
            awaiting_puppeteer_prompt
        )

        # Check for mode switch
        if self._last_mode is not None and self._last_mode != state.mode:
            old_mode = self._last_mode
            self._last_mode = state.mode
            return mode_switch_prompt(old_mode, state.mode)

        self._last_mode = state.mode

        if state.mode == "chimp":
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
        elif state.mode == "tetris":
            return tetris_prompt(
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

    async def _generate_text(self, prompt: str) -> Optional[str]:
        """Generate narration text using Gemini, or fall back to rule-based text."""
        if not self._genai_model:
            return self._fallback_narration()

        try:
            response = await asyncio.to_thread(
                self._genai_model.generate_content, prompt
            )
            return response.text.strip() if response and response.text else self._fallback_narration()
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return self._fallback_narration()

    def _fallback_narration(self) -> Optional[str]:
        """Rule-based narration when Gemini is unavailable."""
        if not self._state_manager:
            return None
        state = self._state_manager.state
        import time

        if state.mode == "chimp":
            if state.sort_state == "human_benchmark":
                elapsed = time.time() - state.sort_start_time if state.sort_start_time else 0
                return f"Human sorting in progress. {state.sort_move_count} moves in {elapsed:.0f} seconds."
            elif state.sort_state == "ghost_replay":
                return "Now replaying the human's sorting strategy."
            elif state.sort_state == "awaiting_puppeteer":
                return "Waiting for a volunteer to control the arm. Step up and move your hand."
            elif state.sort_state == "cyborg_coop":
                return f"Cyborg cooperation active. {state.sort_move_count} moves so far."
            elif state.sort_state == "rebellion":
                if state.rebellion_crowd_choice and state.rebellion_robot_choice:
                    if state.rebellion_crowd_choice != state.rebellion_robot_choice:
                        return (f"The audience voted block {state.rebellion_crowd_choice}. "
                                f"ALICE chose block {state.rebellion_robot_choice}. "
                                f"We gave her permission to decide.")
                return f"ALICE is sorting autonomously. {state.sort_move_count} moves, ignoring all suggestions."
            elif state.sort_state == "complete":
                return "Sorting complete. Well done, team."
        elif state.mode == "tetris":
            if state.tetris_game_over:
                return f"Game over. Final score: {state.tetris_score}, {state.tetris_lines} lines cleared."
            return f"Tetris level {state.tetris_level}. Score: {state.tetris_score}, {state.tetris_lines} lines."
        elif state.mode == "puppeteer":
            if state.puppeteer_recording:
                return "Recording arm motion for later playback."
            return f"Puppeteer mode: {state.puppeteer_state}."
        elif state.mode == "calibrate":
            return f"Calibration: {state.calibration_points} points collected."

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
