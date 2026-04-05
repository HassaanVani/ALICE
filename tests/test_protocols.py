"""Tests for logic/protocols.py — Protocol registry, selector, and wrappers."""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from logic.protocols import (
    Protocol,
    ProtocolSpec,
    ProtocolParam,
    ProtocolContext,
    ProtocolRegistry,
    ProtocolSelector,
    FetchProtocol,
    HandOverProtocol,
    MoveNearProtocol,
    ThrowAwayProtocol,
    NudgeProtocol,
    OrganizeProtocol,
    TeaGuardProtocol,
    FistBumpProtocol,
    WakeScanProtocol,
    TeachProtocol,
    IgnoreProtocol,
    UndoProtocol,
    build_registry,
    build_selector,
)
from logic.object_interaction import InteractionResult


# ── Helpers ──────────────────────────────────────────────────────

def mock_interaction():
    """Build a mock ObjectInteraction with async methods."""
    m = MagicMock()
    m.fetch = AsyncMock(return_value=InteractionResult(
        success=True, action="fetch", object_label="pen",
    ))
    m.hand_over = AsyncMock(return_value=InteractionResult(
        success=True, action="hand_over", object_label="pen",
    ))
    m.move_near = AsyncMock(return_value=InteractionResult(
        success=True, action="place_beside", object_label="pen near laptop",
    ))
    m.throw_away = AsyncMock(return_value=InteractionResult(
        success=True, action="throw_away", object_label="tissue",
    ))
    m.nudge = AsyncMock(return_value=InteractionResult(
        success=True, action="nudge", object_label="cup",
    ))
    return m


def mock_ctx():
    """Build a minimal ProtocolContext with mocks."""
    return ProtocolContext(
        arm=MagicMock(),
        gripper=MagicMock(),
        calibration=MagicMock(),
        dynamics=MagicMock(),
        personality=MagicMock(),
        narration=MagicMock(),
        camera_getter=MagicMock(return_value=None),
        yolo_detector=MagicMock(),
        state_manager=MagicMock(),
    )


# ── Registry ─────────────────────────────────────────────────────

class TestProtocolRegistry:
    def test_register_and_get(self):
        registry = ProtocolRegistry()
        interaction = mock_interaction()
        proto = FetchProtocol(interaction)
        registry.register(proto)
        assert registry.get("fetch") is proto

    def test_get_unknown_returns_none(self):
        registry = ProtocolRegistry()
        assert registry.get("nonexistent") is None

    def test_list_specs(self):
        registry = ProtocolRegistry()
        interaction = mock_interaction()
        registry.register(FetchProtocol(interaction))
        registry.register(HandOverProtocol(interaction))
        specs = registry.list_specs()
        assert len(specs) == 2
        names = [s.name for s in specs]
        assert "fetch" in names
        assert "hand_over" in names

    def test_names(self):
        registry = ProtocolRegistry()
        interaction = mock_interaction()
        registry.register(FetchProtocol(interaction))
        assert "fetch" in registry.names

    def test_tool_prompt_contains_all_protocols(self):
        registry = ProtocolRegistry()
        interaction = mock_interaction()
        registry.register(FetchProtocol(interaction))
        registry.register(MoveNearProtocol(interaction))
        prompt = registry.tool_prompt(visible_objects=["cup", "pen"])
        assert "fetch(object)" in prompt
        assert "place_beside(source, target)" in prompt
        assert "cup, pen" in prompt

    def test_tool_prompt_no_objects(self):
        registry = ProtocolRegistry()
        interaction = mock_interaction()
        registry.register(FetchProtocol(interaction))
        prompt = registry.tool_prompt()
        assert "Objects visible" not in prompt
        assert "fetch" in prompt


# ── build_registry ───────────────────────────────────────────────

class TestBuildRegistry:
    def test_build_registry_has_all_protocols(self):
        interaction = mock_interaction()
        registry = build_registry(interaction)
        expected = [
            "fetch", "hand_over", "place_beside", "throw_away",
            "nudge", "organize", "guard_spill", "fist_bump",
            "scan_desk", "teach", "undo", "ignore",
        ]
        for name in expected:
            assert registry.get(name) is not None, f"Missing protocol: {name}"

    def test_build_registry_count(self):
        interaction = mock_interaction()
        registry = build_registry(interaction)
        assert len(registry.names) == 12


# ── Protocol specs ───────────────────────────────────────────────

