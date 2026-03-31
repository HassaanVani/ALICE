"""Integration tests for main.py — ALICE class lifecycle."""

from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

import pytest

from config import AliceConfig


def make_config(**overrides):
    """Build an AliceConfig with simulation defaults."""
    return AliceConfig(
        mode=overrides.get("mode", "idle"),
        simulate=True,
    )


class TestAliceInit:
    def test_alice_init(self):
        from main import ALICE
        config = make_config()
        alice = ALICE(config)
        assert alice.arm is None
        assert alice.magnet is None
        assert alice.suction is None
        assert alice.gripper is None
        assert alice.calibration is None

    def test_alice_stores_config(self):
        from main import ALICE
        config = make_config()
        alice = ALICE(config)
        assert alice.config is config
        assert alice.simulate is True


class TestAliceInitialize:
    @pytest.mark.asyncio
    async def test_alice_initialize_simulate(self):
        from main import ALICE
        config = make_config()
        alice = ALICE(config)
        result = await alice.initialize()

        assert result is True
        assert alice.arm is not None
        assert alice.arm.is_connected
        assert alice.gripper is not None
        assert alice.calibration is not None
        assert alice.cameras is not None
        assert alice.tracker is not None
        assert alice.inference is not None

    @pytest.mark.asyncio
    async def test_alice_initialize_creates_suction_gripper(self):
        from main import ALICE
        from hardware.gripper import SuctionGripperAdapter
        config = make_config()
        alice = ALICE(config)
        await alice.initialize()

        assert isinstance(alice.gripper, SuctionGripperAdapter)


class TestAliceModeSwitching:
    @pytest.mark.asyncio
    async def test_alice_mode_switching(self):
        from main import ALICE, Mode
        config = make_config(mode="idle")
        alice = ALICE(config)
        await alice.initialize()

        assert alice.mode == Mode.IDLE
        alice.switch_mode(Mode.AUTO_TETRIS)
        assert alice.mode == Mode.AUTO_TETRIS

    @pytest.mark.asyncio
    async def test_alice_mode_switch_same_mode_noop(self):
        from main import ALICE, Mode
        config = make_config(mode="idle")
        alice = ALICE(config)
        await alice.initialize()

        alice.switch_mode(Mode.IDLE)
        # Should not crash, no-op

    @pytest.mark.asyncio
    async def test_alice_mode_switch_teardown(self):
        from main import ALICE, Mode
        config = make_config(mode="idle")
        alice = ALICE(config)
        await alice.initialize()

        alice.switch_mode(Mode.AUTO_TETRIS)
        alice.switch_mode(Mode.IDLE)
        assert alice.tetris is None


class TestAliceShutdown:
    @pytest.mark.asyncio
    async def test_alice_shutdown_cleans_up(self):
        from main import ALICE
        config = make_config()
        alice = ALICE(config)
        await alice.initialize()

        arm = alice.arm
        gripper = alice.gripper
        suction = alice.suction
        magnet = alice.magnet

        arm.home = MagicMock(return_value=True)
        arm.disconnect = MagicMock()
        gripper.open = MagicMock(return_value=True)
        suction.off = MagicMock(return_value=True)
        magnet.off = MagicMock(return_value=True)

        await alice.shutdown()

        arm.home.assert_called_once()
        arm.disconnect.assert_called_once()
        gripper.open.assert_called_once()
        suction.off.assert_called_once()
        magnet.off.assert_called_once()
