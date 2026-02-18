import asyncio
import argparse
import logging
from enum import Enum
from pathlib import Path
from typing import Optional

from config import load_config, AliceConfig
from selftest import SelfTest
from state import AliceStateManager
from recording import SessionRecorder, SessionPlayer
from hardware import (ArmController, MagnetDriver, CalibrationManager,
                      PuppeteerController, IMUSensor, PuppeteerState,
                      create_gripper, KinestheticTeacher)
from vision import (CameraManager, CameraConfig, CameraRole, CameraHealth,
                    ArucoDetector, BlockTracker)
from brain import InferencePipeline
from logic import ChimpSortFSM, SortState, TetrisAgent
from server import TensorStreamServer
from audience_server import AudienceServer
from narration import NarrationService


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("ALICE")

WEIGHTS_PATH = Path(__file__).parent / "brain" / "weights" / "block_recognizer.pth"
STATE_WEIGHTS_PATH = Path(__file__).parent / "brain" / "weights" / "block_state.pth"
RL_AGENT_PATH = Path(__file__).parent / "brain" / "weights" / "sort_agent.zip"


class Mode(Enum):
    CHIMP_SORT = "chimp"
    TETRIS = "tetris"
    CALIBRATE = "calibrate"
    PUPPETEER = "puppeteer"


