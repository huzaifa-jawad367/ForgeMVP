"""Forge ingestion module — video/stream loading and frame data structures."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass


@dataclass
class FrameData:
    """Immutable container for a single decoded video frame and its metadata.

    Attributes:
        frame: Raw pixel data as a NumPy array (H×W×C, BGR colour order).
        frame_index: Zero-based ordinal position of the frame in its source.
        timestamp_ms: Presentation timestamp in milliseconds.
        source_id: Human-readable identifier for the originating source
            (file path, RTSP URL, or ``"webcam"``).
        fps: Native frames-per-second of the source at capture time.
    """

    frame: np.ndarray
    frame_index: int
    timestamp_ms: float
    source_id: str
    fps: float


__all__ = ["FrameData"]
