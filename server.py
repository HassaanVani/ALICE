import asyncio
import json
import logging
from typing import Set, Optional

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

from brain import InferencePipeline


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("TensorServer")


class TensorStreamServer:
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Set[WebSocketServerProtocol] = set()
        self.pipeline: Optional[InferencePipeline] = None
        self._server = None
        self._streaming = False
        self._fps = 30
        self._selected_layer: Optional[str] = None
    
    def set_pipeline(self, pipeline: InferencePipeline) -> None:
        self.pipeline = pipeline
    
    async def register(self, websocket: WebSocketServerProtocol) -> None:
        self.clients.add(websocket)
        logger.info(f"Client connected. Total: {len(self.clients)}")
    
    async def unregister(self, websocket: WebSocketServerProtocol) -> None:
        self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total: {len(self.clients)}")
    
    async def handler(self, websocket: WebSocketServerProtocol) -> None:
        await self.register(websocket)
        
        try:
            async for message in websocket:
                await self._handle_message(message, websocket)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)
    
    async def _handle_message(self, message: str, websocket: WebSocketServerProtocol) -> None:
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
        
        except json.JSONDecodeError:
            pass
    
    async def broadcast(self, data: bytes) -> None:
        if not self.clients:
            return
        
        dead_clients = set()
        
        for client in self.clients:
            try:
                await client.send(data)
            except websockets.exceptions.ConnectionClosed:
                dead_clients.add(client)
        
        for client in dead_clients:
            self.clients.discard(client)
    
    async def stream_loop(self) -> None:
        self._streaming = True
        interval = 1.0 / self._fps
        
        while self._streaming:
            if self.clients and self.pipeline:
                payload = self.pipeline.get_websocket_payload(self._selected_layer)
                if payload:
                    await self.broadcast(payload)
            
            await asyncio.sleep(interval)
    
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
        
        await asyncio.gather(
            self._server.wait_closed(),
            self.stream_loop()
        )
    
    async def stop(self) -> None:
        self._streaming = False
        
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        for client in self.clients.copy():
            await client.close()
        
        self.clients.clear()
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
