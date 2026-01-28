import time
import math
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class PuppeteerState(Enum):
    IDLE = "idle"
    LIVE = "live"
    RECORDING = "recording"
    PLAYBACK = "playback"


@dataclass
class ArmFrame:
    timestamp: float
    angles: Tuple[float, ...]
    velocities: Tuple[float, ...] = (0.0,) * 5
    accelerations: Tuple[float, ...] = (0.0,) * 5


@dataclass
class MotionRecording:
    frames: List[ArmFrame] = field(default_factory=list)
    start_time: float = 0.0
    
    @property
    def duration(self) -> float:
        if not self.frames:
            return 0.0
        return self.frames[-1].timestamp - self.frames[0].timestamp
    
    @property
    def frame_count(self) -> int:
        return len(self.frames)


class IMUSensor:
    AXIS_COUNT = 5
    
    def __init__(self, port: str = "COM4", baudrate: int = 115200, simulate: bool = False):
        self.port = port
        self.baudrate = baudrate
        self.simulate = simulate or not SERIAL_AVAILABLE
        self._serial: Optional[serial.Serial] = None
        self._calibration_offset = np.zeros(self.AXIS_COUNT)
        self._last_angles = np.array([90.0] * self.AXIS_COUNT)
        self._sim_time = 0.0
    
    def connect(self) -> bool:
        if self.simulate:
            return True
        
        try:
            self._serial = serial.Serial(self.port, self.baudrate, timeout=0.1)
            time.sleep(1)
            return True
        except Exception as e:
            print(f"[IMUSensor] Connection failed: {e}")
            return False
    
    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None
    
    def calibrate(self) -> None:
        if self.simulate:
            self._calibration_offset = np.zeros(self.AXIS_COUNT)
            return
        
        samples = []
        for _ in range(50):
            raw = self._read_raw()
            if raw is not None:
                samples.append(raw)
            time.sleep(0.02)
        
        if samples:
            self._calibration_offset = np.mean(samples, axis=0) - 90.0
    
    def read(self) -> Optional[Tuple[float, ...]]:
        if self.simulate:
            return self._simulate_movement()
        
        raw = self._read_raw()
        if raw is None:
            return None
        
        calibrated = raw - self._calibration_offset
        calibrated = np.clip(calibrated, 0, 180)
        self._last_angles = calibrated
        return tuple(calibrated)
    
    def _read_raw(self) -> Optional[np.ndarray]:
        if not self._serial or not self._serial.is_open:
            return None
        
        try:
            line = self._serial.readline().decode().strip()
            if not line:
                return None
            
            values = [float(x) for x in line.split(",")]
            if len(values) >= self.AXIS_COUNT:
                return np.array(values[:self.AXIS_COUNT])
        except Exception:
            pass
        
        return None
    
    def _simulate_movement(self) -> Tuple[float, ...]:
        self._sim_time += 0.033
        t = self._sim_time
        
        angles = [
            90 + 30 * math.sin(t * 0.5),
            90 + 20 * math.sin(t * 0.7 + 1),
            90 + 25 * math.sin(t * 0.3 + 2),
            90 + 15 * math.sin(t * 0.9 + 3),
            90 + 10 * math.sin(t * 0.4 + 4)
        ]
        
        self._last_angles = np.array(angles)
        return tuple(angles)


