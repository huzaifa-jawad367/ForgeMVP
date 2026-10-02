"""Aggregate detection-confidence statistics for a single frame."""

from __future__ import annotations

from typing import Any, Dict, List


def measure_confidence(detections: List[Any]) -> Dict[str, float | int]:
    """Compute summary statistics over detection confidence scores.

    Parameters:
        detections: A list of objects that expose a ``.confidence`` attribute
            (e.g. :class:`~app.inference.model_wrapper.Detection` instances).

    Returns:
        A dict with keys:

        * ``mean_confidence`` — arithmetic mean of confidences.
        * ``min_confidence`` — lowest confidence.
        * ``max_confidence`` — highest confidence.
        * ``num_detections`` — number of detections.

        All values are ``0`` / ``0.0`` when *detections* is empty.
    """
    if not detections:
        return {
            "mean_confidence": 0.0,
            "min_confidence": 0.0,
            "max_confidence": 0.0,
            "num_detections": 0,
        }

    confidences = [d.confidence for d in detections]
    return {
        "mean_confidence": sum(confidences) / len(confidences),
        "min_confidence": min(confidences),
        "max_confidence": max(confidences),
        "num_detections": len(confidences),
    }
