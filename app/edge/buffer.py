"""Resilient edge payload buffer.

Maintains an in-memory queue with optional local SQLite durability to buffer
inference metrics, defect detections, and previews on the edge during network
disconnections, with thread-safe atomic push and lease-ack operations.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import shutil

from app.schema.contracts import PrivacyPayload, PriorityTier

logger = logging.getLogger(__name__)


@dataclass
class EdgePayload:
    """A single edge inference result and telemetry frame."""

    payload_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    boot_id: str = ""
    frame_index: int = 0
    sequence_number: int = 0
    timestamp_ms: float = 0.0
    fps: float = 0.0
    inference_time_ms: float = 0.0
    mean_confidence: float = 0.0
    min_confidence: float = 0.0
    num_detections: int = 0
    detections: List[Dict[str, Any]] = field(default_factory=list)
    brightness: float = 0.0
    blur_score: float = 0.0
    noise_level: float = 0.0
    noise_score: float = 0.0
    has_anomaly: bool = False
    anomaly_score: float = 0.0
    system_metrics: Dict[str, Any] = field(default_factory=dict)
    privacy: Optional[PrivacyPayload] = None
    frame_jpeg_b64: Optional[str] = None
    priority: PriorityTier = field(default=PriorityTier.P3_METRIC)
    timestamps: Dict[str, int] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-serialisable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EdgePayload:
        """Instantiate from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class EdgeBuffer:
    """Thread-safe edge queue with in-memory fast path and SQLite durability."""

    def __init__(
        self,
        max_size: int = 5000,
        db_path: Optional[str] = None,
    ) -> None:
        self.max_size = max_size
        self.db_path = db_path
        self._lock = threading.Lock()
        self._queue: List[EdgePayload] = []

        self.total_enqueued = 0
        self.total_synced = 0
        self.total_dropped = 0
        self.drops_by_tier = {
            PriorityTier.P0_INCIDENT: 0,
            PriorityTier.P1_ANOMALY: 0,
            PriorityTier.P2_DIAGNOSTIC: 0,
            PriorityTier.P3_METRIC: 0,
        }

        if self.db_path:
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initialise edge SQLite queue schema."""
        if not self.db_path:
            return
        p = Path(self.db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS edge_queue (
                    payload_id TEXT PRIMARY KEY,
                    frame_index INTEGER,
                    created_at REAL,
                    payload_json TEXT
                )
                """
            )
            # Load any unsynced items from disk on startup
            cursor = conn.cursor()
            cursor.execute("SELECT payload_json FROM edge_queue ORDER BY created_at ASC")
            rows = cursor.fetchall()
            for (row_json,) in rows:
                try:
                    payload = EdgePayload.from_dict(json.loads(row_json))
                    self._queue.append(payload)
                except Exception as e:
                    logger.warning("Could not restore edge payload: %s", e)
            if self._queue:
                logger.info("Restored %d unsynced payloads from edge disk buffer.", len(self._queue))

    def push(self, payload: EdgePayload) -> bool:
        """Push an inference payload into the edge buffer."""
        with self._lock:
            # Check disk fullness circuit breaker (95%)
            disk_path = self.db_path or "/"
            try:
                # Resolve directory for disk usage
                check_path = Path(disk_path).parent if self.db_path else Path(disk_path)
                if check_path.exists():
                    total, used, free = shutil.disk_usage(check_path)
                    if total > 0 and (used / total) >= 0.95:
                        logger.critical("Circuit Breaker: Edge disk >= 95%% full. Halting local caching.")
                        self.total_dropped += 1
                        self.drops_by_tier[payload.priority] += 1
                        return False
            except Exception as e:
                logger.warning(f"Failed to check disk usage: {e}")

            high_watermark = int(self.max_size * 0.80)

            # If buffer size is above or equal to high watermark, we evict to make room for the new incoming payload.
            if len(self._queue) >= high_watermark:
                evict_candidates = [
                    PriorityTier.P3_METRIC,
                    PriorityTier.P2_DIAGNOSTIC,
                    PriorityTier.P1_ANOMALY
                ]

                evicted = False
                for target_priority in evict_candidates:
                    for i in range(len(self._queue)):
                        if self._queue[i].priority == target_priority:
                            dropped = self._queue.pop(i)
                            self.total_dropped += 1
                            self.drops_by_tier[dropped.priority] += 1
                            if self.db_path:
                                try:
                                    with sqlite3.connect(self.db_path) as conn:
                                        conn.execute("DELETE FROM edge_queue WHERE payload_id = ?", (dropped.payload_id,))
                                except Exception:
                                    pass
                            logger.warning(
                                "Edge buffer >= 80%% (%d items). Evicted %s frame #%d",
                                len(self._queue) + 1,
                                dropped.priority,
                                dropped.frame_index,
                            )
                            evicted = True
                            break
                    if evicted:
                        break

                if not evicted:
                    if payload.priority != PriorityTier.P0_INCIDENT:
                        self.total_dropped += 1
                        self.drops_by_tier[payload.priority] += 1
                        logger.warning("Edge buffer full of P0s. Dropped incoming %s", payload.priority)
                        return False
                    else:
                        if len(self._queue) >= self.max_size:
                            logger.warning("Edge buffer at absolute max capacity with P0s. Dropping incoming P0.")
                            self.total_dropped += 1
                            self.drops_by_tier[payload.priority] += 1
                            return False

            self._queue.append(payload)
            self.total_enqueued += 1

            if self.db_path:
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute(
                            "INSERT OR REPLACE INTO edge_queue (payload_id, frame_index, created_at, payload_json) VALUES (?, ?, ?, ?)",
                            (payload.payload_id, payload.frame_index, payload.created_at, json.dumps(payload.to_dict())),
                        )
                except Exception as e:
                    logger.error("Failed to write edge payload to SQLite: %s", e)

            return True

    def peek_batch(self, max_items: int = 20) -> List[EdgePayload]:
        """Peek at the oldest up to `max_items` without removing them."""
        with self._lock:
            return list(self._queue[:max_items])

    def ack_batch(self, payload_ids: List[str]) -> int:
        """Acknowledge successful sync and remove payload IDs from buffer."""
        if not payload_ids:
            return 0

        id_set = set(payload_ids)
        removed_count = 0
        with self._lock:
            new_queue = []
            for item in self._queue:
                if item.payload_id in id_set:
                    removed_count += 1
                else:
                    new_queue.append(item)
            self._queue = new_queue
            self.total_synced += removed_count

            if self.db_path and removed_count > 0:
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.executemany(
                            "DELETE FROM edge_queue WHERE payload_id = ?",
                            [(pid,) for pid in id_set],
                        )
                except Exception as e:
                    logger.error("Failed to remove synced payloads from SQLite: %s", e)

        return removed_count

    def size(self) -> int:
        """Current number of buffered unsynced payloads."""
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        """True if no payloads are waiting to sync."""
        with self._lock:
            return len(self._queue) == 0

    def get_stats(self) -> Dict[str, Any]:
        """Return runtime statistics for edge telemetry."""
        with self._lock:
            counts = {
                PriorityTier.P0_INCIDENT: 0,
                PriorityTier.P1_ANOMALY: 0,
                PriorityTier.P2_DIAGNOSTIC: 0,
                PriorityTier.P3_METRIC: 0,
            }
            for item in self._queue:
                counts[item.priority] += 1

            return {
                "queue_size": len(self._queue),
                "max_size": self.max_size,
                "total_enqueued": self.total_enqueued,
                "total_synced": self.total_synced,
                "total_dropped": self.total_dropped,
                "p0_count": counts[PriorityTier.P0_INCIDENT],
                "p1_count": counts[PriorityTier.P1_ANOMALY],
                "p2_count": counts[PriorityTier.P2_DIAGNOSTIC],
                "p3_count": counts[PriorityTier.P3_METRIC],
                "drops_by_tier": {k.value: v for k, v in self.drops_by_tier.items()},
            }
