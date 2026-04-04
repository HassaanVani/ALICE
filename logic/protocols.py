"""Protocol registry — named movement protocols that Llama selects from.

Each protocol is a named, executable action with a declared parameter schema.
The registry holds all protocols. The selector resolves natural language to a
protocol + params using a two-tier strategy: regex fast-path, then LLM fallback.

Existing implementations (ObjectInteraction, TeaChoreography, FistBumpInteraction,
etc.) are wrapped — not rewritten. Each wrapper is a thin adapter (~15-25 lines)
that normalizes the interface to Protocol.execute(params, ctx) -> InteractionResult.

The LLM movement interpreter (llm_interpreter.py) coexists with this system:
protocols decide WHAT to do, the interpreter tunes HOW it feels while doing it.
"""

import abc
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from logic.object_interaction import InteractionResult

logger = logging.getLogger("Protocols")


# ── Core types ───────────────────────────────────────────────────

@dataclass
class ProtocolParam:
    """Schema for a single protocol parameter."""
    type: str           # "string"
    required: bool
    description: str


@dataclass
class ProtocolSpec:
    """Metadata for a protocol — used to generate LLM tool prompts."""
    name: str
    description: str
    params: Dict[str, ProtocolParam] = field(default_factory=dict)


@dataclass
class ProtocolContext:
    """Shared dependencies passed to Protocol.execute() per call."""
    arm: Any
    gripper: Any
    calibration: Any
    dynamics: Any
    personality: Any
    narration: Any
    camera_getter: Callable
    yolo_detector: Any
    state_manager: Any
    object_memory: Any = None
    presence_detector: Any = None
    running_check: Optional[Callable[[], bool]] = None


class Protocol(abc.ABC):
    """Base class for all ALICE protocols."""

    @abc.abstractmethod
    def spec(self) -> ProtocolSpec:
        """Return the protocol's metadata and parameter schema."""
        ...

    @abc.abstractmethod
    async def execute(self, params: Dict[str, Any],
                      ctx: ProtocolContext) -> InteractionResult:
        """Run the protocol. Returns standardized result."""
        ...


# ── Registry ─────────────────────────────────────────────────────

class ProtocolRegistry:
    """Holds all registered protocols. Provides lookup and LLM prompt generation."""

    def __init__(self):
        self._protocols: Dict[str, Protocol] = {}

    def register(self, protocol: Protocol) -> None:
        name = protocol.spec().name
        self._protocols[name] = protocol
        logger.debug(f"Registered protocol: {name}")

    def get(self, name: str) -> Optional[Protocol]:
        return self._protocols.get(name)

    def list_specs(self) -> List[ProtocolSpec]:
        return [p.spec() for p in self._protocols.values()]

    @property
    def names(self) -> List[str]:
        return list(self._protocols.keys())

    def tool_prompt(self, visible_objects: Optional[List[str]] = None) -> str:
        """Generate a compact LLM prompt listing all user-facing protocols."""
        lines = [
            'Pick ONE tool. Output ONLY JSON: {"tool":"<name>","params":{...}}',
        ]
        if visible_objects:
            lines.append(f"Objects visible: {', '.join(visible_objects)}")
        lines.append("Tools:")
        for spec in self.list_specs():
            param_str = ", ".join(
                f"{k}{'?' if not v.required else ''}"
                for k, v in spec.params.items()
            )
            lines.append(f"- {spec.name}({param_str}) — {spec.description}")
        return "\n".join(lines)


# ── Selector (regex fast-path + LLM fallback) ───────────────────

# Maps CommandParser action names to protocol names
_ACTION_TO_PROTOCOL = {
    "fetch": "fetch",
    "hand_over": "hand_over",
    "move_near": "place_beside",
    "throw_away": "throw_away",
    "nudge": "nudge",
    "organize": "organize",
}

_TOOL_JSON_RE = re.compile(r'\{(?:[^{}]|\{[^{}]*\})*\}')


