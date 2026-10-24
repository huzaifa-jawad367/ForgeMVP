"""Resilient edge payload buffer.

Maintains an in-memory queue with optional local SQLite durability to buffer
inference metrics, defect detections, and previews on the edge during network
disconnections, with thread-safe atomic push and lease-ack operations.
"""

from __future__ import annotations

from contextlib import closing
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
        self.max_size = max(1, max_size)
        self.db_path = db_path
        self._lock = threading.Lock()
        self._queue: List[EdgePayload] = []

        self.total_enqueued = 0
        self.total_synced = 0
        self.total_dropped = 0
        self.persistence_errors = 0
        self.last_persistence_error = None
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
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
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
                    if payload.priority not in self.drops_by_tier:
                        raise ValueError("Unsupported persisted priority")
                    self._queue.append(payload)
                except Exception as e:
                    self._persistence_failed(e)
            if len(self._queue) > self.max_size:
                logger.warning("Restored backlog exceeds configured capacity; preserving existing records")
                self.max_size = len(self._queue)
            if self._queue:
                logger.info("Restored %d unsynced payloads from edge disk buffer.", len(self._queue))

    def _persistence_failed(self, error: Exception) -> None:
        self.persistence_errors += 1
        self.last_persistence_error = str(error)
        logger.error("Edge queue persistence failed: %s", error)

    def push(self, payload: EdgePayload) -> bool:
        return self.push_with_result(payload)[0]

    def push_with_result(self, payload: EdgePayload) -> tuple[bool, list[str]]:
        """Commit replacement and insertion together before publishing admission."""
        with self._lock:
            def reject():
                self.total_dropped += 1
                self.drops_by_tier[payload.priority] += 1
                return False, []

            if any(p.payload_id == payload.payload_id for p in self._queue):
                return False, []
            if payload.priority not in self.drops_by_tier:
                return False, []
            if self.db_path:
                try:
                    usage = shutil.disk_usage(Path(self.db_path).parent)
                    if usage.total and usage.used / usage.total >= .95:
                        return reject()
                except OSError as error:
                    self._persistence_failed(error)
                    return reject()
            dropped = None
            if len(self._queue) >= max(1, int(self.max_size * .8)):
                for priority in (PriorityTier.P3_METRIC, PriorityTier.P2_DIAGNOSTIC, PriorityTier.P1_ANOMALY):
                    dropped = next((p for p in self._queue if p.priority == priority), None)
                    if dropped:
                        break
                if dropped is None and (payload.priority != PriorityTier.P0_INCIDENT or len(self._queue) >= self.max_size):
                    return reject()
            if self.db_path:
                try:
                    with closing(sqlite3.connect(self.db_path)) as conn, conn:
                        if dropped:
                            conn.execute("DELETE FROM edge_queue WHERE payload_id = ?", (dropped.payload_id,))
                        conn.execute(
                            "INSERT INTO edge_queue (payload_id, frame_index, created_at, payload_json) VALUES (?, ?, ?, ?)",
                            (payload.payload_id, payload.frame_index, payload.created_at, json.dumps(payload.to_dict())),
                        )
                except Exception as error:
                    self._persistence_failed(error)
                    return reject()
            if dropped:
                self._queue.remove(dropped)
                self.total_dropped += 1
                self.drops_by_tier[dropped.priority] += 1
            self._queue.append(payload)
            self.total_enqueued += 1
            return True, [dropped.payload_id] if dropped else []

    def peek_batch(self, max_items: int = 20) -> List[EdgePayload]:
        """Peek at the oldest up to `max_items` without removing them."""
        with self._lock:
            return list(self._queue[:max_items])

    def ack_batch(self, payload_ids: List[str]) -> int:
        """Acknowledge successful sync and remove payload IDs from buffer."""
        if not payload_ids:
            return 0

        id_set = set(payload_ids)
        with self._lock:
            removed_count = sum(item.payload_id in id_set for item in self._queue)
            if self.db_path and removed_count:
                try:
                    with closing(sqlite3.connect(self.db_path)) as conn, conn:
                        conn.executemany("DELETE FROM edge_queue WHERE payload_id = ?", [(pid,) for pid in id_set])
                except Exception as error:
                    self._persistence_failed(error)
                    return 0
            self._queue = [item for item in self._queue if item.payload_id not in id_set]
            self.total_synced += removed_count
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

            persisted_rows = None
            storage_used_bytes = None
            if self.db_path:
                try:
                    with closing(sqlite3.connect(self.db_path)) as conn, conn:
                        persisted_rows = conn.execute("SELECT COUNT(*) FROM edge_queue").fetchone()[0]
                    storage_used_bytes = sum(Path(str(self.db_path) + suffix).stat().st_size
                                             for suffix in ("", "-wal", "-shm")
                                             if Path(str(self.db_path) + suffix).exists())
                except Exception as error:
                    self._persistence_failed(error)
            return {
                "capacity": self.max_size,
                "persisted_rows": persisted_rows,
                "storage_used_bytes": storage_used_bytes,
                "oldest_pending_age_seconds": max(0., time.time() - min(p.created_at for p in self._queue)) if self._queue else None,
                "persistence_errors": self.persistence_errors,
                "last_persistence_error": self.last_persistence_error,
                "durable": bool(self.db_path) and persisted_rows == len(self._queue),
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
