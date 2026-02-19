import logging
import math

logger = logging.getLogger("PuppetIK")
import time
import json
from typing import Tuple, Optional, List, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np


@dataclass
class WorkspaceBounds:
    x_min: float = -150.0
    x_max: float = 150.0
    y_min: float = 50.0
    y_max: float = 250.0
    z_min: float = 0.0
    z_max: float = 150.0
    
    screen_margin: float = 0.2


@dataclass
class ArmGeometry:
    base_height: float = 50.0
    shoulder_length: float = 100.0
    elbow_length: float = 100.0
    wrist_length: float = 80.0


@dataclass
class TeachingFrame:
    timestamp: float
    world_pos: Tuple[float, float, float]
    joint_angles: Tuple[float, ...]
    gripper_state: bool


@dataclass
class LearnedMotion:
    name: str
    frames: List[TeachingFrame] = field(default_factory=list)
    created_at: float = 0.0
    
    @property
    def duration(self) -> float:
        if len(self.frames) < 2:
            return 0.0
        return self.frames[-1].timestamp - self.frames[0].timestamp


class HandToArmMapper:
    def __init__(self, geometry: Optional[ArmGeometry] = None, bounds: Optional[WorkspaceBounds] = None):
        self.geometry = geometry or ArmGeometry()
        self.bounds = bounds or WorkspaceBounds()
        self._last_hand_pos: Optional[Tuple[float, float, float]] = None
        self._smoothing = 0.3
        self._safety_margin = 10.0
    
    def set_smoothing(self, factor: float) -> None:
        self._smoothing = max(0.0, min(0.9, factor))
    
    def hand_to_world(self, hand_x: float, hand_y: float, hand_z: float) -> Tuple[float, float, float]:
        margin = self.bounds.screen_margin
        
        if not (margin < hand_x < 1 - margin and margin < hand_y < 1 - margin):
            if self._last_hand_pos:
                return self._last_hand_pos
            return (0.0, (self.bounds.y_min + self.bounds.y_max) / 2, 50.0)
        
        norm_x = (hand_x - margin) / (1 - 2 * margin)
        norm_y = (hand_y - margin) / (1 - 2 * margin)
        norm_z = max(0.0, min(1.0, hand_z))
        
        world_x = self.bounds.x_min + norm_x * (self.bounds.x_max - self.bounds.x_min)
        world_y = self.bounds.y_min + (1 - norm_y) * (self.bounds.y_max - self.bounds.y_min)
        world_z = self.bounds.z_min + norm_z * (self.bounds.z_max - self.bounds.z_min)
        
        world_z = max(self._safety_margin, world_z)
        
        if self._last_hand_pos and self._smoothing > 0:
            alpha = 1 - self._smoothing
            world_x = alpha * world_x + self._smoothing * self._last_hand_pos[0]
            world_y = alpha * world_y + self._smoothing * self._last_hand_pos[1]
            world_z = alpha * world_z + self._smoothing * self._last_hand_pos[2]
        
        self._last_hand_pos = (world_x, world_y, world_z)
        return (world_x, world_y, world_z)
    
    def solve_ik(self, world_x: float, world_y: float, world_z: float) -> Tuple[float, ...]:
        base_angle = math.degrees(math.atan2(world_y, world_x)) + 90
        
        r = math.sqrt(world_x * world_x + world_y * world_y)
        target_z = world_z - self.geometry.base_height + self.geometry.wrist_length
        
        L1 = self.geometry.shoulder_length
        L2 = self.geometry.elbow_length
        
        d = math.sqrt(r * r + target_z * target_z)
        d = min(d, L1 + L2 - 1)
        d = max(d, abs(L1 - L2) + 1)
        
        cos_elbow = (d * d - L1 * L1 - L2 * L2) / (2 * L1 * L2)
        cos_elbow = max(-1, min(1, cos_elbow))
        elbow_angle = math.degrees(math.acos(cos_elbow))
        
        alpha = math.atan2(target_z, r)
        cos_beta = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)
        cos_beta = max(-1, min(1, cos_beta))
        beta = math.acos(cos_beta)
        shoulder_angle = math.degrees(alpha + beta) + 90
        
        wrist_pitch = 90 - (shoulder_angle - 90) - (180 - elbow_angle)
        wrist_pitch = max(0, min(180, wrist_pitch + 90))
        wrist_roll = 90
        
        return (
            max(0, min(180, base_angle)),
            max(0, min(180, shoulder_angle)),
            max(0, min(180, 180 - elbow_angle)),
            wrist_pitch,
            wrist_roll
        )
    
    def hand_to_angles(self, hand_x: float, hand_y: float, hand_z: float) -> Tuple[float, ...]:
        world = self.hand_to_world(hand_x, hand_y, hand_z)
        return self.solve_ik(*world)
    
    def reset(self) -> None:
        self._last_hand_pos = None


