"""Tests for brain/cnn_model.py — BlockRecognizerCNN."""

from pathlib import Path

import numpy as np
import torch
import pytest

from brain.cnn_model import BlockRecognizerCNN, create_model


WEIGHTS_PATH = Path(__file__).resolve().parent.parent / "brain" / "weights" / "block_recognizer.pth"


@pytest.fixture
def model():
    return BlockRecognizerCNN()


class TestBlockRecognizerCNN:
    def test_forward_single(self, model):
        x = torch.randn(1, 1, 64, 64)
        model.eval()
        with torch.no_grad():
            out = model(x)
        assert out.shape == (1, 16)

    def test_forward_batch(self, model):
        x = torch.randn(4, 1, 64, 64)
        model.eval()
        with torch.no_grad():
            out = model(x)
        assert out.shape == (4, 16)

    def test_predict_returns_id_and_confidence(self, model):
        x = torch.randn(1, 1, 64, 64)
        block_id, confidence = model.predict(x)
        assert 1 <= block_id <= 16
        assert 0.0 <= confidence <= 1.0

    def test_get_layer_names(self, model):
        names = model.get_layer_names()
        assert len(names) == 5
        assert all(isinstance(n, str) for n in names)

    def test_create_model_factory(self):
        m = create_model()
        assert isinstance(m, BlockRecognizerCNN)

    def test_create_model_with_pretrained(self):
        if not WEIGHTS_PATH.exists():
            pytest.skip("No pretrained weights available")
        m = create_model(pretrained_path=WEIGHTS_PATH)
        assert isinstance(m, BlockRecognizerCNN)

    def test_load_existing_weights_and_predict(self):
        if not WEIGHTS_PATH.exists():
            pytest.skip("No pretrained weights available")
        model = BlockRecognizerCNN()
        model.load(WEIGHTS_PATH)
        x = torch.randn(1, 1, 64, 64)
        block_id, confidence = model.predict(x)
        assert 1 <= block_id <= 16
        assert 0.0 <= confidence <= 1.0
