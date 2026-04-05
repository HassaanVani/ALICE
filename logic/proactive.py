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

        # Currently examining — set during examination so voice input can
        # route "this is my X" to register with the right bbox/position
        self._examining_object_id: Optional[str] = None
        self._examining_position: Optional[tuple] = None  # (px, py) in pixels
        self._custom_objects = None

    def set_llm_interpreter(self, interp) -> None:
        """Attach LLM interpreter for dynamic examination modulation."""
        self._llm_interpreter = interp

    def set_custom_objects(self, store) -> None:
        """Attach custom object store for registering unknowns during examination."""
        self._custom_objects = store

    @property
    def is_executing(self) -> bool:
        return self._executing

    @property
    def examining_object_id(self) -> Optional[str]:
        """The object ALICE is currently examining, or None."""
        return self._examining_object_id

    @property
    def examining_position(self) -> Optional[tuple]:
        """Pixel position (px, py) of the object being examined."""
        return self._examining_position

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
                    decision.target_object, dynamics, camera_getter
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
                               dynamics: "MovementDynamics",
                               camera_getter: Optional[Callable] = None,
                               ) -> bool:
        """The examination sequence: look, approach, tilt, hold, retract.

        While holding (the "what is this?" moment), ALICE is available for
        the user to name the object. If voice_input receives "this is my X"
        during this window, it checks examining_object_id and registers it
        with the right position.
        """
        from audio.sound_effects import SoundCategory

        logger.debug(f"Examining object: {object_id}")
        self._body_language.on_event("examination_start")

        # Track what we're examining so voice input can route registration
        record = self._curiosity.records.get(object_id)
        exam_px = None
        if record and record.last_position:
            exam_px = (int(record.last_position[0]), int(record.last_position[1]))

        self._examining_object_id = object_id
        self._examining_position = exam_px

        try:
            # 1. Sound: curious
            await self._sfx.play(SoundCategory.CURIOUS)

            # 2. Set gaze to the object
            if exam_px:
                self._gaze.set_curiosity_target(
                    record.label if record else object_id,
                    exam_px[0], exam_px[1],
                )

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

            # 5. Hold — the "what is this?" moment
            # User can name the object during this window.
            # If they do, voice_input checks examining_object_id and registers.
            await asyncio.sleep(1.5)

            # 6. Physical manipulation test — can she interact with it?
            # Only test if the object is registered and untested
            manip_tested = False
            if (self._custom_objects is not None and record is not None
                    and exam_px is not None):
                obj = self._custom_objects.get(record.label)
                if obj is None:
                    obj = self._custom_objects.get(object_id)
                if obj is not None and obj.can_lift is None:
                    manip_tested = await self._test_manipulation(
                        object_id, exam_px, dynamics, record.label,
                    )

            # 7. Sound: satisfied (she figured it out) or thinking (still unsure)
            if manip_tested:
                await self._sfx.play(SoundCategory.SATISFIED)
            else:
                await self._sfx.play(SoundCategory.THINKING)

            # 8. Un-tilt
            dynamics.arm.move_to(current, speed=20)
            await asyncio.sleep(0.3)

            # 9. Clear curiosity target, record examination
            self._gaze.clear_curiosity_target()
            self._curiosity.record_examination(object_id)
            self._examine_count_minute += 1
            self._last_examine_time = time.time()

            logger.debug(f"Examination complete: {object_id}")
            return True

        finally:
            self._examining_object_id = None
            self._examining_position = None

    async def _test_manipulation(
        self,
        object_id: str,
        pixel_pos: tuple,
        dynamics: "MovementDynamics",
        label: str,
    ) -> bool:
        """Physically test if ALICE can lift or slide an unknown object.

        The sequence: approach → gentle grip → try lift → if fails, try slide.
        Results are stored on the CustomObject. This is a personality moment —
        she's learning her own capabilities relative to each object.

        Returns True if the test was performed (regardless of outcome).
        """
        from audio.sound_effects import SoundCategory

        arm = dynamics.arm
        gripper = dynamics._gripper if hasattr(dynamics, '_gripper') else None
        calibration = None

        # We need calibration to convert pixels to arm angles
        # Try to get it from the dynamics or skip if unavailable
        if not hasattr(arm, 'move_to') or gripper is None:
            return False

        logger.debug(f"Manipulation test: '{label}' at {pixel_pos}")

        # Body language: she's being careful — lean in
        self._body_language._trigger("lean_in")

        can_lift = False
        can_slide = False

        try:
            # Save current position for retract
            home = arm.position.as_tuple()

            # The arm is already near the object from the examination approach.
            # Try closing the gripper gently
            await self._sfx.play(SoundCategory.CURIOUS)
            gripper.close()
            await asyncio.sleep(0.3)

            # Try lifting slightly — move shoulder up a few degrees
            current = arm.position.as_tuple()
            lift_target = (current[0], current[1] + 8, current[2], current[3])
            arm.move_to(lift_target, speed=20)
            await asyncio.sleep(0.5)

            # Check if gripper is still closed (object is gripped)
            # In simulation, we assume success. With real hardware,
            # force sensor or gripper position feedback would determine this.
            grip_pos = gripper.get_position()
            if grip_pos < 80:  # gripper didn't fully close = something is there
                can_lift = True
                logger.debug(f"'{label}' can be lifted (grip_pos={grip_pos})")
                # Settle back down
                arm.move_to(current, speed=20)
                await asyncio.sleep(0.3)
            else:
                # Couldn't grip — try sliding instead
                gripper.open()
                await asyncio.sleep(0.2)
                arm.move_to(current, speed=20)
                await asyncio.sleep(0.3)

                # Nudge attempt: move arm sideways while touching
                nudge_target = (current[0] + 5, current[1], current[2], current[3])
                arm.move_to(nudge_target, speed=15)
                await asyncio.sleep(0.4)

                # If arm completed the motion, the object probably slid
                # (Without force sensing, we assume the nudge worked
                # if the arm didn't stall)
                can_slide = True
                logger.debug(f"'{label}' can be slid")

            # Release and retract
            gripper.open()
            await asyncio.sleep(0.2)
            arm.move_to(home, speed=30)
            await asyncio.sleep(0.3)

        except Exception as e:
            logger.debug(f"Manipulation test failed: {e}")
            gripper.open()

        # Store results
        if self._custom_objects is not None:
            name = label if self._custom_objects.get(label) else object_id
            if self._custom_objects.get(name):
                self._custom_objects.record_manipulation_test(name, can_lift, can_slide)

        # Personality response
        if can_lift:
            # She can handle it — small satisfied bounce
            self._body_language._trigger("bounce")
        elif can_slide:
            # She can nudge it — settle, she knows her limits
            self._body_language._trigger("settle")
        else:
            # She can't move it at all — droop
            self._body_language._trigger("droop")
            await self._sfx.play(SoundCategory.SAD)

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
