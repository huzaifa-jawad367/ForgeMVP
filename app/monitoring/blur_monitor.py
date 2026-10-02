"""Frame blur / sharpness measurement using the Laplacian variance method."""

from __future__ import annotations

import cv2
import numpy as np


def measure_blur(frame: np.ndarray) -> float:
    """Return a sharpness score for *frame* (higher ⇒ sharper).

    Applies a Laplacian filter (``ksize=3``) to the grayscale version of
    the image and returns the **variance** of the result.  Blurry images
    produce low variance; crisp images produce high variance.

    Parameters:
        frame: Input image as a NumPy array (H×W×C, BGR ``uint8``).

    Returns:
        Variance of the Laplacian as a ``float`` (≥ 0).
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F, ksize=3)
    return float(laplacian.var())
