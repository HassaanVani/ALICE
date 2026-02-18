"""Tetris controller — orchestrates screen reading, AI move computation, and key pressing.

Pipeline: ScreenReader.capture_board() -> TetrisAgent.compute_best_move() -> KeyboardPlayer.execute_sequence()
"""

import asyncio
import logging
from typing import Dict, List, Optional

from logic.tetris_agent import TetrisAction, TetrisAgent, TetrisState

logger = logging.getLogger("TetrisController")

# Map TetrisAction -> physical key name
ACTION_TO_KEY: Dict[TetrisAction, str] = {
    TetrisAction.LEFT: "left_arrow",
    TetrisAction.RIGHT: "right_arrow",
    TetrisAction.ROTATE_CW: "up_arrow",
    TetrisAction.ROTATE_CCW: "z",
    TetrisAction.HARD_DROP: "space",
    TetrisAction.HOLD: "c",
}


class TetrisController:
    """Orchestrates the physical Tetris pipeline.

    Captures the tetr.io board from screen, computes the best move using
    TetrisAgent's heuristic, then presses the corresponding keys on a
    physical keyboard via the robotic arm.
    """

    def __init__(self, screen_reader, keyboard_player, agent: Optional[TetrisAgent] = None,
                 loop_delay: float = 0.3):
        self.screen_reader = screen_reader
        self.keyboard_player = keyboard_player
        self.agent = agent or TetrisAgent()
        self.loop_delay = loop_delay
        self._running = False

        # Stats
        self.cycles = 0
        self.total_keys_pressed = 0

    async def run_loop(self, running_check=None) -> None:
        """Main loop: capture -> compute -> press -> wait.

        Args:
            running_check: callable returning False to stop the loop.
        """
        self._running = True
        logger.info("Tetris controller loop started")

        # Initialize agent with an empty board
        self.agent.reset()

        while self._running:
            if running_check and not running_check():
                break

            try:
                # 1. Capture board from screen
                board_state = self.screen_reader.capture_board()
                if board_state is None:
                    logger.debug("No board captured, retrying")
                    await asyncio.sleep(self.loop_delay)
                    continue

                # 2. Update agent state from screen capture
                self._update_agent_from_screen(board_state)

                if self.agent.state and self.agent.state.game_over:
                    logger.info("Game over detected from screen")
                    break

                # 3. Compute best move
                actions = self.agent.compute_best_move()
                if not actions:
                    await asyncio.sleep(self.loop_delay)
                    continue

                # 4. Convert actions to key names
                keys = self._actions_to_keys(actions)
                logger.debug(f"Cycle {self.cycles}: pressing {keys}")

                # 5. Press keys on physical keyboard
                pressed = await self.keyboard_player.execute_sequence(keys)
                self.total_keys_pressed += pressed

                self.cycles += 1

            except Exception as e:
                logger.error(f"Tetris controller error: {e}")

            await asyncio.sleep(self.loop_delay)

        self._running = False
        logger.info(f"Tetris controller stopped after {self.cycles} cycles, "
                     f"{self.total_keys_pressed} keys pressed")

    def stop(self):
        self._running = False

    def _update_agent_from_screen(self, board_state) -> None:
        """Update the TetrisAgent's internal board from the captured screen state."""
        import numpy as np

        if self.agent.state is None:
            self.agent.reset()

        # Convert color indices to binary (0 = empty, 1 = filled)
        binary_board = (board_state.grid > 0).astype(np.int8)
        self.agent.state.board = binary_board

    def _actions_to_keys(self, actions: List[TetrisAction]) -> List[str]:
        """Convert a list of TetrisActions to physical key names."""
        keys = []
        for action in actions:
            key = ACTION_TO_KEY.get(action)
            if key:
                keys.append(key)
        return keys
