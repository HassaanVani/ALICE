from typing import Dict, List, Optional, Callable
from collections import OrderedDict

import torch
import torch.nn as nn
import numpy as np


class HookManager:
    def __init__(self):
        self._activations: OrderedDict[str, torch.Tensor] = OrderedDict()
        self._gradients: OrderedDict[str, torch.Tensor] = OrderedDict()
        self._handles: List[torch.utils.hooks.RemovableHandle] = []
        self._layer_info: Dict[str, dict] = {}
    
    @property
    def activations(self) -> OrderedDict[str, torch.Tensor]:
        return self._activations
    
    @property
    def layer_names(self) -> List[str]:
        return list(self._activations.keys())
    
    def register_hooks(self, model: nn.Module, layer_names: Optional[List[str]] = None) -> None:
        self.clear()
        
        for name, module in model.named_modules():
            if layer_names and name not in layer_names:
                continue
            
            if isinstance(module, (nn.Conv2d, nn.Linear, nn.BatchNorm2d)):
                handle = module.register_forward_hook(self._create_forward_hook(name))
                self._handles.append(handle)
                
                self._layer_info[name] = {
                    "type": module.__class__.__name__,
                    "params": sum(p.numel() for p in module.parameters())
                }
    
    def _create_forward_hook(self, name: str) -> Callable:
        def hook(module: nn.Module, input: tuple, output: torch.Tensor) -> None:
            self._activations[name] = output.detach().clone()
        return hook
    
    def get_activations(self) -> Dict[str, np.ndarray]:
        return {
            name: tensor.cpu().numpy()
            for name, tensor in self._activations.items()
        }
    
    def get_activation(self, layer_name: str) -> Optional[np.ndarray]:
        tensor = self._activations.get(layer_name)
        return tensor.cpu().numpy() if tensor is not None else None
    
    def get_activation_stats(self, layer_name: str) -> Optional[dict]:
        arr = self.get_activation(layer_name)
        if arr is None:
            return None
        
        return {
            "shape": arr.shape,
            "min": float(arr.min()),
            "max": float(arr.max()),
            "mean": float(arr.mean()),
            "std": float(arr.std())
        }
    
    def to_voxel_grid(self, layer_name: str, resolution: int = 32) -> Optional[np.ndarray]:
        arr = self.get_activation(layer_name)
        if arr is None:
            return None
        
        if len(arr.shape) == 4:  # Conv layer: (B, C, H, W)
            data = arr[0]  # Take first batch
            c, h, w = data.shape
            
            normalized = (data - data.min()) / (data.max() - data.min() + 1e-8)
            mean_activation = normalized.mean(axis=0)
            
            from scipy.ndimage import zoom
            scale_h = resolution / h
            scale_w = resolution / w
            resized = zoom(mean_activation, (scale_h, scale_w), order=1)
            
            voxels = np.zeros((resolution, resolution, resolution))
            depth_per_channel = max(1, resolution // c)
            
            for ch in range(min(c, resolution)):
                ch_data = normalized[ch]
                ch_resized = zoom(ch_data, (scale_h, scale_w), order=1)
                z_start = ch * depth_per_channel
                z_end = min(z_start + depth_per_channel, resolution)
                for z in range(z_start, z_end):
                    voxels[:, :, z] = ch_resized
            
            return voxels
        
        elif len(arr.shape) == 2:  # FC layer: (B, features)
            data = arr[0]
            normalized = (data - data.min()) / (data.max() - data.min() + 1e-8)
            
            side = int(np.ceil(len(data) ** (1/3)))
            padded = np.zeros(side ** 3)
            padded[:len(data)] = normalized
            voxels = padded.reshape((side, side, side))
            
            from scipy.ndimage import zoom
            scale = resolution / side
            return zoom(voxels, scale, order=1)
        
        return None
    
    def serialize_for_websocket(self, layer_name: Optional[str] = None) -> bytes:
        if layer_name:
            arr = self.get_activation(layer_name)
            if arr is None:
                return b""
            return arr.astype(np.float32).tobytes()
        
        data = {}
        for name, arr in self.get_activations().items():
            flat = arr.flatten().astype(np.float32)
            if len(flat) > 1024:
                indices = np.linspace(0, len(flat) - 1, 1024, dtype=int)
                flat = flat[indices]
            data[name] = flat
        
        import struct
        result = bytearray()
        result.extend(struct.pack("I", len(data)))
        
        for name, arr in data.items():
            name_bytes = name.encode("utf-8")
            result.extend(struct.pack("I", len(name_bytes)))
            result.extend(name_bytes)
            result.extend(struct.pack("I", len(arr)))
            result.extend(arr.tobytes())
        
        return bytes(result)
    
    def clear(self) -> None:
        for handle in self._handles:
            handle.remove()
        self._handles.clear()
        self._activations.clear()
        self._gradients.clear()
        self._layer_info.clear()
    
    def __del__(self):
        self.clear()
