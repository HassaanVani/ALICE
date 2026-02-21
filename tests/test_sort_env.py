"""Tests for logic/sort_env.py — ChimpSortEnv gymnasium environment."""

import numpy as np
import pytest

from logic.sort_env import ChimpSortEnv


@pytest.fixture
def env():
    return ChimpSortEnv(max_steps=50)


class TestChimpSortEnv:
    def test_reset_obs_shape(self, env):
        obs, info = env.reset(seed=0)
        assert obs.shape == (64,)
        assert obs.dtype == np.float32

    def test_reset_obs_values_in_range(self, env):
        obs, _ = env.reset(seed=0)
        assert np.all(obs >= 0.0)
        assert np.all(obs <= 1.0)

    def test_action_space(self, env):
        assert env.action_space.n == 16

    def test_observation_space_shape(self, env):
        assert env.observation_space.shape == (64,)

    def test_step_returns_correct_types(self, env):
        env.reset(seed=0)
        obs, reward, done, truncated, info = env.step(0)
        assert isinstance(obs, np.ndarray)
        assert isinstance(reward, float)
        assert isinstance(done, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)

    def test_correct_placement_reward(self, env):
        """Placing block 0 first (correct order) yields +0.95 (+1.0 placement - 0.05 step penalty)."""
        env.reset(seed=0)
        _, reward, _, _, _ = env.step(0)
        assert abs(reward - 0.95) < 1e-6

    def test_duplicate_placement_penalty(self, env):
        """Placing an already-placed block yields only the step penalty -0.05."""
        env.reset(seed=0)
        env.step(0)  # Place block 0
        _, reward, _, _, _ = env.step(0)  # Duplicate
        assert abs(reward - (-0.05)) < 1e-6

    def test_all_placed_completion_bonus(self, env):
        """Placing all 16 blocks gives completion bonus +10.0 and done=True."""
        env.reset(seed=0)
        total_reward = 0
        for i in range(16):
            _, reward, done, _, info = env.step(i)
            total_reward += reward
        assert done is True
        assert info["placed"] == 16
        # Last step reward includes completion bonus
        assert reward > 10.0

    def test_max_steps_truncated(self):
        """Reaching max_steps causes done=True."""
        env = ChimpSortEnv(max_steps=3)
        env.reset(seed=0)
        # Use invalid actions (re-place same block) to burn steps
        for _ in range(2):
            env.step(0)
        _, _, done, _, _ = env.step(0)
        assert done is True

    def test_get_state_vector_matches_obs(self, env):
        env.reset(seed=0)
        env.step(0)
        obs_from_step = env._get_obs()
        state_vec = env.get_state_vector()
        np.testing.assert_array_equal(obs_from_step, state_vec)

    def test_seeded_deterministic(self):
        """Same seed produces identical observations."""
        env1 = ChimpSortEnv(max_steps=50)
        env2 = ChimpSortEnv(max_steps=50)
        obs1, _ = env1.reset(seed=123)
        obs2, _ = env2.reset(seed=123)
        np.testing.assert_array_equal(obs1, obs2)
