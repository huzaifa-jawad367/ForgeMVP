"""Frame brightness measurement for image-quality monitoring."""

from __future__ import annotations

import cv2
import numpy as np


def measure_brightness(frame: np.ndarray) -> float:
    """Return the mean pixel brightness of *frame* on a 0–255 scale.

    The frame is converted to single-channel grayscale before computing
    the mean, so the result is independent of colour space artefacts.

    Parameters:
        frame: Input image as a NumPy array (H×W×C, BGR ``uint8``).

    Returns:
        Mean grayscale intensity as a ``float`` in ``[0.0, 255.0]``.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray))