class TestProtocolSpecs:
    def test_fetch_spec(self):
        spec = FetchProtocol(mock_interaction()).spec()
        assert spec.name == "fetch"
        assert "object" in spec.params
        assert spec.params["object"].required is True

    def test_move_near_spec(self):
        spec = MoveNearProtocol(mock_interaction()).spec()
        assert spec.name == "place_beside"
        assert "source" in spec.params
        assert "target" in spec.params

    def test_organize_spec_optional_preset(self):
        spec = OrganizeProtocol().spec()
        assert spec.name == "organize"
        assert "preset" in spec.params
        assert spec.params["preset"].required is False

    def test_fist_bump_spec_optional_mode(self):
        spec = FistBumpProtocol().spec()
        assert spec.name == "fist_bump"
        assert "mode" in spec.params
        assert spec.params["mode"].required is False

    def test_teach_spec(self):
        spec = TeachProtocol().spec()
        assert spec.name == "teach"
        assert "object" in spec.params


# ── Protocol execution ───────────────────────────────────────────

class TestProtocolExecution:
    @pytest.mark.asyncio
    async def test_fetch_delegates(self):
        interaction = mock_interaction()
        proto = FetchProtocol(interaction)
        ctx = mock_ctx()
        result = await proto.execute({"object": "pen"}, ctx)
        interaction.fetch.assert_awaited_once_with("pen", ctx.camera_getter)
        assert result.success is True
        assert result.action == "fetch"

    @pytest.mark.asyncio
    async def test_hand_over_delegates(self):
        interaction = mock_interaction()
        proto = HandOverProtocol(interaction)
        ctx = mock_ctx()
        result = await proto.execute({"object": "marker"}, ctx)
        interaction.hand_over.assert_awaited_once_with("marker", ctx.camera_getter)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_move_near_delegates(self):
        interaction = mock_interaction()
        proto = MoveNearProtocol(interaction)
        ctx = mock_ctx()
        result = await proto.execute({"source": "pen", "target": "laptop"}, ctx)
        interaction.move_near.assert_awaited_once_with("pen", "laptop", ctx.camera_getter)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_throw_away_delegates(self):
        interaction = mock_interaction()
        proto = ThrowAwayProtocol(interaction)
        ctx = mock_ctx()
        result = await proto.execute({"object": "tissue"}, ctx)
        interaction.throw_away.assert_awaited_once_with("tissue", ctx.camera_getter)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_nudge_direction_mapping(self):
        interaction = mock_interaction()
        proto = NudgeProtocol(interaction)
        ctx = mock_ctx()
        await proto.execute({"object": "cup", "direction": "left"}, ctx)
        interaction.nudge.assert_awaited_once_with(
            "cup", ctx.camera_getter, dx_px=-80, dy_px=0,
        )

    @pytest.mark.asyncio
    async def test_nudge_default_direction(self):
        interaction = mock_interaction()
        proto = NudgeProtocol(interaction)
        ctx = mock_ctx()
        await proto.execute({"object": "cup", "direction": "right"}, ctx)
        interaction.nudge.assert_awaited_once_with(
            "cup", ctx.camera_getter, dx_px=80, dy_px=0,
        )

    @pytest.mark.asyncio
    async def test_wake_scan_returns_result(self):
        proto = WakeScanProtocol()
        ctx = mock_ctx()

        mock_scan_result = MagicMock()
        mock_scan_result.objects_found = [{"label": "cup"}, {"label": "pen"}]

        with patch("logic.wake_scan.WakeScanRoutine") as MockRoutine:
            instance = MockRoutine.return_value
            instance.execute = AsyncMock(return_value=mock_scan_result)
            result = await proto.execute({}, ctx)

        assert result.success is True
        assert result.action == "scan_desk"
        assert "2 objects found" in result.message


# ── Selector ─────────────────────────────────────────────────────

