"""Live RTSP / webcam stream loader with background capture thread.

Usage::

    stream = StreamLoader("rtsp://192.168.1.10:554/live")
    for frame_data in stream:
        if frame_data is not None:
            process(frame_data.frame)
    stream.stop()
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Iterator, Optional

import cv2
import numpy as np

from app.ingestion import FrameData

logger = logging.getLogger(__name__)

_MAX_BUFFER_SIZE: int = 30
_MAX_RETRIES: int = 3
_RETRY_DELAY_S: float = 2.0


class StreamLoader:
    """Non-blocking stream reader backed by a daemon capture thread.

    Parameters:
        source: An RTSP URL (``rtsp://…``) or the literal string ``"webcam"``
            (mapped to device index ``0``).
        buffer_size: Maximum number of frames to keep in the ring buffer.
    """

    def __init__(
        self,
        source: str,
        *,
        buffer_size: int = _MAX_BUFFER_SIZE,
    ) -> None:
        self._raw_source = source
        self._cv_source: int | str = 0 if source.lower() == "webcam" else source
        self._buffer_size = buffer_size

        self._buffer: deque[FrameData] = deque(maxlen=buffer_size)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._frame_index: int = 0
        self._fps: float = 30.0  # updated once capture is open

        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None

        self._open_capture()
        self._start_thread()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_capture(self) -> None:
        """Open (or re-open) the underlying ``VideoCapture``."""
        if self._cap is not None and self._cap.isOpened():
            self._cap.release()

        self._cap = cv2.VideoCapture(self._cv_source)
        if self._cap.isOpened():
            self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
            logger.info(
                "Opened stream %s (%.1f FPS)", self._raw_source, self._fps
            )
        else:
            logger.error("Failed to open stream: %s", self._raw_source)

    def _start_thread(self) -> None:
        """Spawn the background capture daemon."""
        self._thread = threading.Thread(
            target=self._capture_loop, name="StreamLoader-capture", daemon=True
        )
        self._thread.start()

    def _capture_loop(self) -> None:
        """Continuously grab frames, retrying on disconnection."""
        retries_left = _MAX_RETRIES

        while not self._stop_event.is_set():
            if self._cap is None or not self._cap.isOpened():
                if retries_left <= 0:
                    logger.error(
                        "Max retries (%d) exhausted for %s — stopping.",
                        _MAX_RETRIES,
                        self._raw_source,
                    )
                    break
                retries_left -= 1
                logger.warning(
                    "Stream disconnected, retrying in %.1fs (%d left) …",
                    _RETRY_DELAY_S,
                    retries_left + 1,
                )
                time.sleep(_RETRY_DELAY_S)
                self._open_capture()
                continue

            ok, frame = self._cap.read()
            if not ok or frame is None:
                # Treat a failed read as a disconnection.
                if self._cap is not None:
                    self._cap.release()
                continue

            # Successful read — reset retry budget.
            retries_left = _MAX_RETRIES

            timestamp_ms = self._cap.get(cv2.CAP_PROP_POS_MSEC)
            data = FrameData(
                frame=frame,
                frame_index=self._frame_index,
                timestamp_ms=timestamp_ms,
                source_id=self._raw_source,
                fps=self._fps,
            )
            self._frame_index += 1

            with self._lock:
                self._buffer.append(data)

        logger.debug("Capture loop exited for %s", self._raw_source)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_alive(self) -> bool:
        """``True`` if the background capture thread is still running."""
        return self._thread is not None and self._thread.is_alive()

    def read(self) -> Optional[FrameData]:
        """Pop the most recent frame from the buffer (non-blocking).

        Returns:
            The latest ``FrameData``, or ``None`` if the buffer is empty.
        """
        with self._lock:
            if self._buffer:
                return self._buffer.pop()
            return None

    def stop(self) -> None:
        """Signal the capture thread to stop and release resources."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        if self._cap is not None and self._cap.isOpened():
            self._cap.release()
        logger.info("StreamLoader stopped for %s", self._raw_source)

    # ------------------------------------------------------------------
    # Iterator protocol
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[Optional[FrameData]]:
        """Yield frames while the capture thread is alive.

        Yields ``None`` when the buffer is temporarily empty.  The caller
        should add a small sleep to avoid busy-waiting.
        """
        while self.is_alive:
            yield self.read()
        # Drain remaining buffered frames.
        while True:
            frame_data = self.read()
            if frame_data is None:
                break
            yield frame_data

    # ------------------------------------------------------------------
    # Resource management
    # ------------------------------------------------------------------

    def __enter__(self) -> "StreamLoader":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.stop()

    def __del__(self) -> None:
        self.stop()

    def __repr__(self) -> str:
        status = "alive" if self.is_alive else "stopped"
        return f"StreamLoader(source={self._raw_source!r}, {status})"
