"""Low-level file-system helpers for Forge.

Provides thin wrappers around OpenCV and JSON I/O with automatic
directory creation so callers never have to worry about missing paths.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

import cv2
import numpy as np


def ensure_dir(path: str) -> None:
    """Create *path* (and any parents) if it does not already exist.

    Args:
        path: Directory path to ensure.
    """
    os.makedirs(path, exist_ok=True)


def save_frame(frame: np.ndarray, path: str) -> str:
    """Encode *frame* as JPEG and write it to *path*.

    Parent directories are created automatically.

    Args:
        frame: BGR image array (as returned by OpenCV).
        path: Destination file path (should end in ``.jpg`` / ``.jpeg``).

    Returns:
        The absolute path to the written file.

    Raises:
        IOError: If OpenCV fails to encode or write the image.
    """
    abs_path = os.path.abspath(path)
    ensure_dir(os.path.dirname(abs_path))

    success = cv2.imwrite(abs_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not success:
        raise IOError(f"cv2.imwrite failed for {abs_path}")

    return abs_path


def save_json(data: Dict[str, Any], path: str) -> str:
    """Serialise *data* as pretty-printed JSON and write to *path*.

    Args:
        data: JSON-serialisable dictionary.
        path: Destination file path (should end in ``.json``).

    Returns:
        The absolute path to the written file.
    """
    abs_path = os.path.abspath(path)
    ensure_dir(os.path.dirname(abs_path))

    with open(abs_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)

    return abs_path