class GestureToGripper:
    PINCH_THRESHOLD = 0.08
    FIST_THRESHOLD = 0.15
    
    def __init__(self):
        self._gripper_state = False
        self._last_change = 0.0
        self._debounce_ms = 100
    
    @property
    def is_gripping(self) -> bool:
        return self._gripper_state
    
    def update(self, landmarks: list) -> bool:
        if not landmarks or len(landmarks) < 21:
            return self._gripper_state
        
        thumb = landmarks[4]
        index = landmarks[8]
        
        pinch_dist = math.sqrt(
            (thumb['x'] - index['x']) ** 2 +
            (thumb['y'] - index['y']) ** 2 +
            (thumb.get('z', 0) - index.get('z', 0)) ** 2
        )
        
        now = time.time() * 1000
        if now - self._last_change < self._debounce_ms:
            return self._gripper_state
        
        if pinch_dist < self.PINCH_THRESHOLD:
            if not self._gripper_state:
                self._gripper_state = True
                self._last_change = now
        elif pinch_dist > self.PINCH_THRESHOLD * 1.5:
            if self._gripper_state:
                self._gripper_state = False
                self._last_change = now
        
        return self._gripper_state
    
    def is_fist(self, landmarks: list) -> bool:
        if not landmarks or len(landmarks) < 21:
            return False
        
        finger_tips = [8, 12, 16, 20]
        palm = landmarks[0]
        
        avg_dist = 0
        for tip_idx in finger_tips:
            tip = landmarks[tip_idx]
            avg_dist += math.sqrt(
                (tip['x'] - palm['x']) ** 2 +
                (tip['y'] - palm['y']) ** 2
            )
        avg_dist /= len(finger_tips)
        
        return avg_dist < self.FIST_THRESHOLD


