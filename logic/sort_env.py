"""Gymnasium environment for ChimpSort RL training."""

from typing import Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces


class ChimpSortEnv(gym.Env):
    """
    ChimpSort as a Gymnasium environment.

    Observation: 16 blocks x 4 features (x, y, in_sorted_zone, partial_order) = 64-dim normalized.
    Action: Discrete(16) — pick block i, place at its target position.
    Reward: +1.0 per correct placement, +0.1 partial credit, -0.05 step penalty, +10.0 episode completion.
    """

    metadata = {"render_modes": []}

    NUM_BLOCKS = 16
    OBS_DIM = NUM_BLOCKS * 4  # x, y, in_sorted_zone, partial_order
    BOARD_WIDTH = 800
    BOARD_HEIGHT = 300
    SORTED_ZONE_Y = 50
    SLOT_WIDTH = 50

    def __init__(self, max_steps: int = 50):
        super().__init__()
        self.action_space = spaces.Discrete(self.NUM_BLOCKS)
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(self.OBS_DIM,), dtype=np.float32
        )
        self.max_steps = max_steps
        self._step_count = 0
        self._block_positions = np.zeros((self.NUM_BLOCKS, 2), dtype=np.float32)
        self._placed = np.zeros(self.NUM_BLOCKS, dtype=bool)
        self._rng = np.random.default_rng()

    def reset(self, seed=None, options=None) -> Tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        self._rng = np.random.default_rng(seed)
        self._step_count = 0
        self._placed[:] = False

        # Randomize initial positions in the "unsorted" zone
        for i in range(self.NUM_BLOCKS):
            self._block_positions[i, 0] = self._rng.uniform(0, self.BOARD_WIDTH)
            self._block_positions[i, 1] = self._rng.uniform(100, self.BOARD_HEIGHT)

        return self._get_obs(), {}

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, dict]:
        self._step_count += 1
        reward = -0.05  # Step penalty

        block_idx = action

        if self._placed[block_idx]:
            # Already placed — no-op with penalty
            obs = self._get_obs()
            done = self._step_count >= self.max_steps
            return obs, reward, done, False, {"placed": int(self._placed.sum())}

        # Move block to its target sorted position
        target_x = block_idx * self.SLOT_WIDTH
        target_y = self.SORTED_ZONE_Y

        # Check if this is the correct next block to place (partial ordering)
        expected_next = self._get_next_expected()
        if block_idx == expected_next:
            reward += 1.0  # Correct placement
        else:
            reward += 0.1  # Partial credit for placing any block

        self._block_positions[block_idx] = [target_x, target_y]
        self._placed[block_idx] = True

        # Check episode completion
        done = bool(self._placed.all()) or self._step_count >= self.max_steps

        if self._placed.all():
            reward += 10.0  # Completion bonus

        obs = self._get_obs()
        return obs, reward, done, False, {"placed": int(self._placed.sum())}

    def _get_next_expected(self) -> int:
        """Return the index of the next block that should be placed in sorted order."""
        for i in range(self.NUM_BLOCKS):
            if not self._placed[i]:
                return i
        return 0

    def _get_obs(self) -> np.ndarray:
        obs = np.zeros(self.OBS_DIM, dtype=np.float32)
        for i in range(self.NUM_BLOCKS):
            base = i * 4
            obs[base] = self._block_positions[i, 0] / self.BOARD_WIDTH
            obs[base + 1] = self._block_positions[i, 1] / self.BOARD_HEIGHT
            obs[base + 2] = 1.0 if self._placed[i] else 0.0
            # Partial order: how many blocks before this one are already placed
            placed_before = sum(1 for j in range(i) if self._placed[j])
            obs[base + 3] = placed_before / max(1, i) if i > 0 else 1.0
        return obs

    def get_state_vector(self) -> np.ndarray:
        """Public method matching ChimpSortFSM interface."""
        return self._get_obs()
