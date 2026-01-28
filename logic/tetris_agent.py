import time
import random
from typing import Optional, Tuple, List, Callable
from dataclasses import dataclass
from enum import Enum, auto

import numpy as np


class TetrisAction(Enum):
    NONE = auto()
    LEFT = auto()
    RIGHT = auto()
    ROTATE_CW = auto()
    ROTATE_CCW = auto()
    SOFT_DROP = auto()
    HARD_DROP = auto()
    HOLD = auto()


@dataclass
class TetrisState:
    board: np.ndarray
    current_piece: int
    next_pieces: List[int]
    hold_piece: Optional[int]
    piece_x: int
    piece_y: int
    piece_rotation: int
    score: int
    lines_cleared: int
    level: int
    game_over: bool


PIECES = {
    0: np.array([[1, 1, 1, 1]]),  # I
    1: np.array([[1, 0], [1, 0], [1, 1]]),  # L
    2: np.array([[0, 1], [0, 1], [1, 1]]),  # J
    3: np.array([[1, 1], [1, 1]]),  # O
    4: np.array([[0, 1, 1], [1, 1, 0]]),  # S
    5: np.array([[1, 1, 0], [0, 1, 1]]),  # Z
    6: np.array([[0, 1, 0], [1, 1, 1]])  # T
}


class TetrisAgent:
    BOARD_WIDTH = 10
    BOARD_HEIGHT = 20
    
    def __init__(self):
        self._state: Optional[TetrisState] = None
        self._on_action: Optional[Callable[[TetrisAction], None]] = None
        self._on_state_update: Optional[Callable[[TetrisState], None]] = None
        self._weights = {
            'height': -0.5,
            'holes': -0.8,
            'bumpiness': -0.2,
            'lines': 1.0
        }
        self._action_delay = 0.05
        self._simulating = False
    
    @property
    def state(self) -> Optional[TetrisState]:
        return self._state
    
    @property
    def is_running(self) -> bool:
        return self._simulating
    
    def on_action(self, callback: Callable[[TetrisAction], None]) -> "TetrisAgent":
        self._on_action = callback
        return self
    
    def on_state_update(self, callback: Callable[[TetrisState], None]) -> "TetrisAgent":
        self._on_state_update = callback
        return self
    
    def set_weights(self, weights: dict) -> None:
        self._weights.update(weights)
    
    def reset(self) -> TetrisState:
        board = np.zeros((self.BOARD_HEIGHT, self.BOARD_WIDTH), dtype=np.int8)
        next_pieces = [random.randint(0, 6) for _ in range(3)]
        
        self._state = TetrisState(
            board=board,
            current_piece=random.randint(0, 6),
            next_pieces=next_pieces,
            hold_piece=None,
            piece_x=self.BOARD_WIDTH // 2 - 1,
            piece_y=0,
            piece_rotation=0,
            score=0,
            lines_cleared=0,
            level=1,
            game_over=False
        )
        
        return self._state
    
    def update_state(self, state: TetrisState) -> None:
        self._state = state
        if self._on_state_update:
            self._on_state_update(state)
    
    def compute_best_move(self) -> List[TetrisAction]:
        if not self._state or self._state.game_over:
            return []
        
        piece = PIECES[self._state.current_piece]
        best_score = float('-inf')
        best_actions: List[TetrisAction] = []
        
        for rotation in range(4):
            rotated = np.rot90(piece, rotation)
            h, w = rotated.shape
            
            for target_x in range(self.BOARD_WIDTH - w + 1):
                landing_y = self._simulate_drop(rotated, target_x)
                
                if landing_y < 0:
                    continue
                
                test_board = self._state.board.copy()
                for dy in range(h):
                    for dx in range(w):
                        if rotated[dy, dx]:
                            test_board[landing_y + dy, target_x + dx] = 1
                
                lines = self._count_complete_lines(test_board)
                test_board = self._clear_lines(test_board)
                
                score = self._evaluate_board(test_board, lines)
                
                if score > best_score:
                    best_score = score
                    best_actions = self._generate_actions(rotation, target_x)
        
        return best_actions
    
    def _simulate_drop(self, piece: np.ndarray, x: int) -> int:
        h, w = piece.shape
        
        for y in range(self.BOARD_HEIGHT - h + 1):
            if self._collision(piece, x, y + 1):
                return y
        
        return self.BOARD_HEIGHT - h
    
    def _collision(self, piece: np.ndarray, x: int, y: int) -> bool:
        h, w = piece.shape
        
        if x < 0 or x + w > self.BOARD_WIDTH:
            return True
        if y < 0 or y + h > self.BOARD_HEIGHT:
            return True
        
        for dy in range(h):
            for dx in range(w):
                if piece[dy, dx]:
                    if self._state.board[y + dy, x + dx]:
                        return True
        
        return False
    
    def _count_complete_lines(self, board: np.ndarray) -> int:
        return sum(1 for row in board if all(row))
    
    def _clear_lines(self, board: np.ndarray) -> np.ndarray:
        new_board = np.zeros_like(board)
        write_row = self.BOARD_HEIGHT - 1
        
        for read_row in range(self.BOARD_HEIGHT - 1, -1, -1):
            if not all(board[read_row]):
                new_board[write_row] = board[read_row]
                write_row -= 1
        
        return new_board
    
    def _evaluate_board(self, board: np.ndarray, lines_cleared: int) -> float:
        heights = []
        for col in range(self.BOARD_WIDTH):
            for row in range(self.BOARD_HEIGHT):
                if board[row, col]:
                    heights.append(self.BOARD_HEIGHT - row)
                    break
            else:
                heights.append(0)
        
        aggregate_height = sum(heights)
        
        holes = 0
        for col in range(self.BOARD_WIDTH):
            found_block = False
            for row in range(self.BOARD_HEIGHT):
                if board[row, col]:
                    found_block = True
                elif found_block:
                    holes += 1
        
        bumpiness = sum(abs(heights[i] - heights[i+1]) for i in range(len(heights)-1))
        
        return (
            self._weights['height'] * aggregate_height +
            self._weights['holes'] * holes +
            self._weights['bumpiness'] * bumpiness +
            self._weights['lines'] * lines_cleared * 100
        )
    
    def _generate_actions(self, target_rotation: int, target_x: int) -> List[TetrisAction]:
        actions = []
        
        rotations_needed = target_rotation % 4
        for _ in range(rotations_needed):
            actions.append(TetrisAction.ROTATE_CW)
        
        current_x = self._state.piece_x if self._state else self.BOARD_WIDTH // 2 - 1
        dx = target_x - current_x
        
        if dx < 0:
            for _ in range(-dx):
                actions.append(TetrisAction.LEFT)
        elif dx > 0:
            for _ in range(dx):
                actions.append(TetrisAction.RIGHT)
        
        actions.append(TetrisAction.HARD_DROP)
        
        return actions
    
    def step(self) -> TetrisAction:
        actions = self.compute_best_move()
        
        if actions:
            action = actions[0]
            if self._on_action:
                self._on_action(action)
            return action
        
        return TetrisAction.NONE
    
    def run_async(self) -> None:
        import threading
        
        def loop():
            self._simulating = True
            while self._simulating and self._state and not self._state.game_over:
                actions = self.compute_best_move()
                for action in actions:
                    if not self._simulating:
                        break
                    if self._on_action:
                        self._on_action(action)
                    time.sleep(self._action_delay)
                time.sleep(0.1)
        
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
    
    def stop(self) -> None:
        self._simulating = False
