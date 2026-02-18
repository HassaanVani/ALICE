"""Audience participation server — WebSocket on port 8767 for LAN access."""

import asyncio
import json
import logging
import time
from collections import defaultdict
from typing import Dict, Optional, Set, Tuple

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

logger = logging.getLogger("AudienceServer")


class AudienceServer:
    """WebSocket server for audience participation — votes and tilt control."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8767):
        self.host = host
        self.port = port
        self.clients: Set[WebSocketServerProtocol] = set()
        self._server = None
        self._running = False

        # Vote tallying
        self._votes: Dict[str, int] = defaultdict(int)
        self._vote_round: int = 0
        self._vote_deadline: float = 0.0

        # Tilt averaging
        self._tilts: Dict[str, Tuple[float, float]] = {}  # client_id -> (alpha, beta)

    @property
    def client_count(self) -> int:
        return len(self.clients)

    async def handler(self, websocket: WebSocketServerProtocol) -> None:
        client_id = str(id(websocket))
        self.clients.add(websocket)
        logger.info(f"Audience member joined. Total: {len(self.clients)}")

        try:
            await websocket.send(json.dumps({
                "type": "welcome",
                "client_id": client_id,
                "audience_count": len(self.clients),
            }))

            async for message in websocket:
                await self._handle_message(message, websocket, client_id)
        except Exception:
            pass
        finally:
            self.clients.discard(websocket)
            self._tilts.pop(client_id, None)
            logger.info(f"Audience member left. Total: {len(self.clients)}")

    async def _handle_message(self, message: str, websocket: WebSocketServerProtocol,
                              client_id: str) -> None:
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "vote":
                action = data.get("action", "")
                self._votes[action] += 1
                # Broadcast updated tally
                await self._broadcast_vote_update()

            elif msg_type == "tilt":
                alpha = data.get("alpha", 0.0)
                beta = data.get("beta", 0.0)
                self._tilts[client_id] = (alpha, beta)

        except json.JSONDecodeError:
            pass

    def get_winning_vote(self) -> Optional[str]:
        """Return the action with the most votes, or None if no votes."""
        if not self._votes:
            return None
        winner = max(self._votes, key=self._votes.get)
        return winner

    def get_winning_block_id(self) -> Optional[int]:
        """Extract block_id from winning vote like 'block_5'."""
        winner = self.get_winning_vote()
        if winner and winner.startswith("block_"):
            try:
                return int(winner.split("_")[1])
            except (IndexError, ValueError):
                pass
        return None

    def clear_votes(self) -> None:
        self._votes.clear()
        self._vote_round += 1

    def get_average_tilt(self) -> Tuple[float, float]:
        """Return average tilt across all connected audience devices."""
        if not self._tilts:
            return (0.0, 0.0)
        alphas = [t[0] for t in self._tilts.values()]
        betas = [t[1] for t in self._tilts.values()]
        return (sum(alphas) / len(alphas), sum(betas) / len(betas))

    async def _broadcast_vote_update(self) -> None:
        if not self.clients:
            return
        msg = json.dumps({
            "type": "vote_update",
            "votes": dict(self._votes),
            "round": self._vote_round,
        })
        dead = set()
        for client in self.clients.copy():
            try:
                await client.send(msg)
            except Exception:
                dead.add(client)
        for c in dead:
            self.clients.discard(c)

    async def broadcast(self, message: dict) -> None:
        """Broadcast a JSON message to all audience clients."""
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

    async def start(self) -> None:
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets not installed")
            return

        self._running = True
        self._server = await websockets.serve(
            self.handler,
            self.host,
            self.port
        )

        logger.info(f"Audience server on ws://{self.host}:{self.port}")
        await self._server.wait_closed()

    async def stop(self) -> None:
        self._running = False
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
