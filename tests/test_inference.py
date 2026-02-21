"""Tests for brain/inference.py — InferencePipeline."""

import numpy as np
import torch
import pytest

from brain.inference import InferencePipeline


@pytest.fixture
def pipeline():
    return InferencePipeline()


class TestInferencePipeline:
    def test_predict_returns_id_conf_activations(self, pipeline, sample_block_image):
        block_id, confidence, activations = pipeline.predict(sample_block_image)
        assert 1 <= block_id <= 16
        assert 0.0 <= confidence <= 1.0
        assert isinstance(activations, dict)

    def test_freeze_caches_result(self, pipeline, sample_block_image):
        result1 = pipeline.predict(sample_block_image)
        pipeline.freeze()
        assert pipeline.is_frozen is True
        # Predict with different image should return cached result
        other_img = np.ones((64, 64), dtype=np.uint8) * 128
        result2 = pipeline.predict(other_img)
        assert result2[0] == result1[0]
        assert result2[1] == result1[1]

    def test_unfreeze_allows_updates(self, pipeline, sample_block_image):
        pipeline.predict(sample_block_image)
        pipeline.freeze()
        pipeline.unfreeze()
        assert pipeline.is_frozen is False

    def test_toggle_freeze(self, pipeline):
        assert pipeline.is_frozen is False
        result = pipeline.toggle_freeze()
        assert result is True
        assert pipeline.is_frozen is True
        result = pipeline.toggle_freeze()
        assert result is False
        assert pipeline.is_frozen is False

    def test_preprocess_grayscale(self, pipeline):
        img = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
        tensor = pipeline.preprocess(img)
        assert tensor.shape == (1, 1, 64, 64)
        assert tensor.dtype == torch.float32

    def test_preprocess_color(self, pipeline):
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        tensor = pipeline.preprocess(img)
        assert tensor.shape == (1, 1, 64, 64)
        assert tensor.dtype == torch.float32

    def test_predict_batch(self, pipeline, sample_block_image, sample_color_image):
        results = pipeline.predict_batch([sample_block_image, sample_color_image])
        assert len(results) == 2
        for block_id, confidence in results:
            assert 1 <= block_id <= 16
            assert 0.0 <= confidence <= 1.0

    def test_predict_batch_empty(self, pipeline):
        results = pipeline.predict_batch([])
        assert results == []
