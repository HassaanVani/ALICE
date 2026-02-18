"""Train BlockRecognizerCNN on synthetic ArUco marker images — enhanced pipeline."""

import random
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import Dataset, DataLoader

from brain.cnn_model import BlockRecognizerCNN

WEIGHTS_DIR = Path(__file__).parent / "weights"
WEIGHTS_PATH = WEIGHTS_DIR / "block_recognizer.pth"

NUM_CLASSES = 16
IMG_SIZE = 64
TRAIN_PER_CLASS = 1000
VAL_PER_CLASS = 100
EPOCHS = 40
BATCH_SIZE = 32
LR = 0.001


def _textured_background(canvas: np.ndarray, rng: np.random.RandomState) -> np.ndarray:
    """Add Perlin-noise-like textured background using Gaussian filter."""
    try:
        from scipy.ndimage import gaussian_filter
        noise = rng.randn(*canvas.shape).astype(np.float32)
        sigma = rng.uniform(3, 10)
        smooth = gaussian_filter(noise, sigma=sigma)
        smooth = (smooth - smooth.min()) / (smooth.max() - smooth.min() + 1e-8)
        bg = (smooth * 150 + 50).astype(np.uint8)
        return bg
    except ImportError:
        return canvas


def _motion_blur(img: np.ndarray, rng: np.random.RandomState) -> np.ndarray:
    """Apply directional motion blur."""
    ksize = rng.randint(3, 9)
    if ksize % 2 == 0:
        ksize += 1
    angle = rng.uniform(0, 180)
    kernel = np.zeros((ksize, ksize), dtype=np.float32)
    center = ksize // 2
    cos_a = np.cos(np.radians(angle))
    sin_a = np.sin(np.radians(angle))
    for i in range(ksize):
        offset = i - center
        x = int(round(center + offset * cos_a))
        y = int(round(center + offset * sin_a))
        if 0 <= x < ksize and 0 <= y < ksize:
            kernel[y, x] = 1.0
    kernel /= kernel.sum() + 1e-8
    return cv2.filter2D(img, -1, kernel)


def _shadow_gradient(canvas: np.ndarray, rng: np.random.RandomState) -> np.ndarray:
    """Add a linear shadow gradient."""
    h, w = canvas.shape
    direction = rng.choice(["horizontal", "vertical"])
    intensity = rng.uniform(0.3, 0.7)
    if direction == "horizontal":
        gradient = np.linspace(1.0, intensity, w, dtype=np.float32)
        gradient = np.tile(gradient, (h, 1))
    else:
        gradient = np.linspace(1.0, intensity, h, dtype=np.float32)
        gradient = np.tile(gradient.reshape(-1, 1), (1, w))
    if rng.random() > 0.5:
        gradient = gradient[::-1]
    result = (canvas.astype(np.float32) * gradient).clip(0, 255).astype(np.uint8)
    return result


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

        # Textured background (Perlin-noise-like)
        canvas = np.full((IMG_SIZE, IMG_SIZE), rng.randint(80, 200), dtype=np.uint8)
        if rng.random() < 0.5:
            canvas = _textured_background(canvas, rng)

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

        # Motion blur (30% chance)
        if rng.random() < 0.3:
            canvas = _motion_blur(canvas, rng)

        # Partial occlusion (20% chance)
        if rng.random() < 0.2:
            for _ in range(rng.randint(1, 3)):
                rx = rng.randint(0, IMG_SIZE - 5)
                ry = rng.randint(0, IMG_SIZE - 5)
                rw = rng.randint(5, 20)
                rh = rng.randint(5, 20)
                canvas[ry:min(ry + rh, IMG_SIZE), rx:min(rx + rw, IMG_SIZE)] = rng.randint(50, 200)

        # Shadow gradient (30% chance)
        if rng.random() < 0.3:
            canvas = _shadow_gradient(canvas, rng)

        # Gaussian noise
        noise = rng.normal(0, rng.uniform(5, 25), canvas.shape).astype(np.float32)
        canvas = np.clip(canvas.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        # Contrast jitter
        contrast = rng.uniform(0.7, 1.5)
        mean = canvas.mean()
        canvas = np.clip((canvas.astype(np.float32) - mean) * contrast + mean, 0, 255).astype(np.uint8)

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
    scheduler = CosineAnnealingLR(optimizer, T_max=EPOCHS)

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

        scheduler.step()

        print(f"Epoch {epoch + 1:2d}/{EPOCHS}  "
              f"Train Loss: {train_loss:.4f}  Train Acc: {train_acc:.1f}%  "
              f"Val Loss: {val_loss:.4f}  Val Acc: {val_acc:.1f}%  "
              f"LR: {scheduler.get_last_lr()[0]:.6f}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), WEIGHTS_PATH)

    print(f"\nBest validation accuracy: {best_val_acc:.1f}%")
    print(f"Weights saved to {WEIGHTS_PATH}")


if __name__ == "__main__":
    train()
