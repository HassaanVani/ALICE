"""Configuration loader for A.L.I.C.E. — loads alice.yaml with CLI/env overrides."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


DEFAULT_CONFIG_PATH = Path(__file__).parent / "alice.yaml"


@dataclass
class CameraExtrinsicsConfig:
    x_offset_mm: float = 0.0
    y_offset_mm: float = 0.0
    z_offset_mm: float = 30.0
    roll_deg: float = 0.0
    pitch_deg: float = -90.0
    yaw_deg: float = 0.0


@dataclass
class HardwareConfig:
    arm_port: Optional[str] = None
    arm_baudrate: int = 115200
    magnet_port: Optional[str] = None
    magnet_pin: int = 13
    imu_port: Optional[str] = None
    gripper_type: str = "suction"
    suction_pin: int = 5
    camera_extrinsics: CameraExtrinsicsConfig = field(default_factory=CameraExtrinsicsConfig)


@dataclass
class CameraConfigYaml:
    device_id: int = 0
    width: int = 1920
    height: int = 1080
    fps: int = 60


@dataclass
class WebSocketConfig:
    tensor_host: str = "localhost"
    tensor_port: int = 8765
    puppet_host: str = "localhost"
    puppet_port: int = 8766


@dataclass
class NarrationConfig:
    enabled: bool = False
    voice_rate: int = 175
    min_interval: int = 8
    model: str = "gemini-pro"


@dataclass
class SelfTestConfig:
    enabled: bool = True
    halt_on_failure: bool = False


@dataclass
class RecordingConfig:
    enabled: bool = False
    output_dir: str = "recordings"


@dataclass
class TimingConfig:
    idle_loop_s: float = 0.1
    sort_loop_s: float = 0.016
    camera_poll_s: float = 0.01


@dataclass
class PersonalityConfig:
    speech_threshold: float = 0.7
    speech_cooldown: float = 15.0
    override_comment_threshold: int = 3
    speed_self_initiated: float = 1.3
    speed_user_requested: float = 1.0
    speed_override: float = 0.6
    idle_micro_motion_delay: float = 3.0
    idle_tetris_delay: float = 30.0
    idle_tetris_delay_alone: float = 10.0
    micro_amplitude_deg: float = 2.0
    micro_period_s: float = 4.0


@dataclass
class TetrisScreenConfig:
    board_left: int = 0
    board_top: int = 0
    board_width: int = 300
    board_height: int = 600
    key_calibration_path: str = "tetris_key_calibration.json"


@dataclass
class TrashZoneConfig:
    enabled: bool = False
    pixel_x: int = 50
    pixel_y: int = 50
    detect_label: Optional[str] = None


@dataclass
class LLMInterpreterConfig:
    enabled: bool = False
    model: str = "llama3.2:3b"
    base_url: str = "http://localhost:11434"
    interval_s: float = 4.0
    timeout_s: float = 0.5
    num_predict: int = 40
    temperature: float = 0.3
    min_modifier: float = 0.3
    max_modifier: float = 2.0


@dataclass
class SoundEffectsConfig:
    enabled: bool = False
    intensity: float = 1.0


@dataclass
class LivingBehaviorsConfig:
    enabled: bool = False
    gaze_smoothing: float = 0.06
    gaze_face_priority: float = 0.8
    curiosity_decay_rate: float = 0.005
    curiosity_examine_threshold: float = 0.25
    habit_min_observations: int = 3
    habit_snapshot_interval_s: float = 30.0
    proactive_min_interval_s: float = 6.0
    body_language_enabled: bool = True


@dataclass
class VoiceInputConfig:
    enabled: bool = False
    activation: str = "wake_word"
    wake_word: str = "alice"
    whisper_model: str = "base.en"
    energy_threshold: int = 1000
    silence_timeout_s: float = 1.5
    max_record_s: float = 10.0


@dataclass
class AliceConfig:
    mode: str = "idle"
    simulate: bool = True
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    arm_camera: CameraConfigYaml = field(default_factory=lambda: CameraConfigYaml(
        device_id=0, width=1920, height=1080, fps=60
    ))
    front_camera: CameraConfigYaml = field(default_factory=lambda: CameraConfigYaml(
        device_id=1, width=1280, height=720, fps=30
    ))
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)
    narration: NarrationConfig = field(default_factory=NarrationConfig)
    selftest: SelfTestConfig = field(default_factory=SelfTestConfig)
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    timing: TimingConfig = field(default_factory=TimingConfig)
    tetris_screen: TetrisScreenConfig = field(default_factory=TetrisScreenConfig)
    personality: PersonalityConfig = field(default_factory=PersonalityConfig)
    trash_zone: TrashZoneConfig = field(default_factory=TrashZoneConfig)
    voice_input: VoiceInputConfig = field(default_factory=VoiceInputConfig)
    sound_effects: SoundEffectsConfig = field(default_factory=SoundEffectsConfig)
    living_behaviors: LivingBehaviorsConfig = field(default_factory=LivingBehaviorsConfig)
    llm_interpreter: LLMInterpreterConfig = field(default_factory=LLMInterpreterConfig)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base dict."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _apply_env_overrides(data: dict) -> dict:
    """Apply environment variable overrides (ALICE_ prefix)."""
    env_map = {
        "ALICE_MODE": ("mode",),
        "ALICE_SIMULATE": ("simulate",),
        "ALICE_ARM_PORT": ("hardware", "arm", "port"),
        "ALICE_MAGNET_PORT": ("hardware", "magnet", "port"),
        "ALICE_IMU_PORT": ("hardware", "imu", "port"),
        "ALICE_TENSOR_PORT": ("websocket", "tensor_port"),
        "ALICE_PUPPET_PORT": ("websocket", "puppet_port"),
    }

    # Env vars that should stay as raw strings (e.g. serial port paths)
    _string_only = {"ALICE_ARM_PORT", "ALICE_MAGNET_PORT", "ALICE_IMU_PORT", "ALICE_MODE"}

    for env_var, path in env_map.items():
        value = os.environ.get(env_var)
        if value is None:
            continue

        # String-only vars: skip boolean/int coercion to preserve casing
        if env_var not in _string_only:
            lower = value.lower()
            if lower in ("true", "false"):
                value = lower == "true"
            else:
                try:
                    value = int(value)
                except ValueError:
                    pass

        # Set nested value
        d = data
        for key in path[:-1]:
            d = d.setdefault(key, {})
        d[path[-1]] = value

    return data


def _dict_to_config(data: dict) -> AliceConfig:
    """Convert raw dict to AliceConfig dataclass tree."""
    hw_data = data.get("hardware", {})

    ce_data = hw_data.get("camera_extrinsics", {})
    camera_extrinsics = CameraExtrinsicsConfig(
        x_offset_mm=ce_data.get("x_offset_mm", 0.0),
        y_offset_mm=ce_data.get("y_offset_mm", 0.0),
        z_offset_mm=ce_data.get("z_offset_mm", 30.0),
        roll_deg=ce_data.get("roll_deg", 0.0),
        pitch_deg=ce_data.get("pitch_deg", -90.0),
        yaw_deg=ce_data.get("yaw_deg", 0.0),
    )

    hardware = HardwareConfig(
        arm_port=hw_data.get("arm", {}).get("port"),
        arm_baudrate=hw_data.get("arm", {}).get("baudrate", 115200),
        magnet_port=hw_data.get("magnet", {}).get("port"),
        magnet_pin=hw_data.get("magnet", {}).get("pin", 13),
        imu_port=hw_data.get("imu", {}).get("port"),
        gripper_type=hw_data.get("gripper_type", "suction"),
        suction_pin=hw_data.get("suction_pin", 5),
        camera_extrinsics=camera_extrinsics,
    )

    cam_data = data.get("cameras", {})
    arm_data = cam_data.get("arm_mounted", cam_data.get("overhead", {}))
    front = cam_data.get("front", {})

    arm_camera = CameraConfigYaml(
        device_id=arm_data.get("device_id", 0),
        width=arm_data.get("width", 1920),
        height=arm_data.get("height", 1080),
        fps=arm_data.get("fps", 60),
    )
    front_camera = CameraConfigYaml(
        device_id=front.get("device_id", 1),
        width=front.get("width", 1280),
        height=front.get("height", 720),
        fps=front.get("fps", 30),
    )

    ws_data = data.get("websocket", {})
    websocket = WebSocketConfig(
        tensor_host=ws_data.get("tensor_host", "localhost"),
        tensor_port=ws_data.get("tensor_port", 8765),
        puppet_host=ws_data.get("puppet_host", "localhost"),
        puppet_port=ws_data.get("puppet_port", 8766),
    )

    narr_data = data.get("narration", {})
    narration = NarrationConfig(
        enabled=narr_data.get("enabled", False),
        voice_rate=narr_data.get("voice_rate", 175),
        min_interval=narr_data.get("min_interval", 8),
        model=narr_data.get("model", "gemini-pro"),
    )

    st_data = data.get("selftest", {})
    selftest = SelfTestConfig(
        enabled=st_data.get("enabled", True),
        halt_on_failure=st_data.get("halt_on_failure", False),
    )

    rec_data = data.get("recording", {})
    recording = RecordingConfig(
        enabled=rec_data.get("enabled", False),
        output_dir=rec_data.get("output_dir", "recordings"),
    )

    tm_data = data.get("timing", {})
    timing = TimingConfig(
        idle_loop_s=tm_data.get("idle_loop_s", 0.1),
        sort_loop_s=tm_data.get("sort_loop_s", 0.016),
        camera_poll_s=tm_data.get("camera_poll_s", 0.01),
    )

    ts_data = data.get("tetris_screen", {})
    tetris_screen = TetrisScreenConfig(
        board_left=ts_data.get("board_left", 0),
        board_top=ts_data.get("board_top", 0),
        board_width=ts_data.get("board_width", 300),
        board_height=ts_data.get("board_height", 600),
        key_calibration_path=ts_data.get("key_calibration_path", "tetris_key_calibration.json"),
    )

    p_data = data.get("personality", {})
    personality = PersonalityConfig(
        speech_threshold=p_data.get("speech_threshold", 0.7),
        speech_cooldown=p_data.get("speech_cooldown", 15.0),
        override_comment_threshold=p_data.get("override_comment_threshold", 3),
        speed_self_initiated=p_data.get("speed_self_initiated", 1.3),
        speed_user_requested=p_data.get("speed_user_requested", 1.0),

        speed_override=p_data.get("speed_override", 0.6),
        idle_micro_motion_delay=p_data.get("idle_micro_motion_delay", 3.0),
        idle_tetris_delay=p_data.get("idle_tetris_delay", 30.0),
        idle_tetris_delay_alone=p_data.get("idle_tetris_delay_alone", 10.0),
        micro_amplitude_deg=p_data.get("micro_amplitude_deg", 2.0),
        micro_period_s=p_data.get("micro_period_s", 4.0),
    )

    tz_data = data.get("trash_zone", {})
    trash_zone = TrashZoneConfig(
        enabled=tz_data.get("enabled", False),
        pixel_x=tz_data.get("pixel_x", 50),
        pixel_y=tz_data.get("pixel_y", 50),
        detect_label=tz_data.get("detect_label"),
    )

    vi_data = data.get("voice_input", {})
    voice_input = VoiceInputConfig(
        enabled=vi_data.get("enabled", False),
        activation=vi_data.get("activation", "wake_word"),
        wake_word=vi_data.get("wake_word", "alice"),
        whisper_model=vi_data.get("whisper_model", "base.en"),
        energy_threshold=vi_data.get("energy_threshold", 1000),
        silence_timeout_s=vi_data.get("silence_timeout_s", 1.5),
        max_record_s=vi_data.get("max_record_s", 10.0),
    )

    li_data = data.get("llm_interpreter", {})
    llm_interpreter = LLMInterpreterConfig(
        enabled=li_data.get("enabled", False),
        model=li_data.get("model", "llama3.2:3b"),
        base_url=li_data.get("base_url", "http://localhost:11434"),
        interval_s=li_data.get("interval_s", 4.0),
        timeout_s=li_data.get("timeout_s", 0.5),
        num_predict=li_data.get("num_predict", 40),
        temperature=li_data.get("temperature", 0.3),
        min_modifier=li_data.get("min_modifier", 0.3),
        max_modifier=li_data.get("max_modifier", 2.0),
    )

    se_data = data.get("sound_effects", {})
    sound_effects = SoundEffectsConfig(
        enabled=se_data.get("enabled", False),
        intensity=se_data.get("intensity", 1.0),
    )

    lb_data = data.get("living_behaviors", {})
    living_behaviors = LivingBehaviorsConfig(
        enabled=lb_data.get("enabled", False),
        gaze_smoothing=lb_data.get("gaze_smoothing", 0.06),
        gaze_face_priority=lb_data.get("gaze_face_priority", 0.8),
        curiosity_decay_rate=lb_data.get("curiosity_decay_rate", 0.005),
        curiosity_examine_threshold=lb_data.get("curiosity_examine_threshold", 0.25),
        habit_min_observations=lb_data.get("habit_min_observations", 3),
        habit_snapshot_interval_s=lb_data.get("habit_snapshot_interval_s", 30.0),
        proactive_min_interval_s=lb_data.get("proactive_min_interval_s", 6.0),
        body_language_enabled=lb_data.get("body_language_enabled", True),
    )

    return AliceConfig(
        mode=data.get("mode", "idle"),
        simulate=data.get("simulate", True),
        hardware=hardware,
        arm_camera=arm_camera,
        front_camera=front_camera,
        websocket=websocket,
        narration=narration,
        selftest=selftest,
        recording=recording,
        timing=timing,
        tetris_screen=tetris_screen,
        personality=personality,
        trash_zone=trash_zone,
        voice_input=voice_input,
        sound_effects=sound_effects,
        living_behaviors=living_behaviors,
        llm_interpreter=llm_interpreter,
    )


def load_config(
    yaml_path: Optional[Path] = None,
    cli_overrides: Optional[dict] = None
) -> AliceConfig:
    """Load configuration from YAML file, merge CLI args and env vars.

    Priority: CLI args > env vars > YAML file > defaults.
    """
    path = yaml_path or DEFAULT_CONFIG_PATH
    data: dict = {}

    if path.exists() and YAML_AVAILABLE:
        with open(path) as f:
            data = yaml.safe_load(f) or {}

    # Apply env vars
    data = _apply_env_overrides(data)

    # Apply CLI overrides
    if cli_overrides:
        data = _deep_merge(data, cli_overrides)

    return _dict_to_config(data)