class ProtocolSelector:
    """Resolves natural language to (protocol_name, params).

    Tier 1: Regex fast-path via CommandParser (0ms, no LLM).
    Tier 2: Ollama LLM call with tool-use prompt (~100-200ms).
    """

    def __init__(self, registry: ProtocolRegistry,
                 command_parser=None, ollama_generate=None):
        """
        Args:
            registry: The protocol registry (for tool_prompt generation).
            command_parser: A CommandParser instance (from voice_input.py).
            ollama_generate: An async callable(prompt: str) -> str for LLM queries.
                             If None, tier 2 is disabled.
        """
        self._registry = registry
        self._parser = command_parser
        self._ollama_generate = ollama_generate

    async def select(self, text: str,
                     visible_objects: Optional[List[str]] = None,
                     ) -> Optional[Tuple[str, dict]]:
        """Resolve text to (protocol_name, params). Returns None if unresolvable."""
        # Tier 1: regex
        if self._parser is not None:
            result = self._try_regex(text)
            if result is not None:
                return result

        # Tier 2: LLM
        if self._ollama_generate is not None:
            return await self._try_llm(text, visible_objects)

        return None

    def _try_regex(self, text: str) -> Optional[Tuple[str, dict]]:
        """Use CommandParser regex patterns to resolve."""
        cmd = self._parser.parse(text)
        if cmd.action == "unknown":
            return None

        protocol_name = _ACTION_TO_PROTOCOL.get(cmd.action)
        if protocol_name is None:
            return None

        params = {}
        if cmd.source_label:
            if protocol_name == "place_beside":
                params["source"] = cmd.source_label
                if cmd.target_label:
                    params["target"] = cmd.target_label
            elif protocol_name == "nudge":
                params["object"] = cmd.source_label
                if cmd.target_label:
                    params["direction"] = cmd.target_label
            else:
                params["object"] = cmd.source_label

        return (protocol_name, params)

    async def _try_llm(self, text: str,
                       visible_objects: Optional[List[str]] = None,
                       ) -> Optional[Tuple[str, dict]]:
        """Use Ollama to select a protocol via tool-use prompt."""
        prompt = self._registry.tool_prompt(visible_objects)
        prompt += f'\nUser: "{text}"\n'

        try:
            raw = await self._ollama_generate(prompt)
        except Exception as e:
            logger.debug(f"Protocol selector LLM error: {e}")
            return None

        if not raw:
            return None

        return self._parse_llm_response(raw)

    def _parse_llm_response(self, raw: str) -> Optional[Tuple[str, dict]]:
        """Extract {"tool": "...", "params": {...}} from LLM output."""
        match = _TOOL_JSON_RE.search(raw)
        if not match:
            return None

        try:
            data = json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            return None

        tool_name = data.get("tool")
        if not tool_name or tool_name not in self._registry.names:
            return None

        params = data.get("params", {})
        if not isinstance(params, dict):
            params = {}

        # Validate required params
        spec = self._registry.get(tool_name).spec()
        for param_name, param_spec in spec.params.items():
            if param_spec.required and param_name not in params:
                logger.debug(f"LLM missing required param '{param_name}' for '{tool_name}'")
                return None

        return (tool_name, params)


# ── Concrete protocol wrappers ───────────────────────────────────

class FetchProtocol(Protocol):
    def __init__(self, interaction):
        self._interaction = interaction

    def spec(self):
        return ProtocolSpec("fetch", "pick up an object and place it in front of you", {
            "object": ProtocolParam("string", True, "object to fetch"),
        })

    async def execute(self, params, ctx):
        return await self._interaction.fetch(params["object"], ctx.camera_getter)


class HandOverProtocol(Protocol):
    def __init__(self, interaction):
        self._interaction = interaction

    def spec(self):
        return ProtocolSpec("hand_over", "pick up and hold in the air for the user to grab from ALICE's gripper — used when user says pass me or give me or hand me", {
            "object": ProtocolParam("string", True, "object to hand over"),
        })

    async def execute(self, params, ctx):
        return await self._interaction.hand_over(params["object"], ctx.camera_getter)


