"""Training script for BlockStateClassifier — synthetic data for UPRIGHT/TILTED/STACKED/OCCLUDED."""

from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

from brain.state_model import BlockStateClassifier, BlockState

WEIGHTS_DIR = Path(__file__).parent / "weights"
WEIGHTS_PATH = WEIGHTS_DIR / "block_state.pth"

NUM_CLASSES = 4
IMG_SIZE = 64
TRAIN_PER_CLASS = 500
VAL_PER_CLASS = 100
EPOCHS = 30
BATCH_SIZE = 32
LR = 0.001


class SyntheticStateDataset(Dataset):
    def __init__(self, images_per_class: int, seed: int = 42):
        self.images = []
        self.labels = []
        rng = np.random.RandomState(seed)
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

        for state_idx in range(NUM_CLASSES):
            for _ in range(images_per_class):
                marker_id = rng.randint(0, 16)
                base_marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 200)
                img = self._make_state_image(base_marker, BlockState(state_idx), rng)
                self.images.append(img)
                self.labels.append(state_idx)

    def _make_state_image(self, marker: np.ndarray, state: BlockState,
                          rng: np.random.RandomState) -> np.ndarray:
        size = marker.shape[0]
        canvas = np.full((IMG_SIZE, IMG_SIZE), rng.randint(80, 200), dtype=np.uint8)

        if state == BlockState.UPRIGHT:
            # Standard rotation + small perspective
            angle = rng.uniform(-15, 15)
            scale = rng.uniform(0.6, 1.0)
        elif state == BlockState.TILTED:
            # Large rotation + strong perspective
            angle = rng.uniform(25, 80) * rng.choice([-1, 1])
            scale = rng.uniform(0.5, 0.9)
        elif state == BlockState.STACKED:
            # Two overlapping markers
            angle = rng.uniform(0, 360)
            scale = rng.uniform(0.4, 0.7)
        elif state == BlockState.OCCLUDED:
            angle = rng.uniform(0, 360)
            scale = rng.uniform(0.5, 1.0)
        else:
            angle, scale = 0, 0.7

        # Apply transform
        center = (size / 2, size / 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(marker, M, (size, size), borderValue=128)

        new_size = max(int(size * scale), 32)
        scaled = cv2.resize(rotated, (new_size, new_size))

        # Perspective warp
        pts_src = np.float32([[0, 0], [new_size, 0], [new_size, new_size], [0, new_size]])
        jitter_scale = 0.03 if state == BlockState.UPRIGHT else 0.12
        jitter = rng.uniform(-new_size * jitter_scale, new_size * jitter_scale, (4, 2)).astype(np.float32)
        pts_dst = pts_src + jitter
        M_p = cv2.getPerspectiveTransform(pts_src, pts_dst)
        warped = cv2.warpPerspective(scaled, M_p, (new_size, new_size), borderValue=128)

        # Paste onto canvas
        h, w = warped.shape[:2]
        y_off = max(0, (IMG_SIZE - h) // 2)
        x_off = max(0, (IMG_SIZE - w) // 2)
        src_y = max(0, (h - IMG_SIZE) // 2)
        src_x = max(0, (w - IMG_SIZE) // 2)
        paste_h = min(h - src_y, IMG_SIZE - y_off)
        paste_w = min(w - src_x, IMG_SIZE - x_off)
        canvas[y_off:y_off + paste_h, x_off:x_off + paste_w] = \
            warped[src_y:src_y + paste_h, src_x:src_x + paste_w]

        if state == BlockState.STACKED:
            # Add a second smaller marker on top
            marker2_id = rng.randint(0, 16)
            dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            m2 = cv2.aruco.generateImageMarker(dictionary, marker2_id, 100)
            m2_resized = cv2.resize(m2, (24, 24))
            ox, oy = rng.randint(10, 30), rng.randint(10, 30)
            canvas[oy:oy + 24, ox:ox + 24] = cv2.addWeighted(
                canvas[oy:oy + 24, ox:ox + 24], 0.4, m2_resized, 0.6, 0
            )

        if state == BlockState.OCCLUDED:
            # Add random rectangles to occlude
            for _ in range(rng.randint(1, 3)):
                rx = rng.randint(0, IMG_SIZE - 10)
                ry = rng.randint(0, IMG_SIZE - 10)
                rw = rng.randint(10, 30)
                rh = rng.randint(10, 30)
                color = rng.randint(50, 200)
                canvas[ry:min(ry + rh, IMG_SIZE), rx:min(rx + rw, IMG_SIZE)] = color

        # Noise + brightness
        noise = rng.normal(0, rng.uniform(5, 20), canvas.shape).astype(np.float32)
        canvas = np.clip(canvas.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        brightness = rng.uniform(0.7, 1.3)
        canvas = np.clip(canvas.astype(np.float32) * brightness, 0, 255).astype(np.uint8)

        return canvas

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        img = self.images[idx].astype(np.float32) / 255.0
        tensor = torch.from_numpy(img).unsqueeze(0)
        return tensor, self.labels[idx]


def train():
    print("Generating synthetic block state training data...")
    train_ds = SyntheticStateDataset(TRAIN_PER_CLASS, seed=42)
    val_ds = SyntheticStateDataset(VAL_PER_CLASS, seed=123)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)

    print(f"Training: {len(train_ds)} images, Validation: {len(val_ds)} images")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = BlockStateClassifier().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LR)

    best_val_acc = 0.0

    for epoch in range(EPOCHS):
        model.train()
        train_loss, train_correct, train_total = 0.0, 0, 0

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

        model.eval()
        val_loss, val_correct, val_total = 0.0, 0, 0

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
              f"Train Loss: {train_loss:.4f}  Acc: {train_acc:.1f}%  "
              f"Val Loss: {val_loss:.4f}  Acc: {val_acc:.1f}%")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), WEIGHTS_PATH)

    print(f"\nBest validation accuracy: {best_val_acc:.1f}%")
    print(f"Weights saved to {WEIGHTS_PATH}")


if __name__ == "__main__":
    train()