class ALICE:
    def __init__(self, config: AliceConfig):
        self.config = config
        self.mode = Mode(config.mode)
        self.simulate = config.simulate

        self.arm: Optional[ArmController] = None
        self.magnet: Optional[MagnetDriver] = None
        self.gripper = None
        self.calibration: Optional[CalibrationManager] = None
        self.cameras: Optional[CameraManager] = None
        self.detector: Optional[ArucoDetector] = None
        self.tracker: Optional[BlockTracker] = None
        self.inference: Optional[InferencePipeline] = None
        self.sort_fsm: Optional[ChimpSortFSM] = None
        self.tetris: Optional[TetrisAgent] = None
        self.puppeteer: Optional[PuppeteerController] = None
        self.kinesthetic: Optional[KinestheticTeacher] = None

        self._running = False
        self._ws_server = TensorStreamServer(
            host=config.websocket.tensor_host,
            port=config.websocket.tensor_port
        )

        # State management
        self.state_manager = AliceStateManager()

        # Recording
        self.recorder = SessionRecorder(config.recording.output_dir)

        # Audience
        self.audience_server = AudienceServer(
            port=config.websocket.audience_port
        )

        # Narration
        self.narration = NarrationService(
            enabled=config.narration.enabled,
            voice_rate=config.narration.voice_rate,
            min_interval=config.narration.min_interval,
            model=config.narration.model,
        )
        self.narration.set_state_manager(self.state_manager)

        # RL agent
        self._rl_agent = None

    async def initialize(self) -> bool:
        logger.info(f"Initializing A.L.I.C.E. in {self.mode.value} mode (simulate={self.simulate})")

        try:
            hw = self.config.hardware
            arm_kwargs = {"simulate": self.simulate}
            magnet_kwargs = {"simulate": self.simulate}
            if hw.arm_port:
                arm_kwargs["port"] = hw.arm_port
            if hw.magnet_port:
                magnet_kwargs["port"] = hw.magnet_port

            self.arm = ArmController(**arm_kwargs)
            self.magnet = MagnetDriver(**magnet_kwargs)
            self.gripper = create_gripper("magnet", self.magnet)
            self.calibration = CalibrationManager()
            self.kinesthetic = KinestheticTeacher(self.arm)

            if not self.arm.connect():
                logger.warning("Arm connection failed, running in simulation")

            self.calibration.load()

            # Cameras from config
            self.cameras = CameraManager()
            oc = self.config.overhead_camera
            fc = self.config.front_camera
            overhead = CameraConfig(device_id=oc.device_id, width=oc.width,
                                    height=oc.height, fps=oc.fps, role=CameraRole.OVERHEAD)
            front = CameraConfig(device_id=fc.device_id, width=fc.width,
                                 height=fc.height, fps=fc.fps, role=CameraRole.FRONT_FACING)

            self.cameras.add_camera(overhead)
            self.cameras.add_camera(front)

            self.detector = ArucoDetector()
            self.tracker = BlockTracker()
            self.inference = InferencePipeline()

            if WEIGHTS_PATH.exists():
                self.inference.load_weights(WEIGHTS_PATH)
                logger.info(f"Loaded CNN weights from {WEIGHTS_PATH}")

            if STATE_WEIGHTS_PATH.exists():
                self.inference.load_state_weights(STATE_WEIGHTS_PATH)
                logger.info(f"Loaded state classifier weights from {STATE_WEIGHTS_PATH}")

            # Wire up servers
            self._ws_server.set_pipeline(self.inference)
            self._ws_server.set_state_manager(self.state_manager)
            self._ws_server.set_switch_mode_callback(self._handle_mode_switch)
            self._ws_server.set_camera_frame_getter(
                lambda: self.cameras.get_frame(CameraRole.OVERHEAD)
            )

            # Load RL agent if available
            self._load_rl_agent()

            # Setup current mode
            self._setup_mode(self.mode)

            # Update state
            self.state_manager.update_mode(self.mode.value)
            self.state_manager.update_cameras(self.cameras.get_all_health())

            logger.info("Initialization complete")
            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False

    def _setup_mode(self, mode: Mode) -> None:
        """Initialize subsystems for a given mode."""
        if mode == Mode.CHIMP_SORT:
            self.sort_fsm = ChimpSortFSM()
            self.sort_fsm.on_state_change(self._on_sort_state_change)
            self.sort_fsm.on_move(self._on_block_move)

        elif mode == Mode.TETRIS:
            self.tetris = TetrisAgent()
            self.tetris.on_action(self._on_tetris_action)

        elif mode == Mode.PUPPETEER:
            hw = self.config.hardware
            imu_kwargs = {"simulate": self.simulate}
            if hw.imu_port:
                imu_kwargs["port"] = hw.imu_port
            sensor = IMUSensor(**imu_kwargs)
            self.puppeteer = PuppeteerController(self.arm, sensor)
            self.puppeteer.on_frame(self._on_puppeteer_frame)

    def _teardown_mode(self) -> None:
        """Clean up current mode's subsystems."""
        if self.puppeteer:
            self.puppeteer.stop()
            self.puppeteer = None
        self.sort_fsm = None
        self.tetris = None

    def _handle_mode_switch(self, new_mode_str: str) -> None:
        """Called from WebSocket switch_mode command."""
        try:
            new_mode = Mode(new_mode_str)
        except ValueError:
            raise ValueError(f"Unknown mode: {new_mode_str}")
        self.switch_mode(new_mode)

    def switch_mode(self, new_mode: Mode) -> None:
        """Hot-swap to a new mode."""
        if new_mode == self.mode:
            return
        logger.info(f"Switching mode: {self.mode.value} -> {new_mode.value}")
        self._teardown_mode()
        self.mode = new_mode
        self._setup_mode(new_mode)
        self.state_manager.update_mode(new_mode.value)

    def _load_rl_agent(self) -> None:
        if RL_AGENT_PATH.exists():
            try:
                from logic.sort_rl import load_agent
                self._rl_agent = load_agent(RL_AGENT_PATH)
                if self._rl_agent:
                    logger.info("RL agent loaded")
            except Exception as e:
                logger.warning(f"Failed to load RL agent: {e}")

    def _on_sort_state_change(self, state: SortState) -> None:
        logger.info(f"Sort state: {state.value}")
        self.state_manager.update_sort_state(state.value)

    def _on_block_move(self, move) -> None:
        logger.debug(f"Block {move.block_id}: {move.from_pos} -> {move.to_pos}")

    def _on_tetris_action(self, action) -> None:
        logger.debug(f"Tetris action: {action.name}")

    def _on_puppeteer_frame(self, frame) -> None:
        logger.debug(f"Arm angles: {[f'{a:.1f}' for a in frame.angles]}")

    async def run(self) -> None:
        self._running = True
        logger.info("Starting main loop")

        self.cameras.start_all()

        # Start recording if enabled
        if self.config.recording.enabled:
            self.recorder.start()

        # Build async tasks
        tasks = [
            asyncio.create_task(self._ws_server.start()),
            asyncio.create_task(self._mode_loop()),
            asyncio.create_task(self.audience_server.start()),
            asyncio.create_task(self.narration.start()),
        ]

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass

    async def _mode_loop(self) -> None:
        """Main dispatch loop — runs the current mode, supports hot-swap."""
        while self._running:
            try:
                if self.mode == Mode.CHIMP_SORT:
                    await self._run_chimp_sort()
                elif self.mode == Mode.TETRIS:
                    await self._run_tetris()
                elif self.mode == Mode.CALIBRATE:
                    await self._run_calibration()
                elif self.mode == Mode.PUPPETEER:
                    await self._run_puppeteer()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Mode loop error: {e}")
                await asyncio.sleep(0.5)

    async def _run_chimp_sort(self) -> None:
        self.sort_fsm.start_human_benchmark()
        current_mode = self.mode

        while self._running and self.mode == current_mode:
            frame = self.cameras.get_frame(CameraRole.OVERHEAD)
            if frame is None:
                await asyncio.sleep(0.01)
                continue

            blocks = self.detector.detect_blocks(frame)

            # Update tracker (F2)
            tracked = self.tracker.update(blocks)
            for t in tracked:
                for b in blocks:
                    if b.block_id == t.block_id:
                        b.track_id = t.track_id

            self.sort_fsm.update(blocks)

            # Record
            if self.recorder.is_recording:
                self.recorder.record_blocks([b.as_dict() for b in blocks])
                self.recorder.record_motor(self.arm.position.as_tuple(), self.gripper.get_position())

            # Update state
            self.state_manager.update_blocks([b.as_dict() for b in blocks])
            self.state_manager.update_arm(self.arm.position.as_tuple(), self.arm.state.value)

            if self.sort_fsm.state == SortState.COMPLETE:
                logger.info(f"Sorting complete! Duration: {self.sort_fsm.session.duration:.2f}s")
                break

            if self.sort_fsm.state == SortState.CYBORG_COOP:
                # Check audience votes
                audience_vote = self.audience_server.get_winning_block_id()
                if audience_vote:
                    self.audience_server.clear_votes()

                target = self.sort_fsm.get_next_robot_target(
                    rl_agent=self._rl_agent,
                    audience_vote=audience_vote
                )
                if target:
                    block_id, (tx, ty) = target
                    angles = self.calibration.pixel_to_arm(tx, ty)
                    self.arm.move_to(angles)
                    self.gripper.close()
                    await asyncio.sleep(0.3)
                    self.gripper.open()

            await asyncio.sleep(0.016)

    async def _run_tetris(self) -> None:
        self.tetris.reset()
        current_mode = self.mode

        while self._running and self.mode == current_mode:
            if self.tetris.state and self.tetris.state.game_over:
                break

            frame = self.cameras.get_frame(CameraRole.OVERHEAD)
            if frame is not None and not self.inference.is_frozen:
                _, _, activations = self.inference.predict(frame)
                if self.recorder.is_recording:
                    self.recorder.record_neural(self.inference.get_all_layer_stats())

            action = self.tetris.step()

            if self.tetris.state:
                self.state_manager.update_tetris_score(self.tetris.state.score)

            await asyncio.sleep(0.1)

        logger.info(f"Game over! Score: {self.tetris.state.score if self.tetris.state else 0}")

    async def _run_calibration(self) -> None:
        logger.info("Calibration mode - press 'q' to quit")
        import cv2
        current_mode = self.mode

        while self._running and self.mode == current_mode:
            frame = self.cameras.get_frame(CameraRole.OVERHEAD)
            if frame is None:
                await asyncio.sleep(0.01)
                continue

            blocks = self.detector.detect_blocks(frame)
            display = self.detector.draw_detections(frame, blocks)

            cv2.imshow("Calibration", display)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                break
            elif key == ord('c') and blocks:
                block = blocks[0]
                angles = self.arm.position.as_tuple()
                self.calibration.add_calibration_point(block.center_x, block.center_y, angles)
                logger.info(f"Added calibration point: ({block.center_x}, {block.center_y})")
            elif key == ord('s'):
                self.calibration.save()
                logger.info("Calibration saved")

        cv2.destroyAllWindows()

    async def _run_puppeteer(self) -> None:
        logger.info("Puppeteer mode - 'l' for live, 'r' to record, 'p' to playback, 'k' for kinesthetic, 'q' to quit")
        current_mode = self.mode

        while self._running and self.mode == current_mode:
            key_pressed = None

            try:
                import msvcrt
                if msvcrt.kbhit():
                    key_pressed = msvcrt.getch().decode().lower()
            except ImportError:
                import sys, select
                if select.select([sys.stdin], [], [], 0)[0]:
                    key_pressed = sys.stdin.read(1).lower()

            if key_pressed == 'q':
                break
            elif key_pressed == 'l':
                if self.puppeteer.state == PuppeteerState.IDLE:
                    self.puppeteer.start_live()
                    self.state_manager.update_puppeteer_state("live")
                    logger.info("LIVE mode - Your arm controls the robot!")
                else:
                    self.puppeteer.stop()
                    self.state_manager.update_puppeteer_state("idle")
                    logger.info("Stopped")
            elif key_pressed == 'r':
                if self.puppeteer.state == PuppeteerState.IDLE:
                    self.puppeteer.start_recording()
                    self.state_manager.update_puppeteer_state("recording")
                    logger.info("RECORDING - Move your arm...")
                elif self.puppeteer.state == PuppeteerState.RECORDING:
                    recording = self.puppeteer.stop_recording()
                    self.state_manager.update_puppeteer_state("idle")
                    logger.info(f"Recorded {recording.frame_count} frames ({recording.duration:.1f}s)")
            elif key_pressed == 'p':
                if self.puppeteer.recording:
                    self.puppeteer.start_playback()
                    self.state_manager.update_puppeteer_state("playback")
                    logger.info("PLAYBACK - Replaying recording...")
            elif key_pressed == 'k':
                if not self.kinesthetic.is_recording:
                    self.kinesthetic.start("kinesthetic_" + str(int(__import__('time').time())))
                    logger.info("KINESTHETIC TEACHING - Move the arm by hand...")
                else:
                    motion = self.kinesthetic.stop()
                    if motion:
                        logger.info(f"Kinesthetic recording: {len(motion.frames)} frames")

            if self.puppeteer.state != PuppeteerState.IDLE:
                frame = self.puppeteer.update()
                if frame:
                    await self._broadcast_puppeteer_activations(frame)
                    self.state_manager.update_arm(
                        tuple(frame.angles),
                        "moving"
                    )

            if self.kinesthetic.is_recording:
                self.kinesthetic.update()

            await asyncio.sleep(0.033)

        self.puppeteer.stop()

    async def _broadcast_puppeteer_activations(self, frame) -> None:
        if not self._ws_server.clients:
            return

        data = self.puppeteer.get_websocket_payload(frame)
        dead_clients = set()
        for client in self._ws_server.clients.copy():
            try:
                await client.send(data)
            except Exception:
                dead_clients.add(client)
        for client in dead_clients:
            self._ws_server.clients.discard(client)

    async def shutdown(self) -> None:
        logger.info("Shutting down")
        self._running = False

        # Stop recording
        if self.recorder.is_recording:
            self.recorder.stop()

        await self.narration.stop()
        await self._ws_server.stop()
        await self.audience_server.stop()

        if self.cameras:
            self.cameras.close_all()

        if self.gripper:
            self.gripper.open()

        if self.magnet:
            self.magnet.off()

        if self.arm:
            self.arm.home()
            self.arm.disconnect()


