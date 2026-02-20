import asyncio
import argparse
import logging
import threading
from enum import Enum
from pathlib import Path
from typing import Optional

from config import load_config, AliceConfig
from selftest import SelfTest
from state import AliceStateManager
from recording import SessionRecorder, SessionPlayer
from hardware import (ArmController, MagnetDriver, CalibrationManager,
                      create_gripper, KinestheticTeacher)
from vision import (CameraManager, CameraConfig, CameraRole,
                    ArucoDetector, BlockTracker)
from brain import InferencePipeline
from logic import ChimpSortFSM, SortState, TetrisAgent, TetrisController
from logic.arm_routines import auto_scramble, auto_solve, PickPlaceConfig
from server import TensorStreamServer
from puppet_server import PuppetServer
from audience_server import AudienceServer
from narration import NarrationService


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("ALICE")

WEIGHTS_PATH = Path(__file__).parent / "brain" / "weights" / "block_recognizer.pth"
STATE_WEIGHTS_PATH = Path(__file__).parent / "brain" / "weights" / "block_state.pth"
RL_AGENT_PATH = Path(__file__).parent / "brain" / "weights" / "sort_agent.zip"


class Mode(Enum):
    IDLE = "idle"
    AUTO_SORT = "auto_sort"
    AUTO_TETRIS = "auto_tetris"
    DEMO = "demo"
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

        # Puppet server — hardware injected later in initialize()
        self.puppet_server = PuppetServer(
            host=config.websocket.puppet_host if hasattr(config.websocket, 'puppet_host') else "localhost",
            port=config.websocket.puppet_port,
            simulate=config.simulate,
        )
        self.puppet_server.set_state_manager(self.state_manager)

        # Audience
        self.audience_server = AudienceServer(
            port=config.websocket.audience_port,
            state_manager=self.state_manager,
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

        # Sort demo progression — survives mode switches (for puppeteer interlude)
        self._sort_act = 0          # 0=fresh, 3=acts 1-2 done, waiting for puppeteer return
        self._human_session = None  # preserved for ghost replay

    async def initialize(self) -> bool:
        logger.info(f"Initializing A.L.I.C.E. in {self.mode.value} mode (simulate={self.simulate})")

        try:
            hw = self.config.hardware
            serial_lock = threading.Lock()
            arm_kwargs = {"simulate": self.simulate, "serial_lock": serial_lock}
            magnet_kwargs = {"simulate": self.simulate, "serial_lock": serial_lock}
            if hw.arm_port:
                arm_kwargs["port"] = hw.arm_port
            if hw.magnet_port:
                magnet_kwargs["port"] = hw.magnet_port

            self.arm = ArmController(**arm_kwargs)
            self.magnet = MagnetDriver(**magnet_kwargs)
            self.gripper = create_gripper("magnet", self.magnet)
            self.calibration = CalibrationManager()

            if not self.arm.connect():
                logger.warning("Arm connection failed, falling back to simulation")
                self.simulate = True
                self.arm = ArmController(simulate=True, serial_lock=serial_lock)
                self.arm.connect()
                self.magnet = MagnetDriver(simulate=True, serial_lock=serial_lock)
                self.gripper = create_gripper("magnet", self.magnet)

            # Created after fallback so it always references the live arm
            self.kinesthetic = KinestheticTeacher(self.arm)

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
            self._ws_server.set_recorder(self.recorder)

            # Inject shared hardware into PuppetServer so it drives the same arm
            self.puppet_server.arm = self.arm
            self.puppet_server.magnet = self.magnet
            self.puppet_server.gripper = self.gripper
            self.puppet_server._owns_hardware = False

            # Wire tensor server for activation forwarding to dashboard
            self.puppet_server.set_tensor_server(self._ws_server)

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
        if mode in (Mode.AUTO_SORT, Mode.DEMO):
            self.sort_fsm = ChimpSortFSM()
            self.sort_fsm.on_state_change(self._on_sort_state_change)
            self.sort_fsm.on_move(self._on_block_move)

        elif mode == Mode.AUTO_TETRIS:
            self.tetris = TetrisAgent()
            self.tetris.on_action(self._on_tetris_action)
            self._tetris_controller = self._create_tetris_controller()

    def _teardown_mode(self) -> None:
        """Clean up current mode's subsystems."""
        if self.mode == Mode.PUPPETEER:
            self.puppet_server.stop_puppet()
        if hasattr(self, '_tetris_controller') and self._tetris_controller:
            self._tetris_controller.stop()
            self._tetris_controller = None
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

    async def run(self) -> None:
        self._running = True
        logger.info("Starting main loop")

        self.cameras.start_all()

        # Start recording if enabled
        if self.config.recording.enabled:
            self.recorder.start()

        # Build async tasks — store references for cancellation
        self._tasks = [
            asyncio.create_task(self._ws_server.start(), name="tensor_server"),
            asyncio.create_task(self.puppet_server.start(), name="puppet_server"),
            asyncio.create_task(self._mode_loop(), name="mode_loop"),
            asyncio.create_task(self.audience_server.start(), name="audience_server"),
            asyncio.create_task(self.narration.start(), name="narration"),
        ]

        try:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass

    async def _mode_loop(self) -> None:
        """Main dispatch loop — runs the current mode, supports hot-swap."""
        while self._running:
            try:
                if self.mode == Mode.IDLE:
                    await self._run_idle()
                elif self.mode == Mode.AUTO_SORT:
                    await self._run_auto_sort()
                elif self.mode == Mode.AUTO_TETRIS:
                    await self._run_auto_tetris()
                elif self.mode == Mode.DEMO:
                    await self._run_demo()
                elif self.mode == Mode.CALIBRATE:
                    await self._run_calibration()
                elif self.mode == Mode.PUPPETEER:
                    await self._run_puppeteer()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Mode loop error: {e}")
                await asyncio.sleep(0.5)

    async def _run_idle(self) -> None:
        """Idle mode — just keep state broadcasting, wait for mode switch."""
        current_mode = self.mode
        while self._running and self.mode == current_mode:
            # Still stream camera + activations so the dashboard has something to show
            frame = self.cameras.get_frame(CameraRole.OVERHEAD)
            if frame is not None and not self.inference.is_frozen:
                self.inference.predict(frame)
            await asyncio.sleep(self.config.timing.idle_loop_s)

    # ── Auto Sort (passive attractor) ────────────────────────────────

    async def _run_auto_sort(self) -> None:
        """Autonomous scramble -> solve -> pause -> repeat loop."""
        current_mode = self.mode
        cycle = 0

        while self._running and self.mode == current_mode:
            cycle += 1
            logger.info(f"Auto-sort cycle {cycle}: scrambling...")
            self.state_manager.update_auto_sort("scrambling", cycle)
            self.sort_fsm.start_rebellion()  # Use rebellion state for autonomous solving
            self.state_manager.update_sort_state("scrambling")

            camera_getter = lambda: self.cameras.get_frame(CameraRole.OVERHEAD)
            running = lambda: self._running and self.mode == current_mode

            await auto_scramble(
                self.arm, self.gripper, self.calibration,
                self.detector, camera_getter,
                running_check=running,
            )
            if not self._running or self.mode != current_mode:
                break

            logger.info(f"Auto-sort cycle {cycle}: solving...")
            self.state_manager.update_auto_sort("solving", cycle)
            self.state_manager.update_sort_state("rebellion")

            await auto_solve(
                self.arm, self.gripper, self.calibration,
                self.detector, camera_getter, self.sort_fsm,
                running_check=running,
            )
            if not self._running or self.mode != current_mode:
                break

            logger.info(f"Auto-sort cycle {cycle} complete")
            self.state_manager.update_auto_sort("complete", cycle)

            # Pause before next cycle
            for _ in range(30):  # ~3 seconds
                if not self._running or self.mode != current_mode:
                    return
                await asyncio.sleep(0.1)

    # ── Auto Tetris (passive attractor) ───────────────────────────────

    def _create_tetris_controller(self) -> 'TetrisController':
        """Create a TetrisController from config."""
        from vision.screen_reader import ScreenReader, ScreenRegion
        from hardware.keyboard_player import KeyboardPlayer
        ts = self.config.tetris_screen
        region = ScreenRegion(
            left=ts.board_left, top=ts.board_top,
            width=ts.board_width, height=ts.board_height,
        )
        reader = ScreenReader(region)
        player = KeyboardPlayer(self.arm, Path(ts.key_calibration_path))
        return TetrisController(reader, player, self.tetris)

    async def _run_auto_tetris(self) -> None:
        """Arm plays tetr.io on a physical keyboard via screen capture."""
        current_mode = self.mode
        logger.info("Auto-Tetris: arm plays tetr.io on physical keyboard")

        if not hasattr(self, '_tetris_controller') or self._tetris_controller is None:
            self._tetris_controller = self._create_tetris_controller()

        running = lambda: self._running and self.mode == current_mode
        await self._tetris_controller.run_loop(running_check=running)

        logger.info(f"Auto-Tetris ended: {self._tetris_controller.cycles} cycles, "
                     f"{self._tetris_controller.total_keys_pressed} keys")

    # ── Demo (5-act show) ─────────────────────────────────────────────

    async def _run_demo(self) -> None:
        """Full 5-act demo: human -> ghost -> puppet -> cyborg -> rebellion.

        Auto-scramble is inserted before Acts 1, 4, and 5 so the operator
        doesn't have to manually reset blocks.
        """
        current_mode = self.mode
        camera_getter = lambda: self.cameras.get_frame(CameraRole.OVERHEAD)
        running = lambda: self._running and self.mode == current_mode

        # ── Resuming after puppeteer interlude? Skip to Act 4 ──
        if self._sort_act >= 3:
            self._sort_act = 4
            await self._run_demo_act4_and_5(current_mode)
            return

        # ── Auto-scramble before Act 1 ──
        logger.info("Demo: scrambling blocks before Act 1")
        self.state_manager.update_demo_act(0, "Scrambling")
        self.state_manager.update_sort_state("scrambling")
        await auto_scramble(self.arm, self.gripper, self.calibration,
                            self.detector, camera_getter, running_check=running)
        if not running():
            return

        # ── Act 1: Human Benchmark ──
        logger.info("Act 1: Human Benchmark — sort the blocks!")
        self.state_manager.update_demo_act(1, "Human Benchmark")
        self.sort_fsm.start_human_benchmark()
        self._human_session = await self._sort_loop(current_mode)
        if not running():
            return

        # ── Act 2: Ghost Replay ──
        if self._human_session and self._human_session.moves:
            logger.info(f"Act 2: Ghost Replay — replaying {len(self._human_session.moves)} moves")
            self.state_manager.update_demo_act(2, "Ghost Replay")
            self.sort_fsm.start_ghost_replay(self._human_session)
            self.state_manager.update_sort_state("ghost_replay")
            for move in self._human_session.moves:
                if not running():
                    return
                angles = self.calibration.pixel_to_arm(move.to_pos[0], move.to_pos[1])
                self.arm.move_to(angles)
                self.gripper.close()
                await asyncio.sleep(0.3)
                self.gripper.open()
                await asyncio.sleep(0.2)
            logger.info("Ghost replay complete")

        # ── Interlude: Await Puppeteer (Act 3) ──
        self._sort_act = 3
        logger.info("Acts 1-2 complete. Switch to PUPPETEER mode for Act 3, then back to DEMO for Acts 4-5.")
        self.state_manager.update_demo_act(3, "Puppeteer")
        self.state_manager.update_sort_state("awaiting_puppeteer")

        # Hold here until operator switches away
        while self._running and self.mode == current_mode:
            await asyncio.sleep(0.25)

    async def _run_demo_act4_and_5(self, current_mode: Mode) -> None:
        """Acts 4 and 5 of the demo, entered after puppeteer interlude."""
        camera_getter = lambda: self.cameras.get_frame(CameraRole.OVERHEAD)
        running = lambda: self._running and self.mode == current_mode

        # ── Auto-scramble before Act 4 ──
        logger.info("Demo: scrambling blocks before Act 4")
        self.state_manager.update_demo_act(4, "Scrambling")
        self.state_manager.update_sort_state("scrambling")
        await auto_scramble(self.arm, self.gripper, self.calibration,
                            self.detector, camera_getter, running_check=running)
        if not running():
            return

        # ── Act 4: Cyborg Cooperation ──
        logger.info("Act 4: Cyborg Cooperation — human + robot + audience!")
        self.state_manager.update_demo_act(4, "Cyborg Coop")
        self.sort_fsm.start_cyborg_coop()
        await self._sort_loop(current_mode)
        if not running():
            return

        # ── Auto-scramble before Act 5 ──
        logger.info("Demo: scrambling blocks before Act 5")
        self.state_manager.update_demo_act(5, "Scrambling")
        self.state_manager.update_sort_state("scrambling")
        await auto_scramble(self.arm, self.gripper, self.calibration,
                            self.detector, camera_getter, running_check=running)
        if not running():
            return

        # ── Act 5: Rebellion ──
        logger.info("Act 5: Rebellion — ALICE sorts optimally, audience overridden")
        self.state_manager.update_demo_act(5, "Rebellion")
        self.sort_fsm.start_rebellion()
        self.state_manager.update_sort_state("rebellion")
        await self._rebellion_loop(current_mode)

        # Done — reset for next demo
        self._sort_act = 0
        self._human_session = None
        self.state_manager.update_demo_act(0, "")

    async def _sort_loop(self, current_mode) -> Optional['SortingSession']:
        """Shared detection/tracking/state loop for human benchmark and cyborg phases."""
        while self._running and self.mode == current_mode:
            frame = self.cameras.get_frame(CameraRole.OVERHEAD)
            if frame is None:
                await asyncio.sleep(self.config.timing.camera_poll_s)
                continue

            blocks = self.detector.detect_blocks(frame)

            # Update tracker
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
            if self.sort_fsm.session:
                self.state_manager.update_sort_progress(
                    move_count=self.sort_fsm.session.move_count,
                    start_time=self.sort_fsm.session.start_time,
                )

            if self.sort_fsm.state == SortState.COMPLETE:
                logger.info(f"Sorting complete! Duration: {self.sort_fsm.session.duration:.2f}s")
                return self.sort_fsm.session

            if self.sort_fsm.state == SortState.CYBORG_COOP:
                # Consume audience block votes
                audience_vote = None
                winner_info = self.audience_server.consume_votes()
                if winner_info:
                    audience_vote = winner_info["block_id"]
                    await self.audience_server.broadcast_winner(winner_info)

                target = self.sort_fsm.get_next_robot_target(
                    rl_agent=self._rl_agent,
                    audience_vote=audience_vote
                )
                if target:
                    block_id, (tx, ty) = target
                    await self.audience_server.broadcast_action("pick", {
                        "block_id": block_id, "target_x": tx, "target_y": ty,
                    })
                    angles = self.calibration.pixel_to_arm(tx, ty)
                    self.arm.move_to(angles)
                    try:
                        self.gripper.close()
                    except Exception as e:
                        logger.error(f"Gripper close failed: {e}")
                    await asyncio.sleep(0.3)
                    try:
                        self.gripper.open()
                    except Exception as e:
                        logger.error(f"Gripper open failed: {e}")

            await asyncio.sleep(self.config.timing.sort_loop_s)
        return self.sort_fsm.session

    async def _rebellion_loop(self, current_mode) -> None:
        """Act 5: Robot sorts optimally, deliberately ignoring audience votes."""
        while self._running and self.mode == current_mode:
            frame = self.cameras.get_frame(CameraRole.OVERHEAD)
            if frame is None:
                await asyncio.sleep(self.config.timing.camera_poll_s)
                continue

            blocks = self.detector.detect_blocks(frame)
            tracked = self.tracker.update(blocks)
            for t in tracked:
                for b in blocks:
                    if b.block_id == t.block_id:
                        b.track_id = t.track_id

            self.sort_fsm.update(blocks)

            # Update state
            self.state_manager.update_blocks([b.as_dict() for b in blocks])
            self.state_manager.update_arm(self.arm.position.as_tuple(), self.arm.state.value)
            if self.sort_fsm.session:
                self.state_manager.update_sort_progress(
                    move_count=self.sort_fsm.session.move_count,
                    start_time=self.sort_fsm.session.start_time,
                )

            if self.sort_fsm.state == SortState.COMPLETE:
                logger.info(f"Rebellion complete! {self.sort_fsm.session.duration:.2f}s")
                return

            # Consume audience votes — we hear them, we just don't obey
            crowd_winner = self.audience_server.consume_votes()
            crowd_choice = crowd_winner["block_id"] if crowd_winner else None
            crowd_votes = crowd_winner["voter_count"] if crowd_winner else 0

            # Robot computes its own optimal move
            optimal = self.sort_fsm.get_optimal_next_target()
            if optimal:
                robot_choice, (tx, ty) = optimal

                # Update state for narration
                self.state_manager.update_rebellion(crowd_choice, robot_choice)

                # Tell the audience: you said X, I chose Y
                if crowd_choice is not None and crowd_choice != robot_choice:
                    await self.audience_server.broadcast_override(
                        crowd_choice=crowd_choice,
                        robot_choice=robot_choice,
                        crowd_votes=crowd_votes,
                        reason="optimal",
                    )
                elif crowd_choice is not None:
                    # Crowd agreed with robot — acknowledge it
                    await self.audience_server.broadcast_override(
                        crowd_choice=crowd_choice,
                        robot_choice=robot_choice,
                        crowd_votes=crowd_votes,
                        reason="agreed",
                    )

                await self.audience_server.broadcast_action("pick", {
                    "block_id": robot_choice, "target_x": tx, "target_y": ty,
                })
                angles = self.calibration.pixel_to_arm(tx, ty)
                self.arm.move_to(angles)
                try:
                    self.gripper.close()
                except Exception as e:
                    logger.error(f"Gripper close failed: {e}")
                await asyncio.sleep(0.3)
                try:
                    self.gripper.open()
                except Exception as e:
                    logger.error(f"Gripper open failed: {e}")

            await asyncio.sleep(self.config.timing.sort_loop_s)

    async def _run_calibration(self) -> None:
        logger.info("Calibration mode - press 'q' to quit")
        import cv2
        current_mode = self.mode

        try:
            while self._running and self.mode == current_mode:
                frame = self.cameras.get_frame(CameraRole.OVERHEAD)
                if frame is None:
                    await asyncio.sleep(self.config.timing.camera_poll_s)
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
        finally:
            cv2.destroyAllWindows()

    async def _run_puppeteer(self) -> None:
        """Puppeteer mode — hand tracking via Haptix.

        PuppetServer owns all control, recording, playback, and broadcasting.
        This loop just enters live mode and waits for a mode switch.
        """
        logger.info("Puppeteer mode — hand tracking via Haptix")
        self.puppet_server.go_live()
        current_mode = self.mode
        while self._running and self.mode == current_mode:
            await asyncio.sleep(self.config.timing.idle_loop_s)
        self.puppet_server.stop_puppet()

    async def shutdown(self) -> None:
        SHUTDOWN_TIMEOUT = 5.0  # seconds to wait before force-cancelling tasks
        logger.info("Shutting down")
        self._running = False

        # Stop recording
        if self.recorder.is_recording:
            self.recorder.stop()

        # Stop services (each has its own internal _streaming flag)
        await self.narration.stop()
        await self._ws_server.stop()
        await self.puppet_server.stop()
        await self.audience_server.stop()

        # Cancel all async tasks with a timeout
        if hasattr(self, '_tasks'):
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            # Wait for tasks to finish cancellation, with a hard timeout
            done, pending = await asyncio.wait(
                self._tasks, timeout=SHUTDOWN_TIMEOUT
            )
            for task in pending:
                logger.warning(f"Force-cancelling stuck task: {task.get_name()}")
                task.cancel()

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
    parser.add_argument("--mode", type=str, choices=["idle", "auto_sort", "auto_tetris", "demo", "calibrate", "puppeteer"], default=None)
    parser.add_argument("--simulate", action="store_true", default=None)
    parser.add_argument("--ws-port", type=int, default=None)
    parser.add_argument("--arm-port", type=str, default=None, help="Serial port for arm controller")
    parser.add_argument("--magnet-port", type=str, default=None, help="Serial port for magnet driver")
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
