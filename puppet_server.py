import asyncio
import json
import logging
import time
from typing import Optional, Set

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketServerProtocol = object  # fallback for type hints

from hardware import (ArmController, MagnetDriver, HandToArmMapper,
                      GestureToGripper, TeachingRecorder, MotionPlayer,
                      create_gripper, PuppeteerState, ArmFrame)
from hardware.puppeteer import get_websocket_payload


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("PuppetServer")


class PuppetServer:
    """Sole owner of puppeteer mode: state machine, arm control, recording, playback, broadcasting."""

    def __init__(self, host: str = "localhost", port: int = 8766, simulate: bool = True,
                 arm: Optional[ArmController] = None,
                 magnet: Optional[MagnetDriver] = None,
                 gripper=None):
        self.host = host
        self.port = port
        self.simulate = simulate

        # Use externally-provided hardware if given, otherwise create in initialize()
        self.arm: Optional[ArmController] = arm
        self.magnet: Optional[MagnetDriver] = magnet
        self.gripper = gripper
        self._owns_hardware = arm is None  # only disconnect what we created

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

        # State machine
        self._state: PuppeteerState = PuppeteerState.IDLE

        # Reference to TensorStreamServer for activation broadcasting
        self._tensor_server = None

        # Last ArmFrame for velocity/acceleration tracking
        self._last_arm_frame: Optional[ArmFrame] = None

    @property
    def state(self) -> PuppeteerState:
        return self._state

    def set_state_manager(self, state_manager) -> None:
        self._state_manager = state_manager

    def set_tensor_server(self, tensor_server) -> None:
        """Wire the TensorStreamServer so we can broadcast activations to dashboard clients."""
        self._tensor_server = tensor_server

    # ── State machine transitions ──────────────────────────────────

    def go_live(self) -> None:
        """Enter LIVE mode — hand tracking drives the arm."""
        self._state = PuppeteerState.LIVE
        self._last_arm_frame = None
        if self.mapper:
            self.mapper.reset()
        self._broadcast_state()
        logger.info("Puppet state → LIVE")

    def start_recording(self, name: str) -> None:
        """Enter RECORDING mode — hand tracking drives arm + records frames."""
        if self.recorder:
            self.recorder.start_recording(name)
        self._state = PuppeteerState.RECORDING
        self._broadcast_state()
        logger.info(f"Puppet state → RECORDING ({name})")

    def stop_recording(self) -> Optional[object]:
        """Stop recording, return the captured motion, go to LIVE."""
        motion = None
        if self.recorder:
            motion = self.recorder.stop_recording()
        self._state = PuppeteerState.LIVE
        self._broadcast_state()
        if motion:
            logger.info(f"Recording complete: {motion.name} ({len(motion.frames)} frames)")
        return motion

    def start_playback(self, name: str) -> bool:
        """Enter PLAYBACK mode — replay a recorded motion."""
        if not self.recorder or not self.player:
            return False
        motion = self.recorder.get_motion(name)
        if not motion:
            return False
        if not self.player.play(motion):
            return False
        self._state = PuppeteerState.PLAYBACK
        self._broadcast_state()
        logger.info(f"Puppet state → PLAYBACK ({name})")
        return True

    def stop_puppet(self) -> None:
        """Return to IDLE — stop everything."""
        if self.player and self.player.is_playing:
            self.player.stop()
        if self.recorder and self.recorder.is_recording:
            self.recorder.stop_recording()
        self._state = PuppeteerState.IDLE
        self._last_arm_frame = None
        self._broadcast_state()
        logger.info("Puppet state → IDLE")

    # ── Broadcasting ───────────────────────────────────────────────

    def _broadcast_state(self) -> None:
        """Broadcast current puppet state to all connected puppet clients."""
        if self._state_manager:
            self._state_manager.update_puppeteer_state(self._state.value)

        msg = json.dumps({"type": "puppet_state", "state": self._state.value})
        asyncio.ensure_future(self._broadcast_to_clients(msg))

    async def _broadcast_to_clients(self, message: str) -> None:
        dead = set()
        for client in self.clients.copy():
            try:
                await client.send(message)
            except Exception:
                dead.add(client)
        for c in dead:
            self.clients.discard(c)

    async def _broadcast_activations(self, arm_frame: ArmFrame) -> None:
        """Send neural activation payload to tensor server (dashboard) clients."""
        if not self._tensor_server or not self._tensor_server.clients:
            return

        payload = get_websocket_payload(arm_frame)
        dead = set()
        for client in self._tensor_server.clients.copy():
            try:
                await client.send(payload)
            except Exception:
                dead.add(client)
        for c in dead:
            self._tensor_server.clients.discard(c)

    # ── Hardware init ──────────────────────────────────────────────

    def initialize(self) -> bool:
        try:
            # Only create hardware if not externally provided
            if self.arm is None:
                arm_kwargs = {"simulate": self.simulate}
                if self._arm_port:
                    arm_kwargs["port"] = self._arm_port
                self.arm = ArmController(**arm_kwargs)
                self.arm.connect()

            if self.magnet is None:
                magnet_kwargs = {"simulate": self.simulate}
                if self._magnet_port:
                    magnet_kwargs["port"] = self._magnet_port
                self.magnet = MagnetDriver(**magnet_kwargs)

            if self.gripper is None:
                self.gripper = create_gripper("magnet", self.magnet)

            self.mapper = HandToArmMapper()
            self.gesture = GestureToGripper()
            self.recorder = TeachingRecorder(self.mapper)
            self.player = MotionPlayer(self.arm, self.magnet)

            logger.info("Puppet server hardware initialized")
            return True
        except Exception as e:
            logger.error(f"Init failed: {e}")
            return False

    # ── WebSocket handler ──────────────────────────────────────────

    async def handler(self, websocket: WebSocketServerProtocol) -> None:
        self.clients.add(websocket)
        logger.info(f"Puppet client connected. Total: {len(self.clients)}")

        # Send initial state sync
        try:
            await websocket.send(json.dumps({
                "type": "puppet_state", "state": self._state.value
            }))
            if self._state_manager:
                await websocket.send(self._state_manager.get_state_sync_message())
        except Exception as e:
            logger.debug(f"Failed to send initial state sync: {e}")

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
                self.start_recording(name)

            elif msg_type == "stop_teaching":
                motion = self.stop_recording()
                if motion:
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
                if not self.start_playback(name):
                    await self._send_error(websocket, f"Motion '{name}' not found or empty")

            elif msg_type == "stop_playback":
                if self.player and self.player.is_playing:
                    self.player.stop()
                self._state = PuppeteerState.LIVE
                self._broadcast_state()

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
                await websocket.send(json.dumps({
                    "type": "puppet_state", "state": self._state.value
                }))
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
        except Exception as e:
            logger.debug(f"Failed to send error to client: {e}")

    # ── Hand position handling (core of live/recording) ────────────

    async def _handle_hand_position(self, data: dict, websocket: WebSocketServerProtocol) -> None:
        # Ignore hand data when in IDLE or PLAYBACK
        if self._state in (PuppeteerState.IDLE, PuppeteerState.PLAYBACK):
            return

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

        if self._state == PuppeteerState.RECORDING and self.recorder.is_recording:
            self.recorder.record_frame(hand_x, hand_y, hand_z, is_pinching)

        # Build ArmFrame for activation encoding
        now = time.time()
        velocities = (0.0,) * 5
        accelerations = (0.0,) * 5
        if self._last_arm_frame:
            dt = now - self._last_arm_frame.timestamp
            if dt > 0:
                velocities = tuple(
                    (a - b) / dt for a, b in zip(angles, self._last_arm_frame.angles)
                )
                accelerations = tuple(
                    (v - pv) / dt for v, pv in zip(velocities, self._last_arm_frame.velocities)
                )

        arm_frame = ArmFrame(
            timestamp=now,
            angles=angles,
            velocities=velocities,
            accelerations=accelerations,
        )
        self._last_arm_frame = arm_frame

        # Update state manager
        if self._state_manager:
            self._state_manager.update_arm(tuple(angles), "moving")

        # Broadcast activations to tensor/dashboard clients
        await self._broadcast_activations(arm_frame)

        # Broadcast arm state to ALL connected puppet clients (throttled)
        self._frame_count += 1
        if self._frame_count % 3 == 0:
            arm_msg = json.dumps({
                "type": "arm_position",
                "angles": list(angles),
                "gripper": is_pinching
            })
            await self._broadcast_to_clients(arm_msg)

    # ── Background loops ───────────────────────────────────────────

    async def _heartbeat_loop(self) -> None:
        """Send heartbeat every 5 seconds."""
        while self._streaming:
            if self.clients and self._state_manager:
                msg = self._state_manager.heartbeat_message()
                await self._broadcast_to_clients(msg)
            await asyncio.sleep(5)

    async def playback_loop(self) -> None:
        while self._streaming:
            if self.player and self.player.is_playing:
                still_playing = self.player.update()
                if not still_playing and self._state == PuppeteerState.PLAYBACK:
                    self._state = PuppeteerState.LIVE
                    self._broadcast_state()
                    logger.info("Playback complete → LIVE")
            await asyncio.sleep(0.05)

    # ── Server lifecycle ───────────────────────────────────────────

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
        self.stop_puppet()

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # Only disconnect hardware we created ourselves
        if self._owns_hardware and self.arm:
            self.arm.home()
            self.arm.disconnect()

        logger.info("Puppet server stopped")


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
