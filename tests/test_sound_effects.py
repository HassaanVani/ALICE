"""Tests for servo-based sound effects."""

import asyncio
import pytest

from hardware.arm_controller import ArmController
from audio.sound_effects import SoundEffects, SoundCategory, PATTERNS, ServoPattern


@pytest.fixture
def sim_sfx():
    arm = ArmController(simulate=True)
    arm.connect()
    return SoundEffects(arm=arm, enabled=True, intensity=1.0)


@pytest.fixture
def disabled_sfx():
    return SoundEffects(arm=None, enabled=False)


class TestSoundCategories:
    def test_all_categories_have_patterns(self):
        for cat in SoundCategory:
            assert cat in PATTERNS, f"Missing pattern for {cat}"

    def test_patterns_are_valid(self):
        for cat, patterns in PATTERNS.items():
            for p in patterns:
                assert isinstance(p, ServoPattern)
                assert 0 <= p.joint <= 3
                assert p.amplitude_deg > 0
                assert p.frequency_hz > 0
                assert p.duration_s > 0
                assert p.repeat >= 1


class TestSoundEffects:
    @pytest.mark.asyncio
    async def test_play_returns_true(self, sim_sfx):
        result = await sim_sfx.play(SoundCategory.ACKNOWLEDGE)
        assert result is True

    @pytest.mark.asyncio
    async def test_play_curious(self, sim_sfx):
        result = await sim_sfx.play(SoundCategory.CURIOUS)
        assert result is True

    @pytest.mark.asyncio
    async def test_play_all_categories(self, sim_sfx):
        for cat in SoundCategory:
            sim_sfx._playing = False
            sim_sfx._last_play_time = 0
            result = await sim_sfx.play(cat)
            assert result is True, f"Failed to play {cat}"

    @pytest.mark.asyncio
    async def test_disabled_returns_false(self, disabled_sfx):
        result = await disabled_sfx.play(SoundCategory.HAPPY)
        assert result is False

    @pytest.mark.asyncio
    async def test_no_overlap(self, sim_sfx):
        """Playing while already playing should return False."""
        sim_sfx._playing = True
        result = await sim_sfx.play(SoundCategory.ACKNOWLEDGE)
        assert result is False

    @pytest.mark.asyncio
    async def test_min_interval(self, sim_sfx):
        """Rapid successive plays should be rate-limited."""
        import time
        await sim_sfx.play(SoundCategory.ACKNOWLEDGE)
        sim_sfx._last_play_time = time.time()  # just played
        result = await sim_sfx.play(SoundCategory.HAPPY)
        assert result is False

    def test_set_arm(self):
        sfx = SoundEffects(arm=None, enabled=True)
        assert not sfx.enabled
        arm = ArmController(simulate=True)
        arm.connect()
        sfx.set_arm(arm)
        assert sfx.enabled

    def test_set_intensity(self, sim_sfx):
        sim_sfx.set_intensity(0.5)
        assert sim_sfx._intensity == 0.5
        sim_sfx.set_intensity(1.5)  # clamped
        assert sim_sfx._intensity == 1.0
        sim_sfx.set_intensity(-0.5)
        assert sim_sfx._intensity == 0.0

    @pytest.mark.asyncio
    async def test_play_for_emotion(self, sim_sfx):
        result = await sim_sfx.play_for_emotion("curious")
        assert result is True

    @pytest.mark.asyncio
    async def test_play_for_neutral_emotion(self, sim_sfx):
        result = await sim_sfx.play_for_emotion("content")
        assert result is False  # content maps to None
