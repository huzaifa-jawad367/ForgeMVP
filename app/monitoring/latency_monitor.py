"""High-precision named latency tracker for pipeline segments.

Usage::

    tracker = LatencyTracker()
    tracker.start("preprocess")
    # … do work …
    tracker.stop("preprocess")

    print(tracker.get_timings())  # {"preprocess": 12.34}
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


class LatencyTracker:
    """Measure wall-clock duration of labelled pipeline stages.

    Each stage is identified by a string *label*.  Call :meth:`start` to begin
    timing and :meth:`stop` to finish.  Timings are stored in milliseconds and
    retrieved with :meth:`get_timings`.
    """

    def __init__(self) -> None:
        self._starts: dict[str, float] = {}
        self._timings: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, label: str) -> None:
        """Record the start time for *label*.

        Parameters:
            label: Arbitrary name for the timing segment (e.g. ``"inference"``).
        """
        self._starts[label] = time.perf_counter()

    def stop(self, label: str) -> None:
        """Record the stop time for *label* and compute elapsed milliseconds.

        Parameters:
            label: Must match a previous :meth:`start` call.

        Raises:
            KeyError: If :meth:`start` was never called with *label*.
        """
        if label not in self._starts:
            raise KeyError(
                f"LatencyTracker.stop() called for unknown label {label!r}. "
                "Did you forget to call start()?"
            )
        elapsed_ms = (time.perf_counter() - self._starts.pop(label)) * 1_000.0
        self._timings[label] = elapsed_ms
        logger.debug("Timing [%s]: %.2f ms", label, elapsed_ms)

    def get_timings(self) -> dict[str, float]:
        """Return a snapshot of all completed timings in milliseconds."""
        return dict(self._timings)

    def reset(self) -> None:
        """Clear all recorded timings and pending starts."""
        self._starts.clear()
        self._timings.clear()

    def __repr__(self) -> str:
        return f"LatencyTracker(segments={list(self._timings.keys())})"
