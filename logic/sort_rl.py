"""DQN training for ChimpSort using stable-baselines3."""

import logging
from pathlib import Path

logger = logging.getLogger("SortRL")

WEIGHTS_DIR = Path(__file__).parent.parent / "brain" / "weights"
AGENT_PATH = WEIGHTS_DIR / "sort_agent.zip"


def train_agent(timesteps: int = 100_000, save_path: Path = AGENT_PATH) -> None:
    """Train a DQN agent for ChimpSort."""
    try:
        from stable_baselines3 import DQN
        from stable_baselines3.common.env_util import make_vec_env
    except ImportError:
        logger.error("stable-baselines3 not installed. Run: pip install stable-baselines3")
        return

    from logic.sort_env import ChimpSortEnv

    print("Creating ChimpSort environment...")
    env = ChimpSortEnv(max_steps=50)

    print(f"Training DQN agent for {timesteps} timesteps...")
    model = DQN(
        "MlpPolicy",
        env,
        learning_rate=1e-3,
        buffer_size=50_000,
        learning_starts=1000,
        batch_size=64,
        gamma=0.99,
        target_update_interval=500,
        exploration_fraction=0.3,
        exploration_final_eps=0.05,
        verbose=1,
    )

    model.learn(total_timesteps=timesteps)

    save_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(save_path))
    print(f"Agent saved to {save_path}")

    # Evaluate
    print("\nEvaluating trained agent...")
    obs, _ = env.reset()
    total_reward = 0
    done = False
    steps = 0

    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done, truncated, info = env.step(action)
        total_reward += reward
        steps += 1
        done = done or truncated

    print(f"Evaluation: {steps} steps, reward={total_reward:.2f}, placed={info.get('placed', 0)}/16")


def load_agent(path: Path = AGENT_PATH):
    """Load a trained DQN agent."""
    try:
        from stable_baselines3 import DQN
    except ImportError:
        logger.error("stable-baselines3 not installed")
        return None

    if not path.exists():
        logger.warning(f"No trained agent found at {path}")
        return None

    return DQN.load(str(path))


if __name__ == "__main__":
    train_agent()
