"""Adaptive Tetris difficulty — ALICE gets better over time.

Tracks ALICE's Tetris performance across sessions (lines cleared, games
played, max score) and gradually adjusts her play style:

- Early sessions: conservative, cautious placements
- After many games: more aggressive, faster decisions, better combos
- Skill level is persisted alongside object memory

The adaptation happens by tuning the TetrisAgent's evaluation weights
and decision timing based on accumulated experience.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("AdaptiveTetris")

DEFAULT_STATS_PATH = Path(__file__).parent.parent / "data" / "tetris_stats.json"


@dataclass
class TetrisStats:
    """Persistent Tetris performance tracking."""
    games_played: int = 0
    total_lines_cleared: int = 0
    max_score: int = 0
    max_lines_single_game: int = 0
    total_play_time_s: float = 0.0
    last_played: float = 0.0

    @property
    def skill_level(self) -> float:
        """0.0 (beginner) to 1.0 (expert), based on cumulative experience."""
        # Ramps up over ~50 games and ~500 lines
        game_factor = min(1.0, self.games_played / 50)
        line_factor = min(1.0, self.total_lines_cleared / 500)
        return (game_factor * 0.4 + line_factor * 0.6)

    def to_dict(self) -> dict:
        return {
            "games_played": self.games_played,
            "total_lines_cleared": self.total_lines_cleared,
            "max_score": self.max_score,
            "max_lines_single_game": self.max_lines_single_game,
            "total_play_time_s": round(self.total_play_time_s, 1),
            "last_played": self.last_played,
            "skill_level": round(self.skill_level, 3),
        }

    @staticmethod
    def from_dict(data: dict) -> "TetrisStats":
        return TetrisStats(
            games_played=data.get("games_played", 0),
            total_lines_cleared=data.get("total_lines_cleared", 0),
            max_score=data.get("max_score", 0),
            max_lines_single_game=data.get("max_lines_single_game", 0),
            total_play_time_s=data.get("total_play_time_s", 0.0),
            last_played=data.get("last_played", 0.0),
        )


class AdaptiveTetris:
    """Manages ALICE's Tetris skill progression.

    Usage:
        adaptive = AdaptiveTetris()
        adaptive.load()
        weights = adaptive.get_agent_weights()  # tuned for current skill
        # ... run game ...
        adaptive.record_game(lines=42, score=12000, duration=180)
        adaptive.save()
    """

    # Weight ranges: [beginner, expert]
    WEIGHT_RANGES = {
        "height": (-0.3, -0.7),      # more aggressive height penalty as she improves
        "holes": (-0.5, -1.0),        # stricter about holes
        "bumpiness": (-0.1, -0.4),    # cares more about surface smoothness
        "lines": (0.6, 1.5),          # higher reward for clearing lines
    }

    # Decision speed: beginner waits longer, expert decides instantly
    DECISION_DELAY_RANGE = (0.4, 0.05)  # seconds (beginner, expert)

    def __init__(self, path: Optional[Path] = None):
        self._path = path or DEFAULT_STATS_PATH
        self._stats = TetrisStats()
        self._game_start_time: float = 0.0

    @property
    def stats(self) -> TetrisStats:
        return self._stats

    @property
    def skill_level(self) -> float:
        return self._stats.skill_level

    def load(self) -> bool:
        """Load stats from disk."""
        if not self._path.exists():
            return False
        try:
            with open(self._path) as f:
                self._stats = TetrisStats.from_dict(json.load(f))
            logger.info(
                f"Tetris stats loaded: {self._stats.games_played} games, "
                f"skill={self._stats.skill_level:.0%}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to load Tetris stats: {e}")
            return False

    def save(self) -> bool:
        """Save stats to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(self._stats.to_dict(), f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save Tetris stats: {e}")
            return False

    def start_game(self) -> None:
        """Call when a Tetris game begins."""
        self._game_start_time = time.time()

    def record_game(self, lines: int = 0, score: int = 0,
                    duration: Optional[float] = None) -> None:
        """Record results of a completed game."""
        self._stats.games_played += 1
        self._stats.total_lines_cleared += lines
        self._stats.max_score = max(self._stats.max_score, score)
        self._stats.max_lines_single_game = max(self._stats.max_lines_single_game, lines)

        if duration is not None:
            self._stats.total_play_time_s += duration
        elif self._game_start_time > 0:
            self._stats.total_play_time_s += time.time() - self._game_start_time

        self._stats.last_played = time.time()
        self._game_start_time = 0.0

        logger.info(
            f"Game #{self._stats.games_played}: {lines} lines, "
            f"score={score}, skill={self._stats.skill_level:.0%}"
        )

    def get_agent_weights(self) -> dict:
        """Get TetrisAgent evaluation weights tuned to current skill level."""
        skill = self._stats.skill_level
        weights = {}
        for key, (lo, hi) in self.WEIGHT_RANGES.items():
            weights[key] = lo + (hi - lo) * skill
        return weights

    def get_decision_delay(self) -> float:
        """Seconds to wait before making a move — faster as skill increases."""
        lo, hi = self.DECISION_DELAY_RANGE
        return lo + (hi - lo) * self._stats.skill_level

    def apply_to_agent(self, agent) -> None:
        """Apply adaptive weights to a TetrisAgent instance."""
        weights = self.get_agent_weights()
        if hasattr(agent, '_weights'):
            agent._weights.update(weights)
            logger.debug(f"Applied adaptive weights: {weights}")
