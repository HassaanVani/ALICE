"""RL neural network architectures for ChimpSort."""

import torch
import torch.nn as nn
import torch.nn.functional as F


class SortQNetwork(nn.Module):
    """Simple Q-network for ChimpSort DQN.

    Input: 64-dim state vector (16 blocks x 4 features).
    Output: 16 Q-values (one per block action).
    """

    def __init__(self, obs_dim: int = 64, n_actions: int = 16, hidden: int = 128):
        super().__init__()
        self.fc1 = nn.Linear(obs_dim, hidden)
        self.fc2 = nn.Linear(hidden, hidden)
        self.fc3 = nn.Linear(hidden, n_actions)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)


class SortDuelingQNetwork(nn.Module):
    """Dueling Q-network variant for potentially better RL performance."""

    def __init__(self, obs_dim: int = 64, n_actions: int = 16, hidden: int = 128):
        super().__init__()
        self.feature = nn.Sequential(
            nn.Linear(obs_dim, hidden),
            nn.ReLU(),
        )
        self.value_stream = nn.Sequential(
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Linear(hidden // 2, 1),
        )
        self.advantage_stream = nn.Sequential(
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Linear(hidden // 2, n_actions),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.feature(x)
        value = self.value_stream(features)
        advantages = self.advantage_stream(features)
        return value + advantages - advantages.mean(dim=1, keepdim=True)
