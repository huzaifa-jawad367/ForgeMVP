import time
from typing import Tuple

import cv2
import numpy as np


def redact_worker_pii(image: np.ndarray, blur_kernel: int = 31) -> Tuple[np.ndarray, bool]:
    """Detects and redacts potential human skin/hand/face regions in an image.

    Target execution time <= 15 ms on CPU. Uses fast YCrCb skin-color thresholding.

    Args:
        image: The input image as a NumPy array (BGR format).
        blur_kernel: The kernel size for Gaussian blur, should be odd and >= 31.

    Returns:
        A tuple containing the redacted image array and a boolean flag `was_redacted`.
    """
    if blur_kernel < 31:
        blur_kernel = 31
    if blur_kernel % 2 == 0:
        blur_kernel += 1

    # Make a copy so we don't modify the original unintentionally
    output_image = image.copy()

    # Fast YCrCb conversion
    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)

    # Typical skin color ranges in YCrCb
    # Note: These values can vary, but this is a standard fast heuristic
    min_YCrCb = np.array([0, 133, 77], np.uint8)
    max_YCrCb = np.array([255, 173, 127], np.uint8)

    # Create mask
    skin_mask = cv2.inRange(ycrcb, min_YCrCb, max_YCrCb)

    # Morphology to reduce noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    skin_mask = cv2.erode(skin_mask, kernel, iterations=1)
    skin_mask = cv2.dilate(skin_mask, kernel, iterations=2)

    # Find contours
    contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    was_redacted = False

    # Only process reasonably sized regions to save time and avoid false positives
    min_area = 100
    for c in contours:
        if cv2.contourArea(c) > min_area:
            was_redacted = True
            x, y, w, h = cv2.boundingRect(c)
            # Expand bounding box slightly for safety
            pad_x = int(w * 0.1)
            pad_y = int(h * 0.1)

            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(image.shape[1], x + w + pad_x)
            y2 = min(image.shape[0], y + h + pad_y)

            # Extract region and blur
            roi = output_image[y1:y2, x1:x2]
            # using blur instead of masking, per the requirement "Apply heavy Gaussian blur ... or solid black masking"
            blurred_roi = cv2.GaussianBlur(roi, (blur_kernel, blur_kernel), 0)
            output_image[y1:y2, x1:x2] = blurred_roi

    return output_image, was_redacted