class TeachingRecorder:
    DEFAULT_MAX_FRAMES = 6000  # 5 minutes at 50ms intervals

    def __init__(self, mapper: HandToArmMapper, max_frames: int = DEFAULT_MAX_FRAMES):
        self.mapper = mapper
        self.max_frames = max_frames
        self._recording = False
        self._current_motion: Optional[LearnedMotion] = None
        self._motions: dict[str, LearnedMotion] = {}
        self._record_interval_ms = 50
        self._last_record_time = 0.0
        self._on_frame: Optional[Callable[[TeachingFrame], None]] = None
    
    @property
    def is_recording(self) -> bool:
        return self._recording
    
    @property
    def motions(self) -> dict[str, LearnedMotion]:
        return self._motions
    
    def on_frame(self, callback: Callable[[TeachingFrame], None]) -> "TeachingRecorder":
        self._on_frame = callback
        return self
    
    def start_recording(self, name: str) -> None:
        self._current_motion = LearnedMotion(name=name, created_at=time.time())
        self._recording = True
        self._last_record_time = 0.0
    
    def stop_recording(self) -> Optional[LearnedMotion]:
        if not self._recording or not self._current_motion:
            return None
        
        self._recording = False
        motion = self._current_motion
        
        if motion.frames:
            self._motions[motion.name] = motion
        
        self._current_motion = None
        return motion
    
    def record_frame(self, hand_x: float, hand_y: float, hand_z: float, gripper: bool) -> Optional[TeachingFrame]:
        if not self._recording or not self._current_motion:
            return None

        if len(self._current_motion.frames) >= self.max_frames:
            logging.getLogger("TeachingRecorder").warning(
                f"Max frames ({self.max_frames}) reached, stopping recording"
            )
            self.stop_recording()
            return None

        now = time.time() * 1000
        if now - self._last_record_time < self._record_interval_ms:
            return None
        
        world = self.mapper.hand_to_world(hand_x, hand_y, hand_z)
        angles = self.mapper.solve_ik(*world)
        
        frame = TeachingFrame(
            timestamp=time.time(),
            world_pos=world,
            joint_angles=angles,
            gripper_state=gripper
        )
        
        self._current_motion.frames.append(frame)
        self._last_record_time = now
        
        if self._on_frame:
            self._on_frame(frame)
        
        return frame
    
    def get_motion(self, name: str) -> Optional[LearnedMotion]:
        return self._motions.get(name)
    
    def list_motions(self) -> List[str]:
        return list(self._motions.keys())
    
    def save_motions(self, path: Path) -> None:
        data = {
            name: {
                "name": m.name,
                "created_at": m.created_at,
                "frames": [asdict(f) for f in m.frames]
            }
            for name, m in self._motions.items()
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def load_motions(self, path: Path) -> bool:
        if not path.exists():
            return False
        
        try:
            with open(path) as f:
                data = json.load(f)
            
            for name, m_data in data.items():
                frames = [TeachingFrame(**f) for f in m_data["frames"]]
                motion = LearnedMotion(
                    name=m_data["name"],
                    created_at=m_data["created_at"],
                    frames=frames
                )
                self._motions[name] = motion
            
            return True
        except Exception as e:
            logger.error(f"Load failed: {e}")
            return False


class MotionPlayer:
    def __init__(self, arm_controller, magnet_driver):
        self.arm = arm_controller
        self.magnet = magnet_driver
        self._playing = False
        self._current_motion: Optional[LearnedMotion] = None
        self._playback_speed = 1.0
        self._start_time: float = 0.0
        self._last_frame_index: int = 0
        self._on_complete: Optional[Callable[[], None]] = None

    @property
    def is_playing(self) -> bool:
        return self._playing

    def on_complete(self, callback: Callable[[], None]) -> "MotionPlayer":
        self._on_complete = callback
        return self

    def set_speed(self, speed: float) -> None:
        self._playback_speed = max(0.1, min(5.0, speed))

    def play(self, motion: LearnedMotion) -> bool:
        if not motion.frames:
            return False

        self._current_motion = motion
        self._start_time = time.time()
        self._last_frame_index = 0
        self._playing = True
        return True

    def stop(self) -> None:
        self._playing = False
        self._current_motion = None
        self._last_frame_index = 0

    def update(self) -> bool:
        if not self._playing or not self._current_motion:
            return False

        frames = self._current_motion.frames
        if not frames:
            self._playing = False
            return False

        # Timestamp-based frame selection scaled by playback speed
        elapsed = (time.time() - self._start_time) * self._playback_speed
        recording_start = frames[0].timestamp
        target_time = recording_start + elapsed

        # Find the frame closest to the target timestamp
        frame_index = self._last_frame_index
        while frame_index < len(frames) - 1 and frames[frame_index + 1].timestamp <= target_time:
            frame_index += 1

        if target_time > frames[-1].timestamp:
            # Playback complete — apply last frame then finish
            frame = frames[-1]
            self.arm.move_to(frame.joint_angles, speed=2.0)
            self.magnet.toggle(frame.gripper_state)
            self._playing = False
            if self._on_complete:
                self._on_complete()
            return False

        frame = frames[frame_index]
        self.arm.move_to(frame.joint_angles, speed=2.0)
        self.magnet.toggle(frame.gripper_state)
        self._last_frame_index = frame_index
        return True
