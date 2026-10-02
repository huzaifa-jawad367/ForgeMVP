"""Video file loader that yields ``FrameData`` instances frame-by-frame.

Usage::

    loader = VideoLoader("clip.mp4")
    for frame_data in loader:
        process(frame_data.frame)
    loader.release()
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

from app.ingestion import FrameData

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".mp4", ".avi", ".mkv", ".mov"})


class VideoLoader:
    """Iterate over frames of a local video file.

    Parameters:
        file_path: Path to a video file (``.mp4``, ``.avi``, ``.mkv``, ``.mov``).

    Raises:
        FileNotFoundError: If *file_path* does not exist.
        ValueError: If the file extension is unsupported or OpenCV cannot open it.
    """

    def __init__(self, file_path: str | Path) -> None:
        self._path = Path(file_path).resolve()

        if not self._path.exists():
            raise FileNotFoundError(f"Video file not found: {self._path}")

        if self._path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported extension '{self._path.suffix}'. "
                f"Expected one of {sorted(_SUPPORTED_EXTENSIONS)}."
            )

        self._cap = cv2.VideoCapture(str(self._path))
        if not self._cap.isOpened():
            raise ValueError(f"OpenCV failed to open video: {self._path}")

        self._fps: float = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._total_frames: int = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._width: int = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height: int = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._frame_index: int = 0

        logger.info(
            "Opened %s — %d frames, %.1f FPS, %dx%d",
            self._path.name,
            self._total_frames,
            self._fps,
            self._width,
            self._height,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def total_frames(self) -> int:
        """Total number of frames reported by the container metadata."""
        return self._total_frames

    @property
    def width(self) -> int:
        """Frame width in pixels."""
        return self._width

    @property
    def height(self) -> int:
        """Frame height in pixels."""
        return self._height

    @property
    def fps(self) -> float:
        """Native frames-per-second of the video."""
        return self._fps

    @property
    def source_id(self) -> str:
        """Canonical string identifier for this video source."""
        return str(self._path)

    # ------------------------------------------------------------------
    # Iterator protocol
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[FrameData]:
        return self

    def __next__(self) -> FrameData:
        if not self._cap.isOpened():
            raise StopIteration

        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise StopIteration

        timestamp_ms = self._cap.get(cv2.CAP_PROP_POS_MSEC)
        data = FrameData(
            frame=frame,
            frame_index=self._frame_index,
            timestamp_ms=timestamp_ms,
            source_id=self.source_id,
            fps=self._fps,
        )
        self._frame_index += 1
        return data

    # ------------------------------------------------------------------
    # Resource management
    # ------------------------------------------------------------------

    def release(self) -> None:
        """Release the underlying ``cv2.VideoCapture``."""
        if self._cap.isOpened():
            self._cap.release()
            logger.debug("Released VideoCapture for %s", self._path.name)

    def __enter__(self) -> "VideoLoader":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.release()

    def __del__(self) -> None:
        self.release()

    def __repr__(self) -> str:
        return (
            f"VideoLoader(path={self._path.name!r}, "
            f"frames={self._total_frames}, fps={self._fps:.1f})"
        )
