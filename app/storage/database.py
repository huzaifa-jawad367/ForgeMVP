"""Database layer for Forge.

Uses SQLAlchemy 2.0 ORM style.  Reads ``DATABASE_URL`` from the
environment (falls back to a local SQLite file) so the same code works
unchanged against both SQLite during development and PostgreSQL in
production / Docker.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    desc,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
)

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///forge.db")

# For SQLite we need ``check_same_thread=False`` so that the FastAPI
# background threads can share the connection.
_connect_args: dict = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Shared declarative base for all Forge ORM models."""


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------


class Source(Base):
    """A video / directory / stream source registered with Forge."""

    __tablename__ = "sources"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    name: str = Column(String(256), nullable=False)
    source_type: str = Column(String(32), nullable=False)  # video | directory | stream
    path: str = Column(String(1024), nullable=False)
    status: str = Column(String(32), nullable=False, default="active")
    created_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class FrameMetric(Base):
    """Per-frame quality and detection metrics."""

    __tablename__ = "frame_metrics"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    source_id: int = Column(Integer, nullable=False, index=True)
    frame_index: int = Column(Integer, nullable=False)
    timestamp_ms: float = Column(Float, nullable=False)
    fps: float = Column(Float, nullable=False)
    inference_time_ms: float = Column(Float, nullable=False)
    mean_confidence: float = Column(Float, nullable=False, default=0.0)
    min_confidence: float = Column(Float, nullable=False, default=0.0)
    num_detections: int = Column(Integer, nullable=False, default=0)
    brightness: float = Column(Float, nullable=False, default=0.0)
    blur_score: float = Column(Float, nullable=False, default=0.0)
    noise_score: Optional[float] = Column(Float, nullable=True, default=0.0)
    created_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class SystemMetric(Base):
    """Point-in-time hardware telemetry snapshot."""

    __tablename__ = "system_metrics"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    cpu_percent: float = Column(Float, nullable=False)
    memory_percent: float = Column(Float, nullable=False)
    gpu_utilization: Optional[float] = Column(Float, nullable=True)
    gpu_memory_percent: Optional[float] = Column(Float, nullable=True)
    gpu_temperature: Optional[float] = Column(Float, nullable=True)
    created_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class Incident(Base):
    """An incident record with full evidence and metrics snapshot."""

    __tablename__ = "incidents"

    id: str = Column(String(36), primary_key=True)  # UUID
    incident_type: str = Column(String(64), nullable=False, index=True)
    source_id: Optional[int] = Column(Integer, nullable=True)
    start_time: datetime = Column(DateTime, nullable=False)
    end_time: Optional[datetime] = Column(DateTime, nullable=True)
    start_frame: int = Column(Integer, nullable=False)
    end_frame: Optional[int] = Column(Integer, nullable=True)
    status: str = Column(String(16), nullable=False, default="active")  # active | resolved
    severity: str = Column(String(16), nullable=False, default="warning")  # warning | critical
    evidence_path: Optional[str] = Column(String(1024), nullable=True)
    metrics_snapshot: Optional[str] = Column(Text, nullable=True)  # JSON string
    created_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Create all tables that do not yet exist, and migrate missing columns."""
    Base.metadata.create_all(bind=engine)

    try:
        with engine.connect() as conn:
            cursor = conn.connection.cursor()
            cursor.execute("PRAGMA table_info(frame_metrics)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "noise_score" not in existing_cols:
                cursor.execute("ALTER TABLE frame_metrics ADD COLUMN noise_score FLOAT DEFAULT 0.0")
                conn.connection.commit()
    except Exception as e:
        logger.warning("Database schema migration check failed (non-fatal): %s", e)


# ---------------------------------------------------------------------------
# Session helper
# ---------------------------------------------------------------------------


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a transactional :class:`Session`, committing on success.

    Usage::

        with get_session() as session:
            session.add(obj)
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------


def store_frame_metric(session: Session, data: Dict[str, Any]) -> FrameMetric:
    """Insert a single :class:`FrameMetric` row.

    Args:
        session: Active SQLAlchemy session.
        data: Dictionary whose keys match :class:`FrameMetric` column names.

    Returns:
        The persisted ORM instance.
    """
    valid_cols = {c.name for c in FrameMetric.__table__.columns}
    payload = {k: v for k, v in data.items() if k in valid_cols}
    metric = FrameMetric(**payload)
    session.add(metric)
    session.flush()
    return metric


def store_system_metric(session: Session, data: Dict[str, Any]) -> SystemMetric:
    """Insert a single :class:`SystemMetric` row."""
    metric = SystemMetric(**data)
    session.add(metric)
    session.flush()
    return metric


def store_incident(session: Session, data: Dict[str, Any]) -> Incident:
    """Insert a single :class:`Incident` row.

    The ``metrics_snapshot`` value is automatically JSON-encoded if it is
    passed as a dict.
    """
    payload = dict(data)

    # Ensure metrics_snapshot is stored as a JSON string.
    snap = payload.get("metrics_snapshot")
    if isinstance(snap, dict):
        payload["metrics_snapshot"] = json.dumps(snap, default=str)

    # Parse ISO datetime strings into proper datetime objects.
    for dt_field in ("start_time", "end_time"):
        val = payload.get(dt_field)
        if isinstance(val, str):
            payload[dt_field] = datetime.fromisoformat(val)

    incident = Incident(**payload)
    session.add(incident)
    session.flush()
    return incident


def get_recent_metrics(
    session: Session,
    source_id: int,
    limit: int = 100,
) -> List[FrameMetric]:
    """Return the most recent frame metrics for a source."""
    return (
        session.query(FrameMetric)
        .filter(FrameMetric.source_id == source_id)
        .order_by(desc(FrameMetric.id))
        .limit(limit)
        .all()
    )


def get_recent_system_metrics(
    session: Session,
    limit: int = 100,
) -> List[SystemMetric]:
    """Return the most recent system-level metrics."""
    return (
        session.query(SystemMetric)
        .order_by(desc(SystemMetric.id))
        .limit(limit)
        .all()
    )


def get_incidents(
    session: Session,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Incident]:
    """Return incidents, optionally filtered by status."""
    query = session.query(Incident)
    if status:
        query = query.filter(Incident.status == status)
    return query.order_by(desc(Incident.created_at)).limit(limit).all()


def update_incident(
    session: Session,
    incident_id: str,
    updates: Dict[str, Any],
) -> Optional[Incident]:
    """Apply *updates* to the incident identified by *incident_id*.

    Returns:
        The updated :class:`Incident` or *None* if not found.
    """
    incident = session.query(Incident).get(incident_id)
    if incident is None:
        return None

    for key, value in updates.items():
        if key == "metrics_snapshot" and isinstance(value, dict):
            value = json.dumps(value, default=str)
        if key in ("start_time", "end_time") and isinstance(value, str):
            value = datetime.fromisoformat(value)
        setattr(incident, key, value)

    session.flush()
    return incident
