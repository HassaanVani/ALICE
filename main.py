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
from hardware import (ArmController, MagnetDriver, SuctionDriver, CalibrationManager,
                      create_gripper, KinestheticTeacher)
from vision import CameraManager, CameraConfig, CameraRole, ArucoDetector, BlockTracker
from brain import InferencePipeline
from logic import ChimpSortFSM, SortState, TetrisAgent, PersonalityEngine, ActionOrigin
from hardware.dynamics import MovementDynamics
from server import TensorStreamServer
from modes import (ModeContext, DemoState, IdleRunner, AutoSortRunner,
                   AutoTetrisRunner, DemoRunner, CalibrateRunner, PuppeteerRunner,
                   PerformanceRunner)
from puppet_server import PuppetServer
from audience_server import AudienceServer
from narration import NarrationService
from voice_input import VoiceInputService


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
    PERFORMANCE = "performance"


class ALICE:
    def __init__(self, config: AliceConfig):
        self.config = config
        self.mode = Mode(config.mode)
        self.simulate = config.simulate

        self.arm: Optional[ArmController] = None
        self.magnet: Optional[MagnetDriver] = None
        self.suction: Optional[SuctionDriver] = None
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

        # Personality engine
        self.personality = PersonalityEngine()
        self.dynamics: Optional[MovementDynamics] = None

        # LLM movement interpreter
        self.llm_interpreter = None

        # Living behaviors (initialized in initialize() if enabled)
        self.object_memory = None
        self.gaze_tracker = None
        self.curiosity_engine = None
        self.habit_engine = None
        self.body_language = None
        self.sound_effects_engine = None
        self.proactive = None
        self.presence_detector = None

        # Connect personality to narration voice gate
        self.narration.set_personality(self.personality)

        # Voice input
        self.voice_input = VoiceInputService(config.voice_input)

        # RL agent
        self._rl_agent = None

        # Demo state — survives mode switches (for puppeteer interlude)
        self._demo_state = DemoState()

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

            gripper_type = hw.gripper_type if hasattr(hw, 'gripper_type') else "suction"
            suction_pin = hw.suction_pin if hasattr(hw, 'suction_pin') else 5

            self.arm = ArmController(**arm_kwargs)
            self.magnet = MagnetDriver(**magnet_kwargs)
            self.suction = SuctionDriver(pin=suction_pin, simulate=self.simulate,
                                         serial_lock=serial_lock)
            self.calibration = CalibrationManager()

            if not self.arm.connect():
                logger.warning("Arm connection failed, falling back to simulation")
                self.simulate = True
                self.arm = ArmController(simulate=True, serial_lock=serial_lock)
                self.arm.connect()
                self.magnet = MagnetDriver(simulate=True, serial_lock=serial_lock)
                self.suction = SuctionDriver(pin=suction_pin, simulate=True,
                                             serial_lock=serial_lock)

            # Share the cobot instance from ArmController with suction driver
            if self.arm.cobot is not None:
                self.suction.use_shared_cobot(self.arm.cobot, serial_lock)

            self.gripper = create_gripper(gripper_type, magnet_driver=self.magnet,
                                          suction_driver=self.suction)

            # Created after fallback so it always references the live arm
            self.kinesthetic = KinestheticTeacher(self.arm)

            # Movement dynamics — wraps arm with personality-driven speed/hesitation
            self.dynamics = MovementDynamics(self.arm, self.personality)

            self.calibration.load()

            # Cameras from config
            self.cameras = CameraManager()
            oc = self.config.arm_camera
            fc = self.config.front_camera
            arm_cam = CameraConfig(device_id=oc.device_id, width=oc.width,
                                   height=oc.height, fps=oc.fps, role=CameraRole.ARM_MOUNTED)
            front = CameraConfig(device_id=fc.device_id, width=fc.width,
                                 height=fc.height, fps=fc.fps, role=CameraRole.FRONT_FACING)

            self.cameras.add_camera(arm_cam)
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

            # Apply personality config
            pc = self.config.personality
            self.personality.SPEECH_THRESHOLD = pc.speech_threshold
            self.personality.SPEECH_COOLDOWN = pc.speech_cooldown
            self.personality.OVERRIDE_COMMENT_THRESHOLD = pc.override_comment_threshold
            self.personality.IDLE_MICRO_MOTION_DELAY = pc.idle_micro_motion_delay
            self.personality.IDLE_TETRIS_DELAY = pc.idle_tetris_delay
            self.personality.IDLE_TETRIS_DELAY_NO_PRESENCE = pc.idle_tetris_delay_alone
            self.personality.SPEED_MULTIPLIERS = {
                ActionOrigin.SELF_INITIATED: pc.speed_self_initiated,
                ActionOrigin.USER_REQUESTED: pc.speed_user_requested,
                ActionOrigin.CROWD_REQUESTED: pc.speed_crowd_requested,
                ActionOrigin.OVERRIDE: pc.speed_override,
            }
            self.dynamics.MICRO_AMPLITUDE = pc.micro_amplitude_deg
            self.dynamics.MICRO_PERIOD = pc.micro_period_s

            # Wire up servers
            self._ws_server.set_pipeline(self.inference)
            self._ws_server.set_state_manager(self.state_manager)
            self._ws_server.set_switch_mode_callback(self._handle_mode_switch)
            self._ws_server.set_camera_frame_getter(
                lambda: self.cameras.get_frame(CameraRole.OVERHEAD)
            )
            self._ws_server.set_recorder(self.recorder)

            # Object interaction — fetch, hand_over, nudge via dashboard commands
            from logic.object_interaction import ObjectInteraction
            yolo = self.inference.yolo if hasattr(self.inference, 'yolo') else None
            self._interaction = ObjectInteraction(
                arm=self.arm, gripper=self.gripper,
                calibration=self.calibration, dynamics=self.dynamics,
                personality=self.personality, yolo_detector=yolo,
                narration=self.narration,
            )
            self._ws_server.set_interaction_callback(self._handle_interaction)

            # Voice input — wire to interaction system
            self.voice_input.set_interaction(self._interaction)
            self.voice_input.set_personality(self.personality)
            self.voice_input.set_narration(self.narration)
            self.voice_input.set_state_manager(self.state_manager)
            self.voice_input.set_camera_getter(
                lambda: self.cameras.get_frame(CameraRole.OVERHEAD)
            )
            if yolo:
                self.voice_input.set_yolo(yolo)

            # Inject shared hardware into PuppetServer so it drives the same arm
            self.puppet_server.arm = self.arm
            self.puppet_server.magnet = self.magnet
            self.puppet_server.gripper = self.gripper
            self.puppet_server._owns_hardware = False

            # Wire tensor server for activation forwarding to dashboard
            self.puppet_server.set_tensor_server(self._ws_server)

            # --- Living behaviors ---
            if self.config.living_behaviors.enabled:
                from logic.gaze_tracker import GazeTracker
                from logic.curiosity import CuriosityEngine
                from logic.habits import HabitEngine
                from logic.body_language import BodyLanguage
                from logic.proactive import ProactiveEngagement
                from audio.sound_effects import SoundEffects
                from logic.object_memory import ObjectMemory
                from vision.presence import PresenceDetector

                lb = self.config.living_behaviors

                self.object_memory = ObjectMemory()
                self.object_memory.load()

                self.presence_detector = PresenceDetector()
                self.presence_detector.start()

                self.gaze_tracker = GazeTracker(
                    alpha=lb.gaze_smoothing,
                    face_priority=lb.gaze_face_priority,
                )
                self.curiosity_engine = CuriosityEngine()
                self.curiosity_engine.DECAY_RATE = lb.curiosity_decay_rate
                self.curiosity_engine.MIN_THRESHOLD = lb.curiosity_examine_threshold
                self.curiosity_engine.load(Path("data/curiosity_state.json"))

                self.habit_engine = HabitEngine()
                self.habit_engine.MIN_OBSERVATIONS = lb.habit_min_observations
                self.habit_engine.load(Path("data/habits.json"))

                self.body_language = BodyLanguage()
                self.body_language.set_enabled(lb.body_language_enabled)

                self.sound_effects_engine = SoundEffects(
                    arm=self.arm,
                    enabled=self.config.sound_effects.enabled,
                    intensity=self.config.sound_effects.intensity,
                )

                self.proactive = ProactiveEngagement(
                    curiosity=self.curiosity_engine,
                    habits=self.habit_engine,
                    gaze=self.gaze_tracker,
                    body_language=self.body_language,
                    sound_effects=self.sound_effects_engine,
                    personality=self.personality,
                    object_memory=self.object_memory,
                )
                self.proactive.MIN_ACTION_INTERVAL = lb.proactive_min_interval_s

                # Wire into dynamics
                self.dynamics.set_body_language(self.body_language)
                self.dynamics.set_gaze_tracker(self.gaze_tracker)

                # Wire emotion listener → body language
                self.personality.on_emotion_change(self.body_language.on_emotion_change)

                # Wire voice sentiment → body language
                self.voice_input.set_body_language(self.body_language)

                logger.info("Living behaviors initialized")

            # --- LLM Movement Interpreter ---
            if self.config.llm_interpreter.enabled:
                from logic.llm_interpreter import LLMInterpreter

                lic = self.config.llm_interpreter
                self.llm_interpreter = LLMInterpreter(
                    model=lic.model,
                    base_url=lic.base_url,
                    interval_s=lic.interval_s,
                    timeout_s=lic.timeout_s,
                    num_predict=lic.num_predict,
                    temperature=lic.temperature,
                    min_val=lic.min_modifier,
                    max_val=lic.max_modifier,
                )
                self.llm_interpreter.attach(
                    personality=self.personality,
                    curiosity_engine=self.curiosity_engine,
                    gaze_tracker=self.gaze_tracker,
                    body_language=self.body_language,
                    object_memory=self.object_memory,
                    presence_detector=self.presence_detector,
                )

                # Wire into consumer systems
                self.dynamics.set_llm_interpreter(self.llm_interpreter)
                if self.body_language:
                    self.body_language.set_llm_interpreter(self.llm_interpreter)
                if self.gaze_tracker:
                    self.gaze_tracker.set_llm_interpreter(self.llm_interpreter)
                if self.sound_effects_engine:
                    self.sound_effects_engine.set_llm_interpreter(self.llm_interpreter)
                if self.proactive:
                    self.proactive.set_llm_interpreter(self.llm_interpreter)

                logger.info("LLM movement interpreter initialized")

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

    def _teardown_mode(self) -> None:
        """Clean up current mode's subsystems."""
        if self.mode == Mode.PUPPETEER:
            self.puppet_server.stop_puppet()
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

    async def _handle_interaction(self, label: str, hand_over: bool = False,
                                    move_near_target: str = None,
                                    throw_away: bool = False,
                                    offset_px: int = 80) -> dict:
        """Handle interaction commands from the dashboard or voice."""
        camera_getter = lambda: self.cameras.get_frame(CameraRole.OVERHEAD)
        if move_near_target:
            result = await self._interaction.move_near(
                label, move_near_target, camera_getter, offset_px,
            )
        elif throw_away:
            result = await self._interaction.throw_away(label, camera_getter)
        elif hand_over:
            result = await self._interaction.hand_over(label, camera_getter)
        else:
            result = await self._interaction.fetch(label, camera_getter)
        return {
            "action": result.action,
            "success": result.success,
            "message": result.message,
        }

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
            asyncio.create_task(self.voice_input.start(), name="voice_input"),
        ]

        if self.llm_interpreter is not None:
            self._tasks.append(
                asyncio.create_task(self.llm_interpreter.start(), name="llm_interpreter")
            )

        try:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass

    _MODE_RUNNERS = {
        Mode.IDLE: IdleRunner,
        Mode.AUTO_SORT: AutoSortRunner,
        Mode.AUTO_TETRIS: AutoTetrisRunner,
        Mode.DEMO: DemoRunner,
        Mode.CALIBRATE: CalibrateRunner,
        Mode.PUPPETEER: PuppeteerRunner,
        Mode.PERFORMANCE: PerformanceRunner,
    }

    def _build_context(self) -> ModeContext:
        """Snapshot current deps into a ModeContext for the active runner."""
        current_mode = self.mode
        return ModeContext(
            config=self.config,
            arm=self.arm,
            gripper=self.gripper,
            calibration=self.calibration,
            cameras=self.cameras,
            detector=self.detector,
            tracker=self.tracker,
            inference=self.inference,
            sort_fsm=self.sort_fsm,
            tetris=self.tetris,
            kinesthetic=self.kinesthetic,
            state_manager=self.state_manager,
            recorder=self.recorder,
            audience_server=self.audience_server,
            narration=self.narration,
            puppet_server=self.puppet_server,
            ws_server=self._ws_server,
            rl_agent=self._rl_agent,
            personality=self.personality,
            dynamics=self.dynamics,
            is_running=lambda: self._running,
            is_current_mode=lambda: self.mode == current_mode,
            gaze_tracker=self.gaze_tracker,
            curiosity_engine=self.curiosity_engine,
            habit_engine=self.habit_engine,
            body_language=self.body_language,
            sound_effects=self.sound_effects_engine,
            proactive=self.proactive,
            object_memory=self.object_memory,
            presence_detector=self.presence_detector,
            llm_interpreter=self.llm_interpreter,
        )

    async def _mode_loop(self) -> None:
        """Main dispatch loop — runs the current mode, supports hot-swap."""
        while self._running:
            try:
                ctx = self._build_context()
                runner_cls = self._MODE_RUNNERS[self.mode]
                if runner_cls is DemoRunner:
                    runner = runner_cls(ctx, self._demo_state)
                else:
                    runner = runner_cls(ctx)
                await runner.run()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Mode loop error: {e}")
                await asyncio.sleep(0.5)

    async def shutdown(self) -> None:
        SHUTDOWN_TIMEOUT = 5.0  # seconds to wait before force-cancelling tasks
        logger.info("Shutting down")
        self._running = False

        # Stop LLM interpreter
        if self.llm_interpreter:
            await self.llm_interpreter.stop()

        # Save living behavior state
        if self.curiosity_engine:
            self.curiosity_engine.save(Path("data/curiosity_state.json"))
        if self.habit_engine:
            self.habit_engine.save(Path("data/habits.json"))
        if self.object_memory:
            self.object_memory.save()
        if self.presence_detector:
            self.presence_detector.stop()

        # Stop recording
        if self.recorder.is_recording:
            self.recorder.stop()

        # Stop services (each has its own internal _streaming flag)
        await self.voice_input.stop()
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

        if self.suction:
            self.suction.off()

        if self.magnet:
            self.magnet.off()

        if self.arm:
            self.arm.home()
            self.arm.disconnect()


async def main():
    parser = argparse.ArgumentParser(description="A.L.I.C.E. - Adaptive Learning Interface for Cognitive Exploration")
    parser.add_argument("--config", type=str, default=None, help="Path to alice.yaml config file")
    parser.add_argument("--mode", type=str, choices=["idle", "auto_sort", "auto_tetris", "demo", "calibrate", "puppeteer", "performance"], default=None)
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
