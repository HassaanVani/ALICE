import asyncio
import json
import logging
from typing import Optional, Set

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

from hardware import ArmController, MagnetDriver, HandToArmMapper, GestureToGripper, TeachingRecorder, MotionPlayer


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("PuppetServer")


class PuppetServer:
    def __init__(self, host: str = "localhost", port: int = 8766, simulate: bool = True):
        self.host = host
        self.port = port
        self.simulate = simulate
        
        self.arm: Optional[ArmController] = None
        self.magnet: Optional[MagnetDriver] = None
        self.mapper: Optional[HandToArmMapper] = None
        self.gesture: Optional[GestureToGripper] = None
        self.recorder: Optional[TeachingRecorder] = None
        self.player: Optional[MotionPlayer] = None
        
        self.clients: Set[WebSocketServerProtocol] = set()
        self._server = None
        
        self._last_angles: tuple = (90, 90, 90, 90, 90)
        self._frame_count = 0
    
    def initialize(self) -> bool:
        try:
            self.arm = ArmController(simulate=self.simulate)
            self.magnet = MagnetDriver(simulate=self.simulate)
            self.mapper = HandToArmMapper()
            self.gesture = GestureToGripper()
            self.recorder = TeachingRecorder(self.mapper)
            self.player = MotionPlayer(self.arm, self.magnet)
            
            self.arm.connect()
            logger.info("Hardware initialized")
            return True
        except Exception as e:
            logger.error(f"Init failed: {e}")
            return False
    
    async def handler(self, websocket: WebSocketServerProtocol) -> None:
        self.clients.add(websocket)
        logger.info(f"Puppet client connected. Total: {len(self.clients)}")
        
        try:
            async for message in websocket:
                await self._handle_message(message, websocket)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            logger.info(f"Client disconnected. Total: {len(self.clients)}")
    
    async def _handle_message(self, message: str, websocket: WebSocketServerProtocol) -> None:
        try:
            data = json.loads(message)
            msg_type = data.get("type") or data.get("command")
            
            if msg_type == "hand_position":
                await self._handle_hand_position(data, websocket)
            
            elif msg_type == "start_teaching":
                name = data.get("name", f"motion_{len(self.recorder.motions)}")
                self.recorder.start_recording(name)
                logger.info(f"Teaching started: {name}")
            
            elif msg_type == "stop_teaching":
                motion = self.recorder.stop_recording()
                if motion:
                    logger.info(f"Teaching complete: {motion.name} ({len(motion.frames)} frames)")
                    await websocket.send(json.dumps({
                        "type": "teaching_complete",
                        "name": motion.name,
                        "frames": len(motion.frames),
                        "duration": motion.duration
                    }))
            
            elif msg_type == "play_motion":
                name = data.get("name")
                motion = self.recorder.get_motion(name)
                if motion:
                    self.player.play(motion)
                    logger.info(f"Playing motion: {name}")
            
            elif msg_type == "list_motions":
                await websocket.send(json.dumps({
                    "type": "motion_list",
                    "motions": self.recorder.list_motions()
                }))
            
            elif msg_type == "set_speed":
                self.player.set_speed(data.get("speed", 1.0))
        
        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    async def _handle_hand_position(self, data: dict, websocket: WebSocketServerProtocol) -> None:
        pos = data.get("position", {})
        hand_x = pos.get("x", 0.5)
        hand_y = pos.get("y", 0.5)
        hand_z = pos.get("z", 0.5)
        
        gestures = data.get("gestures", {})
        is_pinching = gestures.get("pinching", False)
        
        landmarks = data.get("landmarks", [])
        if landmarks:
            landmarks_dicts = [{"x": lm["x"], "y": lm["y"], "z": lm.get("z", 0)} for lm in landmarks]
            self.gesture.update(landmarks_dicts)
        
        angles = self.mapper.hand_to_angles(hand_x, hand_y, hand_z)
        self._last_angles = angles
        
        self.arm.move_to(angles, speed=2.0)
        self.magnet.toggle(is_pinching)
        
        if self.recorder.is_recording:
            self.recorder.record_frame(hand_x, hand_y, hand_z, is_pinching)
        
        self._frame_count += 1
        if self._frame_count % 10 == 0:
            await websocket.send(json.dumps({
                "type": "arm_position",
                "angles": list(angles),
                "gripper": is_pinching
            }))
    
    async def playback_loop(self) -> None:
        while True:
            if self.player and self.player.is_playing:
                self.player.update()
            await asyncio.sleep(0.05)
    
    async def start(self) -> None:
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets not installed")
            return
        
        if not self.initialize():
            return
        
        self._server = await websockets.serve(
            self.handler,
            self.host,
            self.port
        )
        
        logger.info(f"Puppet server on ws://{self.host}:{self.port}")
        
        await asyncio.gather(
            self._server.wait_closed(),
            self.playback_loop()
        )
    
    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        if self.arm:
            self.arm.home()
            self.arm.disconnect()
        
        logger.info("Server stopped")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="A.L.I.C.E. Puppet Mode Server")
    parser.add_argument("--host", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--simulate", action="store_true", default=True)
    args = parser.parse_args()
    
    server = PuppetServer(args.host, args.port, args.simulate)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