class MoveNearProtocol(Protocol):
    def __init__(self, interaction):
        self._interaction = interaction

    def spec(self):
        return ProtocolSpec("place_beside", "pick up one object and put it next to another", {
            "source": ProtocolParam("string", True, "object to pick up"),
            "target": ProtocolParam("string", True, "object to place it next to"),
        })

    async def execute(self, params, ctx):
        return await self._interaction.move_near(
            params["source"], params["target"], ctx.camera_getter,
        )


class ThrowAwayProtocol(Protocol):
    def __init__(self, interaction):
        self._interaction = interaction

    def spec(self):
        return ProtocolSpec("throw_away", "discard an object in the trash", {
            "object": ProtocolParam("string", True, "object to discard"),
        })

    async def execute(self, params, ctx):
        return await self._interaction.throw_away(params["object"], ctx.camera_getter)


class NudgeProtocol(Protocol):
    def __init__(self, interaction):
        self._interaction = interaction

    # Direction → pixel offset
    _DIR_MAP = {
        "left": (-80, 0),
        "right": (80, 0),
        "forward": (0, -80),
        "back": (0, 80),
    }

    def spec(self):
        return ProtocolSpec("nudge", "gently push an object without picking it up", {
            "object": ProtocolParam("string", True, "object to push"),
            "direction": ProtocolParam("string", True, "left, right, forward, or back"),
        })

    async def execute(self, params, ctx):
        direction = params.get("direction", "right").lower()
        dx, dy = self._DIR_MAP.get(direction, (80, 0))
        return await self._interaction.nudge(
            params["object"], ctx.camera_getter, dx_px=dx, dy_px=dy,
        )


class OrganizeProtocol(Protocol):
    def spec(self):
        return ProtocolSpec("organize", "tidy desk to a layout (studying/drawing/working/clean)", {
            "preset": ProtocolParam("string", False, "layout name"),
        })

    async def execute(self, params, ctx):
        from logic.desk_presets import get_preset
        from logic.desk_organizer import DeskOrganizer

        preset_name = params.get("preset", "clean")
        preset = get_preset(preset_name)
        if preset is None:
            return InteractionResult(
                success=False, action="organize", object_label="desk",
                message=f"unknown preset: {preset_name}",
            )

        frame = ctx.camera_getter()
        detections = []
        if frame is not None and ctx.yolo_detector is not None:
            detections = ctx.yolo_detector.detect(frame)

        organizer = DeskOrganizer()
        plan = organizer.create_plan(preset, detections)
        if plan.total_moves == 0:
            return InteractionResult(
                success=True, action="organize", object_label="desk",
                message="desk already matches preset",
            )

        success = await organizer.execute_plan(
            ctx.arm, ctx.gripper, ctx.calibration,
            dynamics=ctx.dynamics, personality=ctx.personality,
            running_check=ctx.running_check,
        )
        return InteractionResult(
            success=success, action="organize", object_label="desk",
            message=f"organized to {preset_name}" if success else "incomplete",
        )


class TeaGuardProtocol(Protocol):
    def spec(self):
        return ProtocolSpec("guard_spill", "move a drink away from the laptop to prevent spills", {})

    async def execute(self, params, ctx):
        from logic.tea_choreography import TeaChoreography

        tea = TeaChoreography()
        try:
            success = await tea.execute(
                arm=ctx.arm, gripper=ctx.gripper, calibration=ctx.calibration,
                dynamics=ctx.dynamics, personality=ctx.personality,
                narration=ctx.narration, camera_getter=ctx.camera_getter,
                yolo_detector=ctx.yolo_detector, running_check=ctx.running_check,
            )
        except Exception as e:
            logger.error(f"Tea guard failed: {e}")
            success = False

        return InteractionResult(
            success=success, action="guard_spill", object_label="cup",
        )


