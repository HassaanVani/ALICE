from typing import Tuple, Optional
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F


class BlockRecognizerCNN(nn.Module):
    NUM_CLASSES = 16
    INPUT_SIZE = 64
    
    def __init__(self):
        super().__init__()
        
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(32)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(64)
        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm2d(128)
        
        self.pool = nn.MaxPool2d(2, 2)
        self.dropout = nn.Dropout(0.25)
        
        self.fc1 = nn.Linear(128 * 8 * 8, 256)
        self.fc2 = nn.Linear(256, self.NUM_CLASSES)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.pool(F.relu(self.bn1(self.conv1(x))))  # 64 -> 32
        x = self.pool(F.relu(self.bn2(self.conv2(x))))  # 32 -> 16
        x = self.pool(F.relu(self.bn3(self.conv3(x))))  # 16 -> 8
        
        x = x.view(x.size(0), -1)
        x = self.dropout(x)
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        
        return x
    
    def predict(self, x: torch.Tensor) -> Tuple[int, float]:
        self.eval()
        with torch.no_grad():
            logits = self.forward(x)
            probs = F.softmax(logits, dim=1)
            pred_idx = probs.argmax(dim=1).item()
            confidence = probs[0, pred_idx].item()
        return pred_idx + 1, confidence  # +1 for 1-indexed block IDs
    
    def get_layer_names(self) -> list[str]:
        return ["conv1", "conv2", "conv3", "fc1", "fc2"]
    
    def save(self, path: Path) -> None:
        torch.save(self.state_dict(), path)
    
    def load(self, path: Path) -> None:
        if path.exists():
            self.load_state_dict(torch.load(path, map_location="cpu"))


def create_model(pretrained_path: Optional[Path] = None) -> BlockRecognizerCNN:
    model = BlockRecognizerCNN()
    if pretrained_path and pretrained_path.exists():
        model.load(pretrained_path)
    return model
