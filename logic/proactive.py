"""Proactive engagement — the orchestrator that makes ALICE feel alive when idle.

Coordinates gaze tracking, curiosity, habits, body language, and sound effects
into coherent idle-time behaviors. ALICE doesn't just sit — she looks around,
examines new things, acts on learned habits, and occasionally engages the user.

Decision hierarchy:
  1. Curiosity: high-curiosity object → examine it
  2. Habits: triggered habit → execute it
  3. User presence: someone idle nearby → look at them
  4. Ambient scan: nothing happening → slow sweep
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from hardware.arm_controller import ArmController
    from hardware.dynamics import MovementDynamics
    from logic.body_language import BodyLanguage
    from logic.curiosity import CuriosityEngine
    from logic.gaze_tracker import GazeTracker
    from logic.habits import HabitEngine, Habit
    from logic.personality import PersonalityEngine
    from logic.object_memory import ObjectMemory
    from audio.sound_effects import SoundEffects, SoundCategory
    from narration import NarrationService
    from hardware import CalibrationManager
    from vision.presence import PresenceInfo

logger = logging.getLogger("Proactive")


class EngagementAction(Enum):
    NONE = "none"
    EXAMINE_OBJECT = "examine"
    LOOK_AT_USER = "look_at_user"
    EXECUTE_HABIT = "habit"
    AMBIENT_SCAN = "scan"


@dataclass
class EngagementDecision:
    action: EngagementAction
    target_object: Optional[str] = None
    habit: Optional["Habit"] = None
    priority: float = 0.0


class ProactiveEngagement:
    """Orchestrates all living behavior systems during idle time.

    Usage:
        proactive = ProactiveEngagement(curiosity, habits, gaze, ...)
        decision = proactive.decide(presence_info)
        if decision.action != EngagementAction.NONE:
            await proactive.execute(decision, dynamics, arm, ...)
    """

    MIN_ACTION_INTERVAL = 6.0      # seconds between proactive actions
    MAX_EXAMINE_PER_MINUTE = 2     # don't over-examine
    SCAN_INTERVAL = 10.0           # seconds between ambient scans
    USER_LOOK_INTERVAL = 15.0      # seconds between "glance at user"

    def __init__(
        self,
        curiosity: "CuriosityEngine",
        habits: "HabitEngine",
        gaze: "GazeTracker",
        body_language: "BodyLanguage",
        sound_effects: "SoundEffects",
        personality: "PersonalityEngine",
        object_memory: "ObjectMemory",
    ):
        self._curiosity = curiosity
        self._habits = habits
        self._gaze = gaze
        self._body_language = body_language
        self._sfx = sound_effects
        self._personality = personality
        self._object_memory = object_memory

        self._last_action_time: float = 0.0
        self._last_examine_time: float = 0.0
        self._examine_count_minute: int = 0
        self._examine_minute_start: float = 0.0
        self._last_look_time: float = 0.0
        self._executing = False
        self._llm_interpreter = None

    def set_llm_interpreter(self, interp) -> None:
        """Attach LLM interpreter for dynamic examination modulation."""
        self._llm_interpreter = interp

    @property
    def is_executing(self) -> bool:
        return self._executing

    def decide(self, presence_info: Optional["PresenceInfo"] = None) -> EngagementDecision:
        """Decide what ALICE should do right now. Returns NONE most of the time."""
        now = time.time()

        if self._executing:
            return EngagementDecision(action=EngagementAction.NONE)

        if now - self._last_action_time < self.MIN_ACTION_INTERVAL:
            return EngagementDecision(action=EngagementAction.NONE)

        # Reset per-minute examine counter
        if now - self._examine_minute_start > 60.0:
            self._examine_count_minute = 0
            self._examine_minute_start = now

        # 1. Curiosity — examine the most interesting object
        if self._examine_count_minute < self.MAX_EXAMINE_PER_MINUTE:
            most_curious = self._curiosity.get_most_curious()
            if most_curious is not None:
                return EngagementDecision(
                    action=EngagementAction.EXAMINE_OBJECT,
                    target_object=most_curious.object_id,
                    priority=most_curious.curiosity_level,
                )

        # 2. Habits — execute triggered habits
        current_objects = self._object_memory.objects
        mood = self._personality.state.overall_mood
        triggered = self._habits.get_triggered_habits(current_objects, mood)
        if triggered:
            strongest = max(triggered, key=lambda h: h.strength)
            return EngagementDecision(
                action=EngagementAction.EXECUTE_HABIT,
                habit=strongest,
                priority=strongest.strength,
            )

        # 3. Glance at user if present
        if (presence_info is not None and presence_info.detected and
                now - self._last_look_time > self.USER_LOOK_INTERVAL):
            return EngagementDecision(
                action=EngagementAction.LOOK_AT_USER,
                priority=0.3,
            )

        return EngagementDecision(action=EngagementAction.NONE)

    async def execute(
        self,
        decision: EngagementDecision,
        dynamics: "MovementDynamics",
        arm: "ArmController",
        calibration: Optional["CalibrationManager"] = None,
        camera_getter: Optional[Callable] = None,
        narration: Optional["NarrationService"] = None,
    ) -> bool:
        """Execute the chosen engagement action. Returns True on success."""
        if decision.action == EngagementAction.NONE:
            return False

        self._executing = True
        self._last_action_time = time.time()

        try:
            if decision.action == EngagementAction.EXAMINE_OBJECT:
                return await self._examine_object(
                    decision.target_object, dynamics
                )
            elif decision.action == EngagementAction.EXECUTE_HABIT:
                return await self._execute_habit(
                    decision.habit, dynamics, arm, calibration, camera_getter
                )
            elif decision.action == EngagementAction.LOOK_AT_USER:
                return await self._look_at_user(dynamics)
            return False
        except Exception as e:
            logger.debug(f"Engagement action failed: {e}")
            return False
        finally:
            self._executing = False

    async def _examine_object(self, object_id: str,
                               dynamics: "MovementDynamics") -> bool:
        """The examination sequence: look, approach, tilt, hold, retract."""
        from audio.sound_effects import SoundCategory

        logger.debug(f"Examining object: {object_id}")
        self._body_language.on_event("examination_start")

        # 1. Sound: curious
        await self._sfx.play(SoundCategory.CURIOUS)

        # 2. Set gaze to the object
        record = self._curiosity.records.get(object_id)
        if record and record.last_position:
            px, py = record.last_position[0], record.last_position[1]
            self._gaze.set_curiosity_target(record.label, int(px), int(py))

        # 3. Let gaze tracking move the arm toward it (several ticks)
        for _ in range(8):
            await self._gaze.apply(dynamics)
            await asyncio.sleep(0.1)

        # 4. Small tilt — the "head tilt" of curiosity (LLM-modulated)
        current = dynamics.arm.position.as_tuple()
        tilt_amount = 8.0
        approach_speed = 25
        if self._llm_interpreter is not None:
            tilt_amount *= self._llm_interpreter.modifiers.tilt
            approach_speed = int(approach_speed * self._llm_interpreter.modifiers.appr)
        tilted = (current[0], current[1], current[2], current[3] + tilt_amount)
        dynamics.arm.move_to(tilted, speed=approach_speed)
        await asyncio.sleep(0.5)

        # 5. Hold — forming an opinion
        await asyncio.sleep(0.4)

        # 6. Sound: satisfied or thinking
        await self._sfx.play(SoundCategory.SATISFIED)

        # 7. Un-tilt
        dynamics.arm.move_to(current, speed=20)
        await asyncio.sleep(0.3)

        # 8. Clear curiosity target, record examination
        self._gaze.clear_curiosity_target()
        self._curiosity.record_examination(object_id)
        self._examine_count_minute += 1
        self._last_examine_time = time.time()

        logger.debug(f"Examination complete: {object_id}")
        return True

    async def _execute_habit(self, habit: "Habit",
                              dynamics: "MovementDynamics",
                              arm: "ArmController",
                              calibration: Optional["CalibrationManager"],
                              camera_getter: Optional[Callable]) -> bool:
        """Execute a learned habit behavior."""
        from audio.sound_effects import SoundCategory

        logger.debug(f"Executing habit: {habit.trigger}")

        if habit.action == "nudge_to_position":
            # Look toward the object first
            oid = habit.action_data.get("object_id", "")
            target_pos = habit.action_data.get("target_position")
            if not target_pos:
                return False

            await self._sfx.play(SoundCategory.THINKING)

            # Orient toward the object
            self._gaze.set_curiosity_target(oid, int(target_pos[0]), int(target_pos[1]))
            for _ in range(5):
                await self._gaze.apply(dynamics)
                await asyncio.sleep(0.1)
            self._gaze.clear_curiosity_target()

            await self._sfx.play(SoundCategory.ACKNOWLEDGE)
            self._habits.record_execution(habit.habit_id)
            return True

        elif habit.action == "orient_toward":
            # Just look toward the second object (anticipation)
            oid = habit.action_data.get("object_id", "")
            obj = self._object_memory.objects.get(oid)
            if obj and obj.last_seen_position:
                px, py = obj.last_seen_position[0], obj.last_seen_position[1]
                self._gaze.set_curiosity_target(oid, int(px), int(py))

                for _ in range(6):
                    await self._gaze.apply(dynamics)
                    await asyncio.sleep(0.1)

                self._gaze.clear_curiosity_target()

            self._habits.record_execution(habit.habit_id)
            return True

        elif habit.action == "nudge_together":
            await self._sfx.play(SoundCategory.THINKING)
            self._habits.record_execution(habit.habit_id)
            return True

        return False

    async def _look_at_user(self, dynamics: "MovementDynamics") -> bool:
        """Glance at the user — the "I see you" moment."""
        from audio.sound_effects import SoundCategory

        self._last_look_time = time.time()

        # The gaze tracker will naturally track the face, so just
        # let it run for a moment and add a small sound
        for _ in range(10):
            await self._gaze.apply(dynamics)
            await asyncio.sleep(0.1)

        # Tiny acknowledge chirp
        await self._sfx.play(SoundCategory.ACKNOWLEDGE)

        self._body_language.on_event("new_person")
        return True
