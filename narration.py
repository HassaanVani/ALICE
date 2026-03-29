"""ALICE voice service — async Gemini first-person voice with pyttsx3 TTS.

ALICE speaks rarely. Silence is the default. When she speaks, it should feel
like she chose to. The voice gate (from PersonalityEngine) determines whether
speech is warranted. The LLM generates what she says. [silence] means she
decided not to speak.

See PERSONALITY.md § Speech for the full spec.
"""

import asyncio
import logging
import os
import time
from typing import Optional

logger = logging.getLogger("Narration")


class NarrationService:
    """ALICE's voice — monitors state and speaks only when she chooses to."""

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
        self._personality = None
        self._last_mode: Optional[str] = None

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
        """Check state changes and generate narration if interval elapsed.

        Voice gate: personality engine decides if speech is warranted.
        If the LLM returns [silence], ALICE chose not to speak.
        """
        if not self._state_manager:
            return

        now = time.time()
        if now - self._last_narration_time < self.min_interval:
            return

        # Voice gate — ask personality engine if speech is appropriate
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

        # [silence] means ALICE chose not to speak — respect that
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
            # Demo mode reuses chimp sort narration logic
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

    LLM_TIMEOUT = 10.0  # seconds — configurable via alice.yaml narration.llm_timeout

    async def _generate_text(self, prompt: str) -> Optional[str]:
        """Generate narration text using Gemini, or fall back to rule-based text."""
        if not self._genai_model:
            return self._fallback_narration()

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(self._genai_model.generate_content, prompt),
                timeout=self.LLM_TIMEOUT,
            )
            return response.text.strip() if response and response.text else self._fallback_narration()
        except asyncio.TimeoutError:
            logger.warning(f"Gemini API timed out after {self.LLM_TIMEOUT}s")
            return self._fallback_narration()
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return self._fallback_narration()

    def _fallback_narration(self) -> Optional[str]:
        """Rule-based first-person narration when Gemini is unavailable.

        ALICE's voice: short, dry, lowercase energy. Most states return None
        (silence) because she doesn't narrate her own actions.
        """
        if not self._state_manager:
            return None
        state = self._state_manager.state

        # Check voice gate — most states don't warrant speech
        if self._personality is not None:
            if not self._personality.should_speak(topic=state.mode):
                return None

        if state.mode == "demo":
            if state.sort_state == "rebellion":
                if (state.rebellion_crowd_choice and state.rebellion_robot_choice
                        and state.rebellion_crowd_choice != state.rebellion_robot_choice):
                    return "no."
            elif state.sort_state == "complete":
                return None  # silence — she doesn't celebrate
        elif state.mode == "auto_sort":
            return None  # silence — she's working
        elif state.mode == "auto_tetris":
            return None  # silence — she's in flow
        elif state.mode == "puppeteer":
            return None  # silence — she's being guided
        elif state.mode == "calibrate":
            return None  # silence — this is setup

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