class TestProtocolSelector:
    def test_regex_fast_path_fetch(self):
        interaction = mock_interaction()
        registry = build_registry(interaction)
        selector = build_selector(registry)

        # Sync test of the regex tier
        result = selector._try_regex("grab the pen")
        assert result is not None
        name, params = result
        assert name == "fetch"
        assert params["object"] == "pen"

    def test_regex_fast_path_move_near(self):
        interaction = mock_interaction()
        registry = build_registry(interaction)
        selector = build_selector(registry)

        result = selector._try_regex("move the cup near my laptop")
        assert result is not None
        name, params = result
        assert name == "place_beside"
        assert params["source"] == "cup"
        assert params["target"] == "laptop"

    def test_regex_fast_path_hand_over(self):
        interaction = mock_interaction()
        registry = build_registry(interaction)
        selector = build_selector(registry)

        result = selector._try_regex("pass me the pen")
        assert result is not None
        name, params = result
        assert name == "hand_over"
        assert params["object"] == "pen"

    def test_regex_fast_path_undo(self):
        interaction = mock_interaction()
        registry = build_registry(interaction)
        selector = build_selector(registry)

        for text in ["undo", "undo that", "put it back", "no not there", "no wrong"]:
            result = selector._try_regex(text)
            assert result is not None, f"'{text}' should match undo"
            name, _ = result
            assert name == "undo", f"'{text}' got {name} instead of undo"

    def test_regex_unknown_returns_none(self):
        interaction = mock_interaction()
        registry = build_registry(interaction)
        selector = build_selector(registry)

        result = selector._try_regex("what is the meaning of life")
        assert result is None

    def test_parse_llm_response_valid(self):
        interaction = mock_interaction()
        registry = build_registry(interaction)
        selector = build_selector(registry)

        raw = '{"tool": "fetch", "params": {"object": "mug"}}'
        result = selector._parse_llm_response(raw)
        assert result is not None
        name, params = result
        assert name == "fetch"
        assert params["object"] == "mug"

    def test_parse_llm_response_unknown_tool(self):
        interaction = mock_interaction()
        registry = build_registry(interaction)
        selector = build_selector(registry)

        raw = '{"tool": "fly_away", "params": {}}'
        result = selector._parse_llm_response(raw)
        assert result is None

    def test_parse_llm_response_missing_required_param(self):
        interaction = mock_interaction()
        registry = build_registry(interaction)
        selector = build_selector(registry)

        raw = '{"tool": "fetch", "params": {}}'
        result = selector._parse_llm_response(raw)
        assert result is None

    def test_parse_llm_response_garbage(self):
        interaction = mock_interaction()
        registry = build_registry(interaction)
        selector = build_selector(registry)

        result = selector._parse_llm_response("not json at all")
        assert result is None

    @pytest.mark.asyncio
    async def test_select_uses_regex_first(self):
        interaction = mock_interaction()
        registry = build_registry(interaction)

        mock_llm = AsyncMock(return_value='{"tool":"hand_over","params":{"object":"pen"}}')
        selector = ProtocolSelector(registry, command_parser=None, ollama_generate=mock_llm)

        # No parser → should skip regex tier, go to LLM
        result = await selector.select("pass me the pen")
        assert result is not None
        name, params = result
        assert name == "hand_over"

    @pytest.mark.asyncio
    async def test_select_no_llm_returns_none(self):
        interaction = mock_interaction()
        registry = build_registry(interaction)
        selector = ProtocolSelector(registry, command_parser=None, ollama_generate=None)

        result = await selector.select("something ambiguous")
        assert result is None


# ── FistBumpProtocol ─────────────────────────────────────────────

class TestFistBumpProtocol:
    def test_inner_access(self):
        proto = FistBumpProtocol()
        assert proto.inner is not None
        assert hasattr(proto.inner, 'check_and_respond')

    def test_shutdown(self):
        proto = FistBumpProtocol()
        proto.shutdown()  # should not raise


# ── ProtocolContext ──────────────────────────────────────────────

class TestUndoProtocol:
    def test_undo_spec(self):
        interaction = mock_interaction()
        spec = UndoProtocol(interaction).spec()
        assert spec.name == "undo"
        assert len(spec.params) == 0

    @pytest.mark.asyncio
    async def test_undo_no_last_move(self):
        interaction = mock_interaction()
        interaction._last_move = None
        interaction.undo = AsyncMock(return_value=InteractionResult(
            success=False, action="undo", object_label="",
            message="nothing to undo",
        ))
        proto = UndoProtocol(interaction)
        ctx = mock_ctx()
        ctx.personality = None
        result = await proto.execute({}, ctx)
        assert result.success is False
        assert "nothing to undo" in result.message

    @pytest.mark.asyncio
    async def test_undo_reverses_last_move(self):
        interaction = mock_interaction()
        interaction.undo = AsyncMock(return_value=InteractionResult(
            success=True, action="undo", object_label="pen",
            message="moved pen back",
        ))
        proto = UndoProtocol(interaction)
        ctx = mock_ctx()
        ctx.personality = None
        result = await proto.execute({}, ctx)
        assert result.success is True
        assert result.object_label == "pen"


class TestIgnoreProtocol:
    def test_ignore_spec(self):
        spec = IgnoreProtocol().spec()
        assert spec.name == "ignore"
        assert len(spec.params) == 0

    @pytest.mark.asyncio
    async def test_ignore_execute(self):
        proto = IgnoreProtocol()
        ctx = mock_ctx()
        result = await proto.execute({}, ctx)
        assert result.success is True
        assert result.action == "ignore"


class TestProtocolContext:
    def test_context_construction(self):
        ctx = mock_ctx()
        assert ctx.arm is not None
        assert ctx.camera_getter is not None
        assert ctx.running_check is None  # default

    def test_context_with_running_check(self):
        ctx = ProtocolContext(
            arm=MagicMock(), gripper=MagicMock(),
            calibration=MagicMock(), dynamics=MagicMock(),
            personality=MagicMock(), narration=MagicMock(),
            camera_getter=MagicMock(), yolo_detector=MagicMock(),
            state_manager=MagicMock(),
            running_check=lambda: True,
        )
        assert ctx.running_check() is True
