"""Shared fixtures for ALICE test suite."""

import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_block_image():
    """Random 64x64 uint8 grayscale image."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 256, size=(64, 64), dtype=np.uint8)


@pytest.fixture
def sample_color_image():
    """Random 64x64x3 uint8 BGR image."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8)


@pytest.fixture
def sim_arm():
    """Simulated ArmController, connected and ready."""
    from hardware.arm_controller import ArmController
    arm = ArmController(simulate=True)
    arm.connect()
    return arm


@pytest.fixture
def sim_gripper():
    """Simulated SuctionGripperAdapter wrapping a simulated SuctionDriver."""
    from hardware.suction_driver import SuctionDriver
    from hardware.gripper import SuctionGripperAdapter
    return SuctionGripperAdapter(SuctionDriver(simulate=True))