class PuppeteerController:
    def __init__(self, arm_controller, sensor: Optional[IMUSensor] = None):
        self.arm = arm_controller
        self.sensor = sensor or IMUSensor(simulate=True)
        self._state = PuppeteerState.IDLE
        self._recording: Optional[MotionRecording] = None
        self._playback_index = 0
        self._on_frame: Optional[Callable[[ArmFrame], None]] = None
        self._last_frame: Optional[ArmFrame] = None
        self._mirror_mode = True
        self._smoothing = 0.3
    
    @property
    def state(self) -> PuppeteerState:
        return self._state
    
    @property
    def recording(self) -> Optional[MotionRecording]:
        return self._recording
    
    def on_frame(self, callback: Callable[[ArmFrame], None]) -> "PuppeteerController":
        self._on_frame = callback
        return self
    
    def set_mirror_mode(self, enabled: bool) -> None:
        self._mirror_mode = enabled
    
    def set_smoothing(self, factor: float) -> None:
        self._smoothing = max(0.0, min(1.0, factor))
    
    def start_live(self) -> bool:
        if not self.sensor.connect():
            return False
        
        self._state = PuppeteerState.LIVE
        return True
    
    def start_recording(self) -> bool:
        if not self.sensor.connect():
            return False
        
        self._recording = MotionRecording(start_time=time.time())
        self._state = PuppeteerState.RECORDING
        return True
    
    def stop_recording(self) -> Optional[MotionRecording]:
        result = self._recording
        self._recording = None
        self._state = PuppeteerState.IDLE
        return result
    
    def start_playback(self, recording: Optional[MotionRecording] = None) -> bool:
        rec = recording or self._recording
        if not rec or not rec.frames:
            return False
        
        self._recording = rec
        self._playback_index = 0
        self._state = PuppeteerState.PLAYBACK
        return True
    
    def stop(self) -> None:
        self._state = PuppeteerState.IDLE
        self.sensor.disconnect()
    
    def update(self) -> Optional[ArmFrame]:
        if self._state == PuppeteerState.IDLE:
            return None
        
        if self._state == PuppeteerState.PLAYBACK:
            return self._update_playback()
        
        angles = self.sensor.read()
        if angles is None:
            return self._last_frame
        
        if self._mirror_mode:
            angles = self._apply_mirror(angles)
        
        if self._last_frame and self._smoothing > 0:
            angles = self._apply_smoothing(angles, self._last_frame.angles)
        
        velocities = (0.0,) * 5
        accelerations = (0.0,) * 5
        
        if self._last_frame:
            dt = 0.033
            velocities = tuple(
                (a - b) / dt for a, b in zip(angles, self._last_frame.angles)
            )
            accelerations = tuple(
                (v - pv) / dt for v, pv in zip(velocities, self._last_frame.velocities)
            )
        
        frame = ArmFrame(
            timestamp=time.time(),
            angles=angles,
            velocities=velocities,
            accelerations=accelerations
        )
        
        if self._state == PuppeteerState.RECORDING and self._recording:
            self._recording.frames.append(frame)
        
        if self._state in (PuppeteerState.LIVE, PuppeteerState.PLAYBACK):
            self.arm.move_to(angles, speed=2.0)
        
        if self._on_frame:
            self._on_frame(frame)
        
        self._last_frame = frame
        return frame
    
    def _update_playback(self) -> Optional[ArmFrame]:
        if not self._recording or self._playback_index >= len(self._recording.frames):
            self._state = PuppeteerState.IDLE
            return None
        
        frame = self._recording.frames[self._playback_index]
        self._playback_index += 1
        
        self.arm.move_to(frame.angles, speed=2.0)
        
        if self._on_frame:
            self._on_frame(frame)
        
        self._last_frame = frame
        return frame
    
    def _apply_mirror(self, angles: Tuple[float, ...]) -> Tuple[float, ...]:
        mirrored = list(angles)
        mirrored[0] = 180 - mirrored[0]
        return tuple(mirrored)
    
    def _apply_smoothing(self, current: Tuple[float, ...], previous: Tuple[float, ...]) -> Tuple[float, ...]:
        alpha = 1 - self._smoothing
        return tuple(
            alpha * c + self._smoothing * p for c, p in zip(current, previous)
        )
    
    def encode_as_neural_activations(self, frame: ArmFrame) -> dict:
        angles_norm = np.array(frame.angles) / 180.0
        vel_norm = np.clip(np.array(frame.velocities) / 100.0, -1, 1) * 0.5 + 0.5
        acc_norm = np.clip(np.array(frame.accelerations) / 500.0, -1, 1) * 0.5 + 0.5
        
        motor_cortex = np.outer(angles_norm, angles_norm).flatten()
        
        premotor = np.convolve(
            np.concatenate([angles_norm, vel_norm]),
            np.ones(3) / 3,
            mode='same'
        )
        
        cerebellum = np.fft.fft(angles_norm).real
        cerebellum = (cerebellum - cerebellum.min()) / (cerebellum.max() - cerebellum.min() + 1e-8)
        
        basal_ganglia = vel_norm * acc_norm
        
        sensory = angles_norm
        
        return {
            "sensory_input": sensory.astype(np.float32),
            "motor_cortex": motor_cortex.astype(np.float32),
            "premotor": premotor.astype(np.float32),
            "cerebellum": cerebellum.astype(np.float32),
            "basal_ganglia": basal_ganglia.astype(np.float32)
        }
    
    def get_websocket_payload(self, frame: ArmFrame) -> bytes:
        activations = self.encode_as_neural_activations(frame)
        
        import struct
        result = bytearray()
        result.extend(struct.pack("I", len(activations)))
        
        for name, arr in activations.items():
            name_bytes = name.encode("utf-8")
            result.extend(struct.pack("I", len(name_bytes)))
            result.extend(name_bytes)
            result.extend(struct.pack("I", len(arr)))
            result.extend(arr.tobytes())
        
        return bytes(result)
