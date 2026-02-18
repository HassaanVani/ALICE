"""Train BlockRecognizerCNN on synthetic ArUco marker images."""

import random
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

from brain.cnn_model import BlockRecognizerCNN

WEIGHTS_DIR = Path(__file__).parent / "weights"
WEIGHTS_PATH = WEIGHTS_DIR / "block_recognizer.pth"

NUM_CLASSES = 16
IMG_SIZE = 64
TRAIN_PER_CLASS = 500
VAL_PER_CLASS = 100
EPOCHS = 20
BATCH_SIZE = 32
LR = 0.001


class SyntheticArucoDataset(Dataset):
    def __init__(self, images_per_class: int, seed: int = 42):
        self.images = []
        self.labels = []
        rng = np.random.RandomState(seed)
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

        for marker_id in range(NUM_CLASSES):
            base_marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 200)
            for _ in range(images_per_class):
                img = self._augment(base_marker, rng)
                self.images.append(img)
                self.labels.append(marker_id)

    def _augment(self, marker: np.ndarray, rng: np.random.RandomState) -> np.ndarray:
        size = marker.shape[0]

        # Random rotation
        angle = rng.uniform(0, 360)
        center = (size / 2, size / 2)
        M_rot = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(marker, M_rot, (size, size),
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=128)

        # Random scale
        scale = rng.uniform(0.5, 1.5)
        new_size = max(int(size * scale), 32)
        scaled = cv2.resize(rotated, (new_size, new_size), interpolation=cv2.INTER_LINEAR)

        # Slight perspective warp
        pts_src = np.float32([[0, 0], [new_size, 0], [new_size, new_size], [0, new_size]])
        jitter = rng.uniform(-new_size * 0.05, new_size * 0.05, (4, 2)).astype(np.float32)
        pts_dst = pts_src + jitter
        M_persp = cv2.getPerspectiveTransform(pts_src, pts_dst)
        warped = cv2.warpPerspective(scaled, M_persp, (new_size, new_size),
                                     borderMode=cv2.BORDER_CONSTANT, borderValue=128)

        # Random background
        canvas = np.full((IMG_SIZE, IMG_SIZE), rng.randint(80, 200), dtype=np.uint8)

        # Paste marker centered
        h, w = warped.shape[:2]
        y_off = max(0, (IMG_SIZE - h) // 2)
        x_off = max(0, (IMG_SIZE - w) // 2)
        src_y = max(0, (h - IMG_SIZE) // 2)
        src_x = max(0, (w - IMG_SIZE) // 2)
        paste_h = min(h - src_y, IMG_SIZE - y_off)
        paste_w = min(w - src_x, IMG_SIZE - x_off)
        canvas[y_off:y_off + paste_h, x_off:x_off + paste_w] = \
            warped[src_y:src_y + paste_h, src_x:src_x + paste_w]

        # Gaussian noise
        noise = rng.normal(0, rng.uniform(5, 25), canvas.shape).astype(np.float32)
        canvas = np.clip(canvas.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        # Brightness jitter
        brightness = rng.uniform(0.7, 1.3)
        canvas = np.clip(canvas.astype(np.float32) * brightness, 0, 255).astype(np.uint8)

        return canvas

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        img = self.images[idx].astype(np.float32) / 255.0
        tensor = torch.from_numpy(img).unsqueeze(0)  # (1, 64, 64)
        label = self.labels[idx]
        return tensor, label


def train():
    print("Generating synthetic training data...")
    train_ds = SyntheticArucoDataset(TRAIN_PER_CLASS, seed=42)
    val_ds = SyntheticArucoDataset(VAL_PER_CLASS, seed=123)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)

    print(f"Training: {len(train_ds)} images, Validation: {len(val_ds)} images")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = BlockRecognizerCNN().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LR)

    best_val_acc = 0.0

    for epoch in range(EPOCHS):
        # Training
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            train_total += labels.size(0)
            train_correct += predicted.eq(labels).sum().item()

        train_loss /= train_total
        train_acc = 100.0 * train_correct / train_total

        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                loss = criterion(outputs, labels)

                val_loss += loss.item() * images.size(0)
                _, predicted = outputs.max(1)
                val_total += labels.size(0)
                val_correct += predicted.eq(labels).sum().item()

        val_loss /= val_total
        val_acc = 100.0 * val_correct / val_total

        print(f"Epoch {epoch + 1:2d}/{EPOCHS}  "
              f"Train Loss: {train_loss:.4f}  Train Acc: {train_acc:.1f}%  "
              f"Val Loss: {val_loss:.4f}  Val Acc: {val_acc:.1f}%")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), WEIGHTS_PATH)

    print(f"\nBest validation accuracy: {best_val_acc:.1f}%")
    print(f"Weights saved to {WEIGHTS_PATH}")


if __name__ == "__main__":
    train()
