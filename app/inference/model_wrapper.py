"""Abstract base class and data structures for object-detection inference.

Every concrete inference model in Forge inherits from
:class:`BaseInferenceModel` and implements :meth:`predict`.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class Detection:
    """A single detected object within a frame.

    Attributes:
        bbox: Bounding box as ``(x1, y1, x2, y2)`` pixel coordinates.
        class_name: Human-readable class label (e.g. ``"person"``).
        confidence: Model confidence score in ``[0, 1]``.
        class_id: Integer class index used by the model.
    """

    bbox: tuple[float, float, float, float]
    class_name: str
    confidence: float
    class_id: int


@dataclass
class InferenceResult:
    """Container for the output of a single model inference call.

    Attributes:
        detections: Detected objects for the frame.
        inference_time_ms: Wall-clock time spent in the model, in milliseconds.
        model_name: Identifier for the model that produced this result.
    """

    detections: list[Detection] = field(default_factory=list)
    inference_time_ms: float = 0.0
    model_name: str = ""


class BaseInferenceModel(abc.ABC):
    """Abstract interface that all Forge inference backends must implement."""

    @abc.abstractmethod
    def predict(self, frame: np.ndarray) -> InferenceResult:
        """Run inference on a single BGR frame.

        Parameters:
            frame: Input image as a NumPy array (H×W×3, ``uint8``, BGR).

        Returns:
            An :class:`InferenceResult` containing detections and timing info.
        """
        ...


__all__ = ["Detection", "InferenceResult", "BaseInferenceModel"]