async def main():
    parser = argparse.ArgumentParser(description="A.L.I.C.E. - Adaptive Learning Interface for Cognitive Exploration")
    parser.add_argument("--config", type=str, default=None, help="Path to alice.yaml config file")
    parser.add_argument("--mode", type=str, choices=["chimp", "tetris", "calibrate", "puppeteer"], default=None)
    parser.add_argument("--simulate", action="store_true", default=None)
    parser.add_argument("--ws-port", type=int, default=None)
    parser.add_argument("--arm-port", type=str, default=None, help="Serial port for arm controller")
    parser.add_argument("--magnet-port", type=str, default=None, help="Serial port for magnet driver")
    parser.add_argument("--imu-port", type=str, default=None, help="Serial port for IMU sensor")
    parser.add_argument("--record", action="store_true", default=False, help="Enable session recording")
    parser.add_argument("--replay", type=str, default=None, help="Replay a recorded session")
    args = parser.parse_args()

    # Build CLI overrides
    cli_overrides = {}
    if args.mode:
        cli_overrides["mode"] = args.mode
    if args.simulate is not None:
        cli_overrides["simulate"] = args.simulate
    if args.ws_port:
        cli_overrides.setdefault("websocket", {})["tensor_port"] = args.ws_port
    if args.arm_port:
        cli_overrides.setdefault("hardware", {}).setdefault("arm", {})["port"] = args.arm_port
    if args.magnet_port:
        cli_overrides.setdefault("hardware", {}).setdefault("magnet", {})["port"] = args.magnet_port
    if args.imu_port:
        cli_overrides.setdefault("hardware", {}).setdefault("imu", {})["port"] = args.imu_port
    if args.record:
        cli_overrides.setdefault("recording", {})["enabled"] = True

    config_path = Path(args.config) if args.config else None
    config = load_config(config_path, cli_overrides)

    # Self-test
    if config.selftest.enabled:
        tester = SelfTest(simulate=config.simulate)
        ws_ports = [config.websocket.tensor_port, config.websocket.puppet_port,
                    config.websocket.audience_port]
        tester.run_all(ws_ports=ws_ports)

    # Replay mode
    if args.replay:
        replay_path = Path(args.replay)
        if not replay_path.exists():
            logger.error(f"Replay file not found: {replay_path}")
            return
        logger.info(f"Replaying session: {replay_path}")
        player = SessionPlayer(replay_path)
        async for frame in player.play():
            logger.info(f"[{frame.frame_type}] {frame.timestamp:.3f}")
        return

    alice = ALICE(config)

    if not await alice.initialize():
        return

    try:
        await alice.run()
    except KeyboardInterrupt:
        pass
    finally:
        await alice.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
