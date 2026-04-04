import asyncio
import json
import logging
from typing import Set, Optional, Callable

try:
    import websockets
    from websockets.asyncio.server import ServerConnection
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    ServerConnection = object

from brain import InferencePipeline
from modes import DEMO_VISIBLE_MODES


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("TensorServer")


class TensorStreamServer:
    MAX_CLIENT_QUEUE = 8  # drop frames if client is this far behind

    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Set[ServerConnection] = set()
        self._client_queues: dict[ServerConnection, asyncio.Queue] = {}
        self.pipeline: Optional[InferencePipeline] = None
        self._server = None
        self._streaming = False
        self._fps = 30
        self._selected_layer: Optional[str] = None
        self._state_manager = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._switch_mode_callback: Optional[Callable[[str], None]] = None
        self._camera_stream_clients: Set[ServerConnection] = set()
        self._camera_frame_getter: Optional[Callable] = None
        self._recorder = None
        self._interaction_callback: Optional[Callable] = None

    def set_pipeline(self, pipeline: InferencePipeline) -> None:
        self.pipeline = pipeline

    def set_state_manager(self, state_manager) -> None:
        self._state_manager = state_manager

    def set_switch_mode_callback(self, callback: Callable[[str], None]) -> None:
        self._switch_mode_callback = callback

    def set_camera_frame_getter(self, getter: Callable) -> None:
        self._camera_frame_getter = getter

    def set_recorder(self, recorder) -> None:
        """Set reference to SessionRecorder for recording commands."""
        self._recorder = recorder

    def set_interaction_callback(self, callback: Callable) -> None:
        """Set callback for fetch_object/hand_over commands. Called with (label, hand_over)."""
        self._interaction_callback = callback

    def set_protocol_dispatch(self, callback: Callable) -> None:
        """Set callback for protocol dispatch. Called with (protocol_name, params) -> InteractionResult."""
        self._protocol_dispatch = callback

    async def register(self, websocket: ServerConnection) -> None:
        self.clients.add(websocket)
        self._client_queues[websocket] = asyncio.Queue(maxsize=self.MAX_CLIENT_QUEUE)
        asyncio.create_task(self._client_sender(websocket))
        logger.info(f"Client connected. Total: {len(self.clients)}")

        # Send initial state sync (with available modes filtered for demo)
        if self._state_manager:
            try:
                await websocket.send(self._state_sync_with_modes())
            except Exception as e:
                logger.debug(f"Failed to send initial state sync: {e}")

    async def unregister(self, websocket: ServerConnection) -> None:
        self.clients.discard(websocket)
        self._camera_stream_clients.discard(websocket)
        self._client_queues.pop(websocket, None)
        logger.info(f"Client disconnected. Total: {len(self.clients)}")

    async def handler(self, websocket: ServerConnection) -> None:
        await self.register(websocket)

        try:
            async for message in websocket:
                await self._handle_message(message, websocket)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)

    async def _handle_message(self, message: str, websocket: ServerConnection) -> None:
        try:
            data = json.loads(message)
            command = data.get("command")

            if command == "freeze":
                if self.pipeline:
                    frozen = data.get("frozen", False)
                    if frozen:
                        self.pipeline.freeze()
                    else:
                        self.pipeline.unfreeze()
                    logger.info(f"Inference {'frozen' if frozen else 'unfrozen'}")

            elif command == "select_layer":
                self._selected_layer = data.get("layer")
                logger.info(f"Selected layer: {self._selected_layer}")

            elif command == "set_fps":
                self._fps = max(1, min(60, data.get("fps", 30)))
                logger.info(f"FPS set to: {self._fps}")

            elif command == "get_layers":
                if self.pipeline:
                    layers = self.pipeline.hooks.layer_names
                    await websocket.send(json.dumps({"type": "layers", "layers": layers}))

            elif command == "switch_mode":
                new_mode = data.get("mode")
                if new_mode and self._switch_mode_callback:
                    try:
                        self._switch_mode_callback(new_mode)
                        await websocket.send(json.dumps({
                            "type": "mode_switched",
                            "mode": new_mode
                        }))
                    except Exception as e:
                        await websocket.send(json.dumps({
                            "type": "error",
                            "detail": f"Mode switch failed: {e}"
                        }))

            elif command == "stream_camera":
                self._camera_stream_clients.add(websocket)
                logger.info("Camera streaming started for client")

            elif command == "stop_camera":
                self._camera_stream_clients.discard(websocket)

            elif command == "get_state":
                if self._state_manager:
                    await websocket.send(self._state_sync_with_modes())

            elif command == "start_recording":
                if self._recorder and not self._recorder.is_recording:
                    self._recorder.start()
                    await websocket.send(json.dumps({"type": "recording_started"}))
                    logger.info("Recording started via dashboard")

            elif command == "stop_recording":
                if self._recorder and self._recorder.is_recording:
                    path = self._recorder.stop()
                    await websocket.send(json.dumps({
                        "type": "recording_stopped",
                        "path": str(path) if path else None,
                    }))
                    logger.info("Recording stopped via dashboard")

            elif command == "snapshot":
                if self._state_manager:
                    snapshot = self._state_manager.get_snapshot()
                    await websocket.send(json.dumps({
                        "type": "snapshot",
                        "state": snapshot,
                    }))

            elif command == "fetch_object":
                label = data.get("label")
                if label and self._interaction_callback:
                    asyncio.create_task(self._handle_fetch(websocket, label))

            elif command == "hand_over":
                label = data.get("label")
                if label and self._interaction_callback:
                    asyncio.create_task(self._handle_fetch(websocket, label, hand_over=True))

            elif command == "move_near":
                source = data.get("source")
                target = data.get("target")
                if source and target and self._interaction_callback:
                    asyncio.create_task(self._handle_interaction_cmd(
                        websocket, "move_near", source=source, target=target,
                        offset_px=data.get("offset_px", 80),
                    ))

            elif command == "throw_away":
                label = data.get("label")
                if label and self._interaction_callback:
                    asyncio.create_task(self._handle_interaction_cmd(
                        websocket, "throw_away", source=label,
                    ))

            elif command == "run_protocol":
                protocol_name = data.get("protocol")
                params = data.get("params", {})
                if protocol_name and hasattr(self, '_protocol_dispatch') and self._protocol_dispatch:
                    asyncio.create_task(self._handle_protocol(
                        websocket, protocol_name, params,
                    ))

        except json.JSONDecodeError as e:
            logger.debug(f"Malformed JSON from client: {e}")

    async def _handle_fetch(self, websocket: ServerConnection, label: str,
                             hand_over: bool = False) -> None:
        """Handle an async fetch/hand_over command."""
        try:
            result = await self._interaction_callback(label, hand_over)
            await websocket.send(json.dumps({
                "type": "interaction_result",
                "action": result.get("action", "fetch"),
                "label": label,
                "success": result.get("success", False),
                "message": result.get("message", ""),
            }))
        except Exception as e:
            await websocket.send(json.dumps({
                "type": "error",
                "detail": f"Interaction failed: {e}",
            }))

    async def _handle_interaction_cmd(self, websocket: ServerConnection,
                                       action: str, source: str = "",
                                       target: str = "", offset_px: int = 80) -> None:
        """Handle move_near, throw_away, and future interaction commands."""
        try:
            result = await self._interaction_callback(
                source, False,
                move_near_target=target if action == "move_near" else None,
                throw_away=action == "throw_away",
                offset_px=offset_px,
            )
            await websocket.send(json.dumps({
                "type": "interaction_result",
                "action": result.get("action", action),
                "label": source,
                "success": result.get("success", False),
                "message": result.get("message", ""),
            }))
        except Exception as e:
            await websocket.send(json.dumps({
                "type": "error",
                "detail": f"Interaction failed: {e}",
            }))

    async def _handle_protocol(self, websocket: ServerConnection,
                               protocol_name: str, params: dict) -> None:
        """Handle a run_protocol command from the dashboard."""
        try:
            result = await self._protocol_dispatch(protocol_name, params)
            await websocket.send(json.dumps({
                "type": "interaction_result",
                "action": result.action,
                "label": result.object_label,
                "success": result.success,
                "message": result.message,
            }))
        except Exception as e:
            await websocket.send(json.dumps({
                "type": "error",
                "detail": f"Protocol failed: {e}",
            }))

    def _state_sync_with_modes(self) -> str:
        """Return state_sync JSON with available_modes filtered for demos."""
        raw = self._state_manager.get_state_sync_message()
        msg = json.loads(raw)
        msg["available_modes"] = list(DEMO_VISIBLE_MODES)
        return json.dumps(msg)

    async def _client_sender(self, websocket: ServerConnection) -> None:
        """Per-client sender drains the queue — applies back-pressure."""
        queue = self._client_queues.get(websocket)
        if not queue:
            return
        try:
            while True:
                data = await queue.get()
                await websocket.send(data)
        except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
            pass
        finally:
            self.clients.discard(websocket)
            self._camera_stream_clients.discard(websocket)
            self._client_queues.pop(websocket, None)

    async def broadcast(self, data: bytes) -> None:
        if not self.clients:
            return

        for client in list(self.clients):
            queue = self._client_queues.get(client)
            if queue is None:
                continue
            if queue.full():
                # Drop oldest frame for this slow client
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                pass

    async def stream_loop(self) -> None:
        self._streaming = True
        interval = 1.0 / self._fps

        while self._streaming:
            if self.clients and self.pipeline:
                payload = self.pipeline.get_websocket_payload(self._selected_layer)
                if payload:
                    await self.broadcast(payload)

            await asyncio.sleep(interval)

    async def _state_broadcast_loop(self) -> None:
        """Broadcast full state to all dashboard clients at ~2fps."""
        while self._streaming:
            if self.clients and self._state_manager:
                msg = self._state_sync_with_modes()
                dead = set()
                for client in self.clients.copy():
                    try:
                        await client.send(msg)
                    except Exception:
                        dead.add(client)
                for c in dead:
                    self.clients.discard(c)
            await asyncio.sleep(0.5)

    async def _camera_stream_loop(self) -> None:
        """Stream JPEG frames at 15fps to requesting clients."""
        import cv2
        while self._streaming:
            if self._camera_stream_clients and self._camera_frame_getter:
                frame = self._camera_frame_getter()
                if frame is not None:
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    import base64
                    b64 = base64.b64encode(buf).decode("ascii")
                    msg = json.dumps({"type": "camera_frame", "jpeg_b64": b64})
                    dead = set()
                    for client in self._camera_stream_clients.copy():
                        try:
                            await client.send(msg)
                        except Exception:
                            dead.add(client)
                    for c in dead:
                        self._camera_stream_clients.discard(c)
            await asyncio.sleep(1.0 / 15)  # 15 fps

    async def start(self) -> None:
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets package not installed")
            return

        self._server = await websockets.serve(
            self.handler,
            self.host,
            self.port
        )

        logger.info(f"Tensor stream server started on ws://{self.host}:{self.port}")

        self._streaming = True
        tasks = [
            self._server.wait_closed(),
            self.stream_loop(),
            self._state_broadcast_loop(),
            self._camera_stream_loop(),
        ]
        await asyncio.gather(*tasks)

    async def stop(self) -> None:
        self._streaming = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        for client in self.clients.copy():
            await client.close()

        self.clients.clear()
        self._camera_stream_clients.clear()
        logger.info("Server stopped")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="A.L.I.C.E. Tensor Stream Server")
    parser.add_argument("--host", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    pipeline = InferencePipeline()

    server = TensorStreamServer(args.host, args.port)
    server.set_pipeline(pipeline)

    try:
        await server.start()
    except KeyboardInterrupt:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
