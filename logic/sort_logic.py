import logging
import time
from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from vision.aruco_detector import BlockData

logger = logging.getLogger("SortLogic")


class SortState(Enum):
    IDLE = "idle"
    SCRAMBLING = "scrambling"
    HUMAN_BENCHMARK = "human_benchmark"
    GHOST_REPLAY = "ghost_replay"
    AWAITING_PUPPETEER = "awaiting_puppeteer"
    CYBORG_COOP = "cyborg_coop"
    REBELLION = "rebellion"
    COMPLETE = "complete"


@dataclass
class MoveRecord:
    block_id: int
    from_pos: Tuple[int, int]
    to_pos: Tuple[int, int]
    timestamp: float


@dataclass
class SortingSession:
    start_time: float = 0.0
    end_time: float = 0.0
    moves: List[MoveRecord] = field(default_factory=list)
    final_order: List[int] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time if self.end_time else 0.0
    
    @property
    def move_count(self) -> int:
        return len(self.moves)
    
    @property
    def efficiency_score(self) -> float:
        if self.move_count == 0:
            return 0.0
        return min(1.0, NUM_BLOCKS / self.move_count)


NUM_BLOCKS = 16  # default block count — used across sort logic and efficiency scoring


class ChimpSortFSM:
    def __init__(self, num_blocks: int = NUM_BLOCKS,
                 sorted_zone: Tuple[int, int, int, int] = (0, 0, 800, 100),
                 drop_zone: Tuple[int, int, int, int] = (800, 0, 200, 300)):
        self._state = SortState.IDLE
        self._session: Optional[SortingSession] = None
        self._block_positions: dict[int, Tuple[int, int]] = {}
        self._num_blocks = num_blocks
        self._sorted_zone = sorted_zone
        self._drop_zone = drop_zone
        self._on_state_change: Optional[Callable[[SortState], None]] = None
        self._on_move: Optional[Callable[[MoveRecord], None]] = None
    
    @property
    def state(self) -> SortState:
        return self._state
    
    @property
    def session(self) -> Optional[SortingSession]:
        return self._session
    
    def on_state_change(self, callback: Callable[[SortState], None]) -> "ChimpSortFSM":
        self._on_state_change = callback
        return self
    
    def on_move(self, callback: Callable[[MoveRecord], None]) -> "ChimpSortFSM":
        self._on_move = callback
        return self
    
    def set_zones(self, sorted_zone: Tuple[int, int, int, int], drop_zone: Tuple[int, int, int, int]) -> None:
        self._sorted_zone = sorted_zone
        self._drop_zone = drop_zone
    
    def _transition(self, new_state: SortState) -> None:
        if self._state != new_state:
            self._state = new_state
            if self._on_state_change:
                self._on_state_change(new_state)
    
    def start_human_benchmark(self) -> None:
        self._session = SortingSession(start_time=time.time())
        self._block_positions.clear()
        self._transition(SortState.HUMAN_BENCHMARK)
    
    def start_ghost_replay(self, session: Optional[SortingSession] = None) -> None:
        if session:
            self._session = session
        self._transition(SortState.GHOST_REPLAY)
    
    def start_cyborg_coop(self) -> None:
        self._session = SortingSession(start_time=time.time())
        self._transition(SortState.CYBORG_COOP)

    def start_rebellion(self) -> None:
        self._session = SortingSession(start_time=time.time())
        self._block_positions.clear()
        self._transition(SortState.REBELLION)
    
    def stop(self) -> Optional[SortingSession]:
        if self._session:
            self._session.end_time = time.time()
        result = self._session
        self._session = None
        self._transition(SortState.IDLE)
        return result
    
    def update(self, blocks: List[BlockData]) -> None:
        if self._state == SortState.IDLE:
            return
        
        for block in blocks:
            pos = (block.center_x, block.center_y)
            block_id = block.block_id
            
            if block_id in self._block_positions:
                prev_pos = self._block_positions[block_id]
                if self._significant_move(prev_pos, pos):
                    move = MoveRecord(
                        block_id=block_id,
                        from_pos=prev_pos,
                        to_pos=pos,
                        timestamp=time.time()
                    )
                    if self._session:
                        self._session.moves.append(move)
                    if self._on_move:
                        self._on_move(move)
            
            self._block_positions[block_id] = pos
        
        if self._check_sorted(blocks):
            if self._session:
                self._session.end_time = time.time()
                self._session.final_order = [b.block_id for b in blocks]
            self._transition(SortState.COMPLETE)
    
    def _significant_move(self, prev: Tuple[int, int], curr: Tuple[int, int], threshold: int = 30) -> bool:
        return abs(prev[0] - curr[0]) > threshold or abs(prev[1] - curr[1]) > threshold
    
    def _check_sorted(self, blocks: List[BlockData]) -> bool:
        if len(blocks) < self._num_blocks:
            return False

        ids = [b.block_id for b in sorted(blocks, key=lambda b: b.center_x)]
        return ids == list(range(1, self._num_blocks + 1))
    
    def is_in_drop_zone(self, x: int, y: int) -> bool:
        zx, zy, zw, zh = self._drop_zone
        return zx <= x < zx + zw and zy <= y < zy + zh
    
    def is_in_sorted_zone(self, x: int, y: int) -> bool:
        zx, zy, zw, zh = self._sorted_zone
        return zx <= x < zx + zw and zy <= y < zy + zh
    
    def get_state_vector(self) -> "np.ndarray":
        """Return normalized state vector for RL agent (64-dim)."""
        import numpy as _np
        obs = _np.zeros(64, dtype=_np.float32)
        sorted_zone = self._sorted_zone
        for block_id, pos in self._block_positions.items():
            if 1 <= block_id <= self._num_blocks:
                idx = block_id - 1
                base = idx * 4
                obs[base] = pos[0] / 800.0
                obs[base + 1] = pos[1] / 300.0
                obs[base + 2] = 1.0 if self.is_in_sorted_zone(pos[0], pos[1]) else 0.0
                placed_before = sum(
                    1 for bid in range(1, block_id)
                    if bid in self._block_positions and
                    self.is_in_sorted_zone(*self._block_positions[bid])
                )
                obs[base + 3] = placed_before / max(1, idx) if idx > 0 else 1.0
        return obs

    def apply_action(self, block_id: int) -> Optional[Tuple[int, Tuple[int, int]]]:
        """Apply an RL action: move block_id to its sorted position."""
        if block_id not in self._block_positions:
            return None
        slot_width = self._sorted_zone[2] // self._num_blocks
        target_x = self._sorted_zone[0] + (block_id - 1) * slot_width
        target_y = self._sorted_zone[1] + 50
        return (block_id, (target_x, target_y))

    def get_next_robot_target(self, rl_agent=None, audience_vote: Optional[int] = None) -> Optional[Tuple[int, Tuple[int, int]]]:
        if self._state != SortState.CYBORG_COOP:
            return None

        # Audience vote takes priority
        if audience_vote is not None and audience_vote in self._block_positions:
            return self.apply_action(audience_vote)

        # RL agent next
        if rl_agent is not None:
            try:
                obs = self.get_state_vector()
                action, _ = rl_agent.predict(obs, deterministic=True)
                block_id = int(action) + 1
                result = self.apply_action(block_id)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"RL agent prediction failed: {e}")

        # Greedy fallback
        slot_width = self._sorted_zone[2] // self._num_blocks
        for block_id, pos in self._block_positions.items():
            if self.is_in_drop_zone(pos[0], pos[1]):
                target_x = self._sorted_zone[0] + (block_id - 1) * slot_width
                target_y = self._sorted_zone[1] + 50
                return (block_id, (target_x, target_y))

        return None

    def get_optimal_next_target(self) -> Optional[Tuple[int, Tuple[int, int]]]:
        """Pure greedy optimal: next block in sequence that isn't already placed.
        Used in rebellion mode — ignores audience input entirely."""
        for target_id in range(1, self._num_blocks + 1):
            if target_id not in self._block_positions:
                continue
            pos = self._block_positions[target_id]
            slot_width = self._sorted_zone[2] // self._num_blocks
            target_x = self._sorted_zone[0] + (target_id - 1) * slot_width
            target_y = self._sorted_zone[1] + 50
            # Skip if already in position
            if not self._significant_move(pos, (target_x, target_y), threshold=20):
                continue
            return (target_id, (target_x, target_y))
        return None
    
    def get_ghost_replay_moves(self) -> List[MoveRecord]:
        if not self._session:
            return []
        return list(self._session.moves)
    
    def compute_optimal_sort(self, blocks: List[BlockData]) -> List[Tuple[int, Tuple[int, int], Tuple[int, int]]]:
        current = {b.block_id: (b.center_x, b.center_y) for b in blocks}
        moves = []
        slot_width = self._sorted_zone[2] // self._num_blocks

        for target_id in range(1, self._num_blocks + 1):
            if target_id not in current:
                continue

            from_pos = current[target_id]
            target_x = self._sorted_zone[0] + (target_id - 1) * slot_width
            target_y = self._sorted_zone[1] + 50
            to_pos = (target_x, target_y)
            
            if self._significant_move(from_pos, to_pos, threshold=10):
                moves.append((target_id, from_pos, to_pos))
                current[target_id] = to_pos
        
        return moves
