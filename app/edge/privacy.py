from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Tuple

import cv2
import numpy as np


_FACE_LOCK = Lock()
MAX_REGIONS = 128


@lru_cache(maxsize=1)
def _face_detector():
    cascade_dir = getattr(getattr(cv2, "data", None), "haarcascades", None)
    if not cascade_dir:
        return None
    path = Path(cascade_dir) / "haarcascade_frontalface_default.xml"
    if not path.is_file():
        return None
    detector = cv2.CascadeClassifier(str(path))
    if detector.empty():
        return None
    detector.detectMultiScale(np.zeros((256, 256), np.uint8), scaleFactor=1.1,
                              minNeighbors=5, minSize=(24, 24))
    return detector


# Load and initialize the local detector outside the per-frame processing budget.
_face_detector()


def redact_image(image: np.ndarray, mode: str = "blur", blur_kernel: int = 31):
    """Return a copy, detected regions and method warnings; detection is heuristic."""
    if mode not in {"blur", "mask"}:
        raise ValueError("Mode must be blur or mask")
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Expected an 8-bit BGR image")
    height, width = image.shape[:2]
    if not width or not height:
        raise ValueError("Image must have nonzero dimensions")
    regions = []
    warnings = []

    def add_region(x, y, w, h, source):
        pad_x, pad_y = int(w * 0.1), int(h * 0.1)
        x1, y1 = max(0, x - pad_x), max(0, y - pad_y)
        x2, y2 = min(width, x + w + pad_x), min(height, y + h + pad_y)
        regions.append({"x": x1, "y": y1, "width": x2 - x1,
                        "height": y2 - y1, "source": source})

    uniform = not np.any(image != image[0, 0])
    detector = None if uniform else _face_detector()
    if uniform:
        warnings.append("Uniform image; face detection was skipped because no facial detail is present.")
    elif detector is None:
        warnings.append("Face detector unavailable; only skin-colour heuristic was used.")
    else:
        scale = min(1.0, 320 / max(height, width))
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if scale < 1:
            gray = cv2.resize(gray, (max(1, round(width * scale)), max(1, round(height * scale))),
                              interpolation=cv2.INTER_AREA)
        with _FACE_LOCK:
            faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                              minSize=(24, 24))
        for x, y, w, h in faces:
            add_region(int(x / scale), int(y / scale), int(w / scale), int(h / scale), "face")

    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    mask = cv2.inRange(ycrcb, np.array([0, 133, 77], np.uint8),
                       np.array([255, 173, 127], np.uint8))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.erode(mask, kernel, iterations=1)
    mask = cv2.dilate(mask, kernel, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        if cv2.contourArea(contour) > 100:
            add_region(*cv2.boundingRect(contour), "skin")

    if len(regions) > MAX_REGIONS:
        # Merge by detector source rather than silently dropping detections.
        merged = []
        for source in ("face", "skin"):
            matches = [region for region in regions if region["source"] == source]
            if matches:
                x1 = min(region["x"] for region in matches)
                y1 = min(region["y"] for region in matches)
                x2 = max(region["x"] + region["width"] for region in matches)
                y2 = max(region["y"] + region["height"] for region in matches)
                merged.append({"x": x1, "y": y1, "width": x2 - x1,
                               "height": y2 - y1, "source": source})
        regions = merged
        warnings.append("Too many regions detected; regions were merged into larger redaction areas.")
    regions.sort(key=lambda region: (region["y"], region["x"], region["source"]))
    output = image.copy()
    blur_kernel = max(31, int(blur_kernel))
    blur_kernel += 1 - blur_kernel % 2
    for region in regions:
        x, y, w, h = (region[key] for key in ("x", "y", "width", "height"))
        roi = output[y:y + h, x:x + w]
        if mode == "mask":
            roi[:] = 0
        else:
            roi[:] = cv2.GaussianBlur(roi, (blur_kernel, blur_kernel), 0)
    method = "opencv-haar-frontalface-default+ycrcb-skin-v1" if detector is not None else "ycrcb-skin-v1"
    if uniform:
        method = "ycrcb-skin-v1+uniform-frame-check-v1"
    return output, regions, method, warnings


def redact_worker_pii(image: np.ndarray, blur_kernel: int = 31) -> Tuple[np.ndarray, bool]:
    """Apply the shared detector/redactor without modifying the input BGR image."""
    output, regions, _, _ = redact_image(image, blur_kernel=blur_kernel)
    return output, bool(regions)
