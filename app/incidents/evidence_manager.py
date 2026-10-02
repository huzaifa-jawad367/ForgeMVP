"""Evidence capture and persistence for Forge incidents.

Maintains a sliding window of recent frames so that pre-incident context
can be saved alongside the incident frame itself when an anomaly fires.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any, Dict, Optional, Tuple

import numpy as np

from app.storage.file_storage import save_frame, save_json

logger = logging.getLogger(__name__)

# Type alias for a single ring-buffer entry.
_BufferEntry = Tuple[np.ndarray, int, float]  # (frame, frame_index, timestamp_ms)


class EvidenceManager:
    """Ring-buffer backed evidence capture system.

    Keeps the last *buffer_size* frames in memory so that when an incident
    is detected the manager can retrospectively save the pre-incident
    frame, the incident frame, and (later) a post-incident frame.

    Args:
        buffer_size: Maximum number of ``(frame, frame_index, timestamp)``
            entries retained.  Defaults to ``30``.
        pre_incident_offset: How many frames before the incident frame to
            look back for the "pre" snapshot.  Defaults to ``5``.
    """

    def __init__(
        self,
        buffer_size: int = 30,
        pre_incident_offset: int = 5,
    ) -> None:
        self._buffer: deque[_BufferEntry] = deque(maxlen=buffer_size)
        self._pre_incident_offset = pre_incident_offset

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def push_frame(
        self,
        frame: np.ndarray,
        frame_index: int,
        timestamp: float,
    ) -> None:
        """Append a frame to the ring buffer.

        Args:
            frame: The raw BGR image array.
            frame_index: Monotonically increasing frame counter.
            timestamp: Capture timestamp in milliseconds.
        """
        self._buffer.append((frame, frame_index, timestamp))

    def capture_evidence(
        self,
        incident_id: str,
        incident_frame_index: int,
        metrics_snapshot: Dict[str, Any],
        output_dir: str = "outputs/incidents",
    ) -> Dict[str, Any]:
        """Persist pre-incident frame, incident frame, and metrics.

        Args:
            incident_id: Unique identifier for the incident (UUID string).
            incident_frame_index: The frame index at which the incident
                was detected.
            metrics_snapshot: A JSON-serialisable dictionary of metrics at
                the time of incident.
            output_dir: Root directory under which evidence is stored.

        Returns:
            Dictionary with paths to the saved artefacts::

                {
                    "incident_id": "...",
                    "pre_frame_path": "..." | None,
                    "incident_frame_path": "..." | None,
                    "metrics_path": "...",
                    "evidence_dir": "...",
                }
        """
        evidence_dir = f"{output_dir}/{incident_id}"

        result: Dict[str, Any] = {
            "incident_id": incident_id,
            "pre_frame_path": None,
            "incident_frame_path": None,
            "metrics_path": None,
            "evidence_dir": evidence_dir,
        }

        # Build a lookup from frame_index → buffer position for fast access.
        index_map: Dict[int, int] = {
            entry[1]: pos for pos, entry in enumerate(self._buffer)
        }

        # --- Incident frame ---
        if incident_frame_index in index_map:
            incident_entry = self._buffer[index_map[incident_frame_index]]
            path = save_frame(
                incident_entry[0],
                f"{evidence_dir}/incident_frame_{incident_frame_index}.jpg",
            )
            result["incident_frame_path"] = path

        # --- Pre-incident frame (N frames before incident) ---
        pre_index = incident_frame_index - self._pre_incident_offset
        if pre_index in index_map:
            pre_entry = self._buffer[index_map[pre_index]]
            path = save_frame(
                pre_entry[0],
                f"{evidence_dir}/pre_frame_{pre_index}.jpg",
            )
            result["pre_frame_path"] = path
        else:
            # Fall back to the oldest frame in the buffer if exact offset
            # is not available.
            if self._buffer:
                oldest = self._buffer[0]
                path = save_frame(
                    oldest[0],
                    f"{evidence_dir}/pre_frame_{oldest[1]}.jpg",
                )
                result["pre_frame_path"] = path

        # --- Metrics snapshot ---
        metrics_path = save_json(
            metrics_snapshot,
            f"{evidence_dir}/metrics_snapshot.json",
        )
        result["metrics_path"] = metrics_path

        logger.info("Evidence captured for incident %s → %s", incident_id, evidence_dir)
        return result

    def capture_post_frame(
        self,
        incident_id: str,
        frame: np.ndarray,
        output_dir: str = "outputs/incidents",
    ) -> Optional[str]:
        """Save a post-incident frame once it becomes available.

        Args:
            incident_id: The incident to attach the frame to.
            frame: The post-incident image array.
            output_dir: Root evidence directory.

        Returns:
            Absolute path to the saved JPEG, or *None* on failure.
        """
        evidence_dir = f"{output_dir}/{incident_id}"
        try:
            return save_frame(frame, f"{evidence_dir}/post_frame.jpg")
        except Exception:
            logger.exception(
                "Failed to save post-incident frame for %s", incident_id
            )
            return None
