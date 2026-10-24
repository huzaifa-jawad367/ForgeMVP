"""Preserve raw model scores even for frames without defect detections."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import torch

from app.inference.efficientad_runner import EfficientADRunner


class AnomalyTelemetryTests(unittest.TestCase):
    def test_normal_frame_preserves_model_score(self):
        runner = EfficientADRunner.__new__(EfficientADRunner)
        runner.device = 'cpu'
        runner.target_size = (256, 256)
        runner.threshold = .5
        runner._model_name = 'test-efficientad'
        runner._model = Mock(return_value=SimpleNamespace(
            pred_score=torch.tensor(.1234), pred_label=torch.tensor(False)))
        result = runner.predict(np.zeros((30, 40, 3), dtype=np.uint8))
        self.assertEqual(result.detections, [])
        self.assertAlmostEqual(result.anomaly_score, .1234, places=5)
