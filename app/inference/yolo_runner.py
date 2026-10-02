"""YOLO-based and simulated inference runners.

* :class:`YOLORunner` — wraps Ultralytics YOLOv8 (requires ``ultralytics``).
* :class:`SimulatedRunner` — zero-dependency fake detector for demos/testing.
* :func:`get_inference_model` — factory that picks the best available backend.
"""

from __future__ import annotations

import logging
import random
import time
from typing import List

import numpy as np

from app.inference.model_wrapper import (
    BaseInferenceModel,
    Detection,
    InferenceResult,
)

logger = logging.getLogger(__name__)


# ======================================================================
# YOLORunner
# ======================================================================


class YOLORunner(BaseInferenceModel):
    """Run YOLOv8-nano inference via the Ultralytics library.

    Parameters:
        model_path: Path or model name passed to ``YOLO()``.  Defaults to
            ``"yolov8n.pt"`` (auto-downloaded on first use).

    Raises:
        ImportError: If the ``ultralytics`` package is not installed.
    """

    def __init__(self, model_path: str = "yolov8n.pt") -> None:
        try:
            from ultralytics import YOLO  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "The 'ultralytics' package is required for YOLORunner. "
                "Install it with:  pip install ultralytics"
            ) from exc

        self._model = YOLO(model_path)
        self._model_name = model_path
        logger.info("YOLORunner initialised with model %s", model_path)

    def predict(self, frame: np.ndarray) -> InferenceResult:
        """Run YOLOv8 on *frame* and return structured detections."""
        t0 = time.perf_counter()
        results = self._model(frame, verbose=False)
        elapsed_ms = (time.perf_counter() - t0) * 1_000.0

        detections: List[Detection] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = result.names.get(cls_id, str(cls_id))
                detections.append(
                    Detection(
                        bbox=(x1, y1, x2, y2),
                        class_name=cls_name,
                        confidence=conf,
                        class_id=cls_id,
                    )
                )

        return InferenceResult(
            detections=detections,
            inference_time_ms=elapsed_ms,
            model_name=self._model_name,
        )


# ======================================================================
# SimulatedRunner
# ======================================================================

_SIM_CLASSES: list[tuple[int, str]] = [
    (0, "person"),
    (2, "car"),
    (7, "truck"),
    (1, "bicycle"),
    (16, "dog"),
]


class SimulatedRunner(BaseInferenceModel):
    """Zero-dependency fake detector for development and demo purposes.

    Generates 1–5 random bounding boxes per frame with realistic-looking
    confidence scores.

    Attributes:
        degrade_confidence: Multiplicative factor applied to all confidence
            scores (default ``1.0``).  Set < 1 to simulate model degradation.
        degrade_latency: Extra sleep in **milliseconds** added on top of the
            base simulated latency (default ``0.0``).
    """

    def __init__(self) -> None:
        self.degrade_confidence: float = 1.0
        self.degrade_latency: float = 0.0
        logger.info("SimulatedRunner initialised (no real model loaded)")

    def predict(self, frame: np.ndarray) -> InferenceResult:
        """Return randomly generated detections with simulated latency."""
        # Simulated inference delay: 5–20 ms base + optional degradation.
        base_sleep_ms = random.uniform(5.0, 20.0)
        total_sleep_ms = base_sleep_ms + self.degrade_latency
        time.sleep(total_sleep_ms / 1_000.0)

        t0 = time.perf_counter()

        h, w = frame.shape[:2]
        num_detections = random.randint(1, 5)
        detections: list[Detection] = []

        for _ in range(num_detections):
            cls_id, cls_name = random.choice(_SIM_CLASSES)

            # Random bbox within frame bounds.
            x1 = random.uniform(0, w * 0.7)
            y1 = random.uniform(0, h * 0.7)
            x2 = x1 + random.uniform(w * 0.05, w * 0.3)
            y2 = y1 + random.uniform(h * 0.05, h * 0.3)
            x2 = min(x2, float(w))
            y2 = min(y2, float(h))

            raw_conf = random.gauss(0.82, 0.08)
            conf = float(np.clip(raw_conf * self.degrade_confidence, 0.3, 0.99))

            detections.append(
                Detection(
                    bbox=(x1, y1, x2, y2),
                    class_name=cls_name,
                    confidence=conf,
                    class_id=cls_id,
                )
            )

        elapsed_ms = (time.perf_counter() - t0) * 1_000.0 + total_sleep_ms

        return InferenceResult(
            detections=detections,
            inference_time_ms=elapsed_ms,
            model_name="simulated",
        )


# ======================================================================
# Factory
# ======================================================================


def get_inference_model() -> BaseInferenceModel:
    """Return the best available inference backend.

    Tries :class:`YOLORunner` first; falls back to :class:`SimulatedRunner`
    with a warning if Ultralytics is not installed.
    """
    try:
        return YOLORunner()
    except ImportError:
        logger.warning(
            "Ultralytics not available — falling back to SimulatedRunner. "
            "Install ultralytics for real YOLO inference."
        )
        return SimulatedRunner()
