import logging
import struct
from typing import Tuple
from dataclasses import dataclass
from enum import Enum

import numpy as np

logger = logging.getLogger("Puppeteer")


class PuppeteerState(Enum):
    IDLE = "idle"
    LIVE = "live"
    RECORDING = "recording"
    PLAYBACK = "playback"


@dataclass
class ArmFrame:
    timestamp: float
    angles: Tuple[float, ...]
    velocities: Tuple[float, ...] = (0.0,) * 4
    accelerations: Tuple[float, ...] = (0.0,) * 4


def encode_as_neural_activations(frame: ArmFrame) -> dict:
    """Encode an ArmFrame as neural activation patterns for dashboard visualization."""
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


def get_websocket_payload(frame: ArmFrame) -> bytes:
    """Serialize an ArmFrame's neural activations into a binary websocket payload."""
    activations = encode_as_neural_activations(frame)

    result = bytearray()
    result.extend(struct.pack("I", len(activations)))

    for name, arr in activations.items():
        name_bytes = name.encode("utf-8")
        result.extend(struct.pack("I", len(name_bytes)))
        result.extend(name_bytes)
        result.extend(struct.pack("I", len(arr)))
        result.extend(arr.tobytes())

    return bytes(result)
