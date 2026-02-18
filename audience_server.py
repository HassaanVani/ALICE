"""Audience participation server — live state, block voting, tilt, reactions."""

import asyncio
import json
import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

logger = logging.getLogger("AudienceServer")


# ─── Phase descriptions shown to audience ───────────────────────────
PHASE_INFO = {
    "idle":             {"label": "Waiting",       "desc": "Demo hasn't started yet", "interactive": False},
    "human_benchmark":  {"label": "Human Turn",    "desc": "Watch the human sort",   "interactive": False},
    "ghost_replay":     {"label": "Ghost Replay",  "desc": "Replaying the human",     "interactive": False},
    "cyborg_coop":      {"label": "Your Turn",     "desc": "Tap a block to vote!",    "interactive": True},
    "complete":         {"label": "Done!",          "desc": "Sorting complete",         "interactive": False},
    "tetris":           {"label": "Tetris",         "desc": "Tilt to nudge pieces",    "interactive": True},
    "calibrate":        {"label": "Calibrating",    "desc": "System calibration",       "interactive": False},
    "puppeteer":        {"label": "Puppeteer",      "desc": "Watch the arm dance",      "interactive": False},
}


class AudienceServer:
    """WebSocket server for audience participation — live state, block voting, tilt, reactions."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8767, state_manager=None):
        self.host = host
        self.port = port
        self.state_manager = state_manager
        self.clients: Set[WebSocketServerProtocol] = set()
        self._server = None
        self._running = False

        # ── Block voting ──
        self._block_votes: Dict[int, Set[str]] = defaultdict(set)   # block_id -> {client_ids}
        self._client_votes: Dict[str, int] = {}                      # client_id -> block_id
        self._vote_round: int = 0
        self._last_winner: Optional[dict] = None                      # {block_id, voter_count, round}

        # ── Tilt aggregation ──
        self._tilts: Dict[str, Tuple[float, float]] = {}  # client_id -> (beta, gamma)

        # ── Reactions ──
        self._reaction_cooldowns: Dict[str, float] = {}  # client_id -> last_reaction_time

        # ── Broadcast loop ──
        self._broadcast_task: Optional[asyncio.Task] = None

    # ── Properties ───────────────────────────────────────────────────

    @property
    def client_count(self) -> int:
        return len(self.clients)

    def get_winning_block_id(self) -> Optional[int]:
        """Return the block_id with the most votes, or None."""
        if not self._block_votes:
            return None
        winner = max(self._block_votes.items(), key=lambda kv: len(kv[1]))
        block_id, voters = winner
        if len(voters) == 0:
            return None
        return block_id

    def get_vote_results(self) -> dict:
        """Return {block_id: vote_count} for all blocks with votes."""
        return {bid: len(voters) for bid, voters in self._block_votes.items() if voters}

    def consume_votes(self) -> Optional[dict]:
        """Consume the winning vote — returns winner info and resets for next round."""
        winner_id = self.get_winning_block_id()
        if winner_id is None:
            return None

        voter_count = len(self._block_votes[winner_id])
        voter_ids = list(self._block_votes[winner_id])

        result = {
            "block_id": winner_id,
            "voter_count": voter_count,
            "voter_ids": voter_ids,
            "round": self._vote_round,
        }

        self._last_winner = result
        self._block_votes.clear()
        self._client_votes.clear()
        self._vote_round += 1

        return result

    def get_average_tilt(self) -> Tuple[float, float]:
        """Return average (pitch, roll) across all audience phones. Normalized to -1..1."""
        if not self._tilts:
            return (0.0, 0.0)
        pitches = [t[0] for t in self._tilts.values()]
        rolls = [t[1] for t in self._tilts.values()]
        avg_pitch = max(-1.0, min(1.0, (sum(pitches) / len(pitches)) / 45.0))
        avg_roll = max(-1.0, min(1.0, (sum(rolls) / len(rolls)) / 45.0))
        return (avg_pitch, avg_roll)

    # ── Connection handler ───────────────────────────────────────────

    async def handler(self, websocket: WebSocketServerProtocol) -> None:
        client_id = str(id(websocket))
        self.clients.add(websocket)
        logger.info(f"Audience +1 → {len(self.clients)} connected")

        try:
            # Send welcome with full state
            await websocket.send(json.dumps(self._build_welcome(client_id)))

            # Notify everyone of new count
            await self._broadcast_audience_count()

            async for message in websocket:
                await self._handle_message(message, websocket, client_id)
        except Exception:
            pass
        finally:
            self.clients.discard(websocket)
            self._tilts.pop(client_id, None)
            self._reaction_cooldowns.pop(client_id, None)
            # Clean up this client's vote
            if client_id in self._client_votes:
                old_block = self._client_votes.pop(client_id)
                self._block_votes[old_block].discard(client_id)
            logger.info(f"Audience -1 → {len(self.clients)} connected")
            await self._broadcast_audience_count()

    def _build_welcome(self, client_id: str) -> dict:
        """Build the initial state message for a new audience member."""
        state = self._get_current_state()
        return {
            "type": "welcome",
            "client_id": client_id,
            "audience_count": len(self.clients),
            "state": state,
            "phase_info": self._get_phase_info(state.get("sort_state", "idle"), state.get("mode", "idle")),
            "votes": self.get_vote_results(),
            "vote_round": self._vote_round,
            "last_winner": self._last_winner,
        }

    # ── Message handling ─────────────────────────────────────────────

    async def _handle_message(self, message: str, websocket: WebSocketServerProtocol,
                              client_id: str) -> None:
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "vote_block":
                block_id = data.get("block_id")
                if isinstance(block_id, int):
                    await self._handle_block_vote(client_id, block_id, websocket)

            elif msg_type == "tilt":
                beta = float(data.get("beta", 0))
                gamma = float(data.get("gamma", 0))
                self._tilts[client_id] = (beta, gamma)

            elif msg_type == "reaction":
                emoji = data.get("emoji", "")
                await self._handle_reaction(client_id, emoji)

        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    async def _handle_block_vote(self, client_id: str, block_id: int,
                                  websocket: WebSocketServerProtocol) -> None:
        """Handle a client voting for a specific block."""
        # Remove previous vote if any
        if client_id in self._client_votes:
            old_block = self._client_votes[client_id]
            self._block_votes[old_block].discard(client_id)

        # Record new vote
        self._client_votes[client_id] = block_id
        self._block_votes[block_id].add(client_id)

        # Ack to voter
        await self._safe_send(websocket, {
            "type": "vote_ack",
            "block_id": block_id,
            "your_vote": True,
        })

        # Broadcast updated tallies to everyone
        await self._broadcast_votes()

    async def _handle_reaction(self, client_id: str, emoji: str) -> None:
        """Handle an emoji reaction with cooldown."""
        ALLOWED = {"👏", "🔥", "😮", "💀", "🤖", "🧠"}
        if emoji not in ALLOWED:
            return

        now = time.time()
        last = self._reaction_cooldowns.get(client_id, 0)
        if now - last < 1.0:  # 1-second cooldown per client
            return
        self._reaction_cooldowns[client_id] = now

        await self._broadcast({
            "type": "reaction",
            "emoji": emoji,
            "count": len(self.clients),  # rough "energy" signal
        })

    # ── State helpers ────────────────────────────────────────────────

    def _get_current_state(self) -> dict:
        if self.state_manager:
            return self.state_manager.get_snapshot()
        return {"mode": "idle", "sort_state": "idle", "detected_blocks": [], "tetris_score": 0}

    def _get_phase_info(self, sort_state: str, mode: str) -> dict:
        """Determine the audience-facing phase from backend state."""
        if mode == "chimp":
            return PHASE_INFO.get(sort_state, PHASE_INFO["idle"])
        return PHASE_INFO.get(mode, PHASE_INFO["idle"])

    # ── Broadcast loops ──────────────────────────────────────────────

    async def _state_broadcast_loop(self) -> None:
        """Push live state to all audience clients at ~2fps."""
        while self._running:
            if self.clients and self.state_manager:
                state = self._get_current_state()
                sort_state = state.get("sort_state", "idle")
                mode = state.get("mode", "idle")
                phase = self._get_phase_info(sort_state, mode)

                avg_tilt = self.get_average_tilt()

                msg = {
                    "type": "state_update",
                    "state": state,
                    "phase": phase,
                    "audience_count": len(self.clients),
                    "votes": self.get_vote_results(),
                    "vote_round": self._vote_round,
                    "last_winner": self._last_winner,
                    "avg_tilt": {"pitch": avg_tilt[0], "roll": avg_tilt[1]},
                }
                await self._broadcast(msg)

            await asyncio.sleep(0.5)

    async def _broadcast_votes(self) -> None:
        """Broadcast current vote tallies."""
        await self._broadcast({
            "type": "vote_update",
            "votes": self.get_vote_results(),
            "vote_round": self._vote_round,
            "leading": self.get_winning_block_id(),
        })

    async def _broadcast_audience_count(self) -> None:
        await self._broadcast({
            "type": "audience_count",
            "count": len(self.clients),
        })

    async def broadcast_winner(self, winner: dict) -> None:
        """Called by main.py after consuming a vote — tells everyone who won."""
        await self._broadcast({
            "type": "vote_winner",
            "block_id": winner["block_id"],
            "voter_count": winner["voter_count"],
            "voter_ids": winner["voter_ids"],
            "round": winner["round"],
        })

    async def broadcast_action(self, action_type: str, detail: dict) -> None:
        """Broadcast a robot action so the audience sees cause → effect."""
        await self._broadcast({
            "type": "robot_action",
            "action": action_type,
            **detail,
        })

    # ── Transport ────────────────────────────────────────────────────

    async def _broadcast(self, message: dict) -> None:
        if not self.clients:
            return
        msg = json.dumps(message)
        dead = set()
        for client in self.clients.copy():
            try:
                await client.send(msg)
            except Exception:
                dead.add(client)
        for c in dead:
            self.clients.discard(c)

    async def _safe_send(self, websocket, message: dict) -> None:
        try:
            await websocket.send(json.dumps(message))
        except Exception:
            pass

    # ── Lifecycle ────────────────────────────────────────────────────

    async def start(self) -> None:
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets not installed")
            return

        self._running = True
        self._server = await websockets.serve(self.handler, self.host, self.port)
        self._broadcast_task = asyncio.create_task(self._state_broadcast_loop())

        logger.info(f"Audience server on ws://{self.host}:{self.port}")
        await self._server.wait_closed()

    async def stop(self) -> None:
        self._running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        for client in self.clients.copy():
            try:
                await client.close()
            except Exception:
                pass
        self.clients.clear()
        logger.info("Audience server stopped")
