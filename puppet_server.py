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

from hardware import (ArmController, MagnetDriver, HandToArmMapper,
                      GestureToGripper, TeachingRecorder, MotionPlayer,
                      create_gripper)


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("PuppetServer")


class PuppetServer:
    def __init__(self, host: str = "localhost", port: int = 8766, simulate: bool = True):
        self.host = host
        self.port = port
        self.simulate = simulate

        self.arm: Optional[ArmController] = None
        self.magnet: Optional[MagnetDriver] = None
        self.gripper = None
        self.mapper: Optional[HandToArmMapper] = None
        self.gesture: Optional[GestureToGripper] = None
        self.recorder: Optional[TeachingRecorder] = None
        self.player: Optional[MotionPlayer] = None

        self.clients: Set[WebSocketServerProtocol] = set()
        self._server = None
        self._streaming = True

        self._last_angles: tuple = (90, 90, 90, 90, 90)
        self._frame_count = 0
        self._arm_port: Optional[str] = None
        self._magnet_port: Optional[str] = None
        self._state_manager = None

    def set_state_manager(self, state_manager) -> None:
        self._state_manager = state_manager

    def initialize(self) -> bool:
        try:
            arm_kwargs = {"simulate": self.simulate}
            magnet_kwargs = {"simulate": self.simulate}
            if self._arm_port:
                arm_kwargs["port"] = self._arm_port
            if self._magnet_port:
                magnet_kwargs["port"] = self._magnet_port
            self.arm = ArmController(**arm_kwargs)
            self.magnet = MagnetDriver(**magnet_kwargs)
            self.gripper = create_gripper("magnet", self.magnet)
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

        # Send initial state sync
        if self._state_manager:
            try:
                await websocket.send(self._state_manager.get_state_sync_message())
            except Exception:
                pass

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
        except json.JSONDecodeError:
            await self._send_error(websocket, "Invalid JSON")
            return

        msg_type = data.get("type") or data.get("command")

        try:
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
                if not name:
                    await self._send_error(websocket, "play_motion requires 'name'")
                    return
                motion = self.recorder.get_motion(name)
                if motion:
                    self.player.play(motion)
                    logger.info(f"Playing motion: {name}")
                else:
                    await self._send_error(websocket, f"Motion '{name}' not found")

            elif msg_type == "list_motions":
                await websocket.send(json.dumps({
                    "type": "motion_list",
                    "motions": self.recorder.list_motions()
                }))

            elif msg_type == "set_speed":
                self.player.set_speed(data.get("speed", 1.0))

            elif msg_type == "gripper":
                position = data.get("position", 0.0)
                if self.gripper:
                    self.gripper.set_position(position)

            elif msg_type == "get_state":
                if self._state_manager:
                    await websocket.send(self._state_manager.get_state_sync_message())

            else:
                logger.warning(f"Unknown message type: {msg_type}")

        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"Bad message data for '{msg_type}': {e}")
            await self._send_error(websocket, str(e))
        except Exception as e:
            logger.exception(f"Unexpected error handling '{msg_type}'")
            await self._send_error(websocket, "Internal server error")

    async def _send_error(self, websocket: WebSocketServerProtocol, detail: str) -> None:
        try:
            await websocket.send(json.dumps({"type": "error", "detail": detail}))
        except Exception:
            pass

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

        if self.gripper:
            self.gripper.set_position(1.0 if is_pinching else 0.0)
        else:
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

    async def _heartbeat_loop(self) -> None:
        """Send heartbeat every 5 seconds."""
        while self._streaming:
            if self.clients and self._state_manager:
                msg = self._state_manager.heartbeat_message()
                dead = set()
                for client in self.clients.copy():
                    try:
                        await client.send(msg)
                    except Exception:
                        dead.add(client)
                for c in dead:
                    self.clients.discard(c)
            await asyncio.sleep(5)

    async def playback_loop(self) -> None:
        while self._streaming:
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

        self._streaming = True
        await asyncio.gather(
            self._server.wait_closed(),
            self.playback_loop(),
            self._heartbeat_loop(),
        )

    async def stop(self) -> None:
        self._streaming = False

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
    parser.add_argument("--arm-port", type=str, default=None, help="Serial port for arm controller")
    parser.add_argument("--magnet-port", type=str, default=None, help="Serial port for magnet driver")
    args = parser.parse_args()

    server = PuppetServer(args.host, args.port, args.simulate)
    if args.arm_port:
        server._arm_port = args.arm_port
    if args.magnet_port:
        server._magnet_port = args.magnet_port

    try:
        await server.start()
    except KeyboardInterrupt:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