class FistBumpProtocol(Protocol):
    """Wraps the stateful FistBumpInteraction. Supports reactive and initiated modes."""

    def __init__(self):
        from logic.fist_bump import FistBumpInteraction
        self._fb = FistBumpInteraction()

    def spec(self):
        return ProtocolSpec("fist_bump", "respond to or offer a fist bump", {
            "mode": ProtocolParam("string", False, "reactive or initiate"),
        })

    async def execute(self, params, ctx):
        mode = params.get("mode", "reactive")

        if mode == "initiate":
            success = await self._fb.initiate_bump(
                camera_getter=ctx.camera_getter,
                arm=ctx.arm, dynamics=ctx.dynamics,
                personality=ctx.personality, narration=ctx.narration,
                state_manager=ctx.state_manager,
            )
        else:
            frame = ctx.camera_getter()
            success = await self._fb.check_and_respond(
                frame, arm=ctx.arm, dynamics=ctx.dynamics,
                personality=ctx.personality, narration=ctx.narration,
                state_manager=ctx.state_manager,
            )

        return InteractionResult(
            success=success, action="fist_bump", object_label="",
        )

    @property
    def inner(self):
        """Access the underlying FistBumpInteraction for cooldown checks etc."""
        return self._fb

    def shutdown(self):
        self._fb.shutdown()


class WakeScanProtocol(Protocol):
    def spec(self):
        return ProtocolSpec("scan_desk", "look around and identify all objects on the desk", {})

    async def execute(self, params, ctx):
        from logic.wake_scan import WakeScanRoutine

        routine = WakeScanRoutine()
        result = await routine.execute(
            arm=ctx.arm, camera_getter=ctx.camera_getter,
            yolo_detector=ctx.yolo_detector,
            object_memory=ctx.object_memory,
            running_check=ctx.running_check,
        )
        return InteractionResult(
            success=True, action="scan_desk", object_label="desk",
            message=f"{len(result.objects_found)} objects found",
        )


class TeachProtocol(Protocol):
    """Wraps TeachingSession. Supports start/record/stop lifecycle."""

    def __init__(self):
        self._session = None

    def spec(self):
        return ProtocolSpec("teach", "user physically guides ALICE to learn where an object should go — triggered by teach or train or learn", {
            "object": ProtocolParam("string", True, "object to learn placement for"),
        })

    async def execute(self, params, ctx):
        from logic.teaching import TeachingSession

        if self._session is None:
            kinesthetic = None
            if ctx.arm and hasattr(ctx.arm, 'kinesthetic'):
                kinesthetic = ctx.arm.kinesthetic
            self._session = TeachingSession(
                kinesthetic_teacher=kinesthetic,
                object_memory=ctx.object_memory,
                calibration=ctx.calibration,
            )

        label = params.get("object", "unknown")

        if not self._session._active:
            self._session.start(label)
            return InteractionResult(
                success=True, action="teach", object_label=label,
                message=f"teaching started for {label}",
            )
        else:
            result = self._session.stop()
            self._session = None
            return InteractionResult(
                success=True, action="teach", object_label=label,
                message=f"teaching complete: {result.get('positions_recorded', 0)} positions",
            )


# ── Factory ──────────────────────────────────────────────────────

def build_registry(interaction, kinesthetic=None) -> ProtocolRegistry:
    """Build and populate a ProtocolRegistry from existing subsystem instances.

    Args:
        interaction: The shared ObjectInteraction instance.
        kinesthetic: Optional KinestheticTeacher for the teach protocol.
    """
    registry = ProtocolRegistry()

    registry.register(FetchProtocol(interaction))
    registry.register(HandOverProtocol(interaction))
    registry.register(MoveNearProtocol(interaction))
    registry.register(ThrowAwayProtocol(interaction))
    registry.register(NudgeProtocol(interaction))
    registry.register(OrganizeProtocol())
    registry.register(TeaGuardProtocol())
    registry.register(FistBumpProtocol())
    registry.register(WakeScanProtocol())
    registry.register(TeachProtocol())

    logger.info(f"Protocol registry: {len(registry.names)} protocols registered")
    return registry


def build_selector(registry: ProtocolRegistry,
                   ollama_generate=None) -> ProtocolSelector:
    """Build a ProtocolSelector with regex fast-path and optional LLM fallback.

    Args:
        registry: The protocol registry.
        ollama_generate: Async callable(prompt) -> str. Pass None to disable LLM tier.
    """
    from voice_input import CommandParser
    parser = CommandParser()
    return ProtocolSelector(registry, parser, ollama_generate)
