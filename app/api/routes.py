"""FastAPI routes for the Forge observability API.

Exposes REST endpoints for sources, metrics, incidents, demo degradation
controls, and pipeline status.  All database access goes through the
helpers in :mod:`app.storage.database`.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.state import DEGRADATION_STATE, PIPELINE_STATE
from app.storage.database import (
    FrameMetric,
    Incident,
    Source,
    SystemMetric,
    get_incidents,
    get_recent_metrics,
    get_recent_system_metrics,
    get_session,
    store_incident,
    update_incident,
)

router = APIRouter()


# =========================================================================
# Pydantic request / response schemas
# =========================================================================


class SourceCreate(BaseModel):
    """Body for ``POST /api/sources``."""

    name: str
    source_type: str = Field(..., pattern=r"^(video|directory|stream)$")
    path: str


class SourceOut(BaseModel):
    """Response schema for a registered source."""

    id: int
    name: str
    source_type: str
    path: str
    status: str
    created_at: str

    class Config:
        from_attributes = True


class DegradationInput(BaseModel):
    """Body for ``POST /api/demo/degrade``."""

    blur: float = Field(0.0, ge=0.0, le=100.0)
    brightness: float = Field(0.0, ge=0.0, le=100.0)
    noise: float = Field(0.0, ge=0.0, le=100.0)
    confidence: float = Field(0.0, ge=0.0, le=100.0)
    latency: float = Field(0.0, ge=0.0, le=5000.0)


class PipelineStartInput(BaseModel):
    """Body for ``POST /api/pipeline/start``."""

    input: str  # path, URL, webcam index, or visa:category (e.g. visa:pcb1)
    loop: bool = True
    fps: Optional[float] = 10.0
    model: Optional[str] = None


# =========================================================================
# Sources
# =========================================================================


@router.get("/api/sources", response_model=List[SourceOut], tags=["Sources"])
def list_sources() -> Any:
    """Return all registered sources."""
    with get_session() as session:
        sources = session.query(Source).order_by(Source.id).all()
        return [
            SourceOut(
                id=s.id,
                name=s.name,
                source_type=s.source_type,
                path=s.path,
                status=s.status,
                created_at=s.created_at.isoformat() if s.created_at else "",
            )
            for s in sources
        ]


@router.post("/api/sources", response_model=SourceOut, status_code=201, tags=["Sources"])
def add_source(body: SourceCreate) -> Any:
    """Register a new video/directory/stream source."""
    with get_session() as session:
        source = Source(
            name=body.name,
            source_type=body.source_type,
            path=body.path,
            status="active",
        )
        session.add(source)
        session.flush()
        return SourceOut(
            id=source.id,
            name=source.name,
            source_type=source.source_type,
            path=source.path,
            status=source.status,
            created_at=source.created_at.isoformat() if source.created_at else "",
        )


# =========================================================================
# Metrics
# =========================================================================


@router.get("/api/metrics", tags=["Metrics"])
def get_frame_metrics(
    source_id: int = Query(..., description="Source ID to filter by"),
    limit: int = Query(100, ge=1, le=1000),
) -> Any:
    """Return recent frame metrics for a given source."""
    with get_session() as session:
        rows = get_recent_metrics(session, source_id=source_id, limit=limit)
        return [_frame_metric_to_dict(r) for r in rows]


@router.get("/api/metrics/system", tags=["Metrics"])
def get_system_metrics(limit: int = Query(100, ge=1, le=1000)) -> Any:
    """Return recent system-level hardware metrics."""
    with get_session() as session:
        rows = get_recent_system_metrics(session, limit=limit)
        return [_system_metric_to_dict(r) for r in rows]


@router.get("/api/metrics/latest", tags=["Metrics"])
def get_latest_metrics() -> Any:
    """Return the single most recent frame metric and system metric."""
    with get_session() as session:
        frame_rows = (
            session.query(FrameMetric)
            .order_by(FrameMetric.id.desc())
            .limit(1)
            .all()
        )
        sys_rows = (
            session.query(SystemMetric)
            .order_by(SystemMetric.id.desc())
            .limit(1)
            .all()
        )
        return {
            "frame_metric": _frame_metric_to_dict(frame_rows[0]) if frame_rows else None,
            "system_metric": _system_metric_to_dict(sys_rows[0]) if sys_rows else None,
        }


# =========================================================================
# Incidents
# =========================================================================


@router.get("/api/incidents", tags=["Incidents"])
def list_incidents(
    status: Optional[str] = Query(None, pattern=r"^(active|resolved)$"),
    limit: int = Query(50, ge=1, le=500),
) -> Any:
    """List incidents, optionally filtered by status."""
    with get_session() as session:
        rows = get_incidents(session, status=status, limit=limit)
        return [_incident_to_dict(r) for r in rows]


@router.get("/api/incidents/{incident_id}", tags=["Incidents"])
def get_incident(incident_id: str) -> Any:
    """Retrieve full detail for a single incident."""
    with get_session() as session:
        row = session.query(Incident).get(incident_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        return _incident_to_dict(row)


@router.post("/api/incidents/{incident_id}/resolve", tags=["Incidents"])
def resolve_incident(incident_id: str) -> Any:
    """Mark an incident as resolved."""
    with get_session() as session:
        updated = update_incident(
            session,
            incident_id,
            {
                "status": "resolved",
                "end_time": datetime.now(timezone.utc).isoformat(),
            },
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Export resolved incident to websocket stream
        try:
            from app.telemetry.reporter import telemetry_manager
            telemetry_manager.export_incident(_incident_to_dict(updated))
        except Exception:
            # Don't fail the HTTP response if telemetry reporting fails
            pass

        return {"status": "resolved", "incident_id": incident_id}


@router.get("/api/incidents/{incident_id}/evidence", tags=["Incidents"])
def get_incident_evidence(incident_id: str) -> Any:
    """Return evidence image filenames and metadata for an incident."""
    with get_session() as session:
        row = session.query(Incident).get(incident_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Incident not found")

        evidence_dir = row.evidence_path
        images: List[str] = []
        metadata: Optional[Dict[str, Any]] = None

        if evidence_dir and os.path.isdir(evidence_dir):
            for fname in sorted(os.listdir(evidence_dir)):
                if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                    images.append(fname)
                elif fname.endswith(".json"):
                    fpath = os.path.join(evidence_dir, fname)
                    with open(fpath, "r", encoding="utf-8") as fh:
                        metadata = json.load(fh)

        return {
            "incident_id": incident_id,
            "evidence_dir": evidence_dir,
            "images": images,
            "metadata": metadata,
        }


# =========================================================================
# Demo / Degradation Controls
# =========================================================================


@router.get("/api/demo/status", tags=["Demo"])
def demo_status() -> Any:
    """Return current degradation settings."""
    return dict(DEGRADATION_STATE)


@router.post("/api/demo/degrade", tags=["Demo"])
def demo_degrade(body: DegradationInput) -> Any:
    """Apply degradation settings used by the pipeline in real time."""
    DEGRADATION_STATE["blur"] = body.blur / 100.0 if body.blur > 1.0 else body.blur
    DEGRADATION_STATE["brightness"] = body.brightness / 100.0 if body.brightness > 1.0 else body.brightness
    DEGRADATION_STATE["noise"] = body.noise / 100.0 if body.noise > 1.0 else body.noise
    DEGRADATION_STATE["confidence"] = body.confidence / 100.0 if body.confidence > 1.0 else body.confidence
    DEGRADATION_STATE["latency"] = body.latency
    return {"status": "applied", **dict(DEGRADATION_STATE)}


@router.post("/api/demo/reset", tags=["Demo"])
def demo_reset() -> Any:
    """Reset all degradation values to zero."""
    for key in DEGRADATION_STATE:
        DEGRADATION_STATE[key] = 0.0
    return {"status": "reset", **dict(DEGRADATION_STATE)}


# =========================================================================
# Pipeline Status
# =========================================================================


@router.get("/api/pipeline/status", tags=["Pipeline"])
def pipeline_status() -> Any:
    """Return the current pipeline runtime state."""
    state = dict(PIPELINE_STATE)
    # Compute uptime if running.
    if state["is_running"] and state["start_time"] is not None:
        try:
            start = datetime.fromisoformat(str(state["start_time"]))
            state["uptime_seconds"] = (
                datetime.now(timezone.utc) - start
            ).total_seconds()
        except (ValueError, TypeError):
            state["uptime_seconds"] = None
    else:
        state["uptime_seconds"] = None
    return state


# =========================================================================
# Internal serialisation helpers
# =========================================================================


def _frame_metric_to_dict(m: FrameMetric) -> Dict[str, Any]:
    return {
        "id": m.id,
        "source_id": m.source_id,
        "frame_index": m.frame_index,
        "timestamp_ms": m.timestamp_ms,
        "fps": m.fps,
        "inference_time_ms": m.inference_time_ms,
        "mean_confidence": m.mean_confidence,
        "min_confidence": m.min_confidence,
        "num_detections": m.num_detections,
        "brightness": m.brightness,
        "blur_score": m.blur_score,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _system_metric_to_dict(m: SystemMetric) -> Dict[str, Any]:
    return {
        "id": m.id,
        "cpu_percent": m.cpu_percent,
        "memory_percent": m.memory_percent,
        "gpu_utilization": m.gpu_utilization,
        "gpu_memory_percent": m.gpu_memory_percent,
        "gpu_temperature": m.gpu_temperature,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _incident_to_dict(i: Incident) -> Dict[str, Any]:
    snap = i.metrics_snapshot
    if isinstance(snap, str):
        try:
            snap = json.loads(snap)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "id": i.id,
        "incident_type": i.incident_type,
        "source_id": i.source_id,
        "start_time": i.start_time.isoformat() if i.start_time else None,
        "end_time": i.end_time.isoformat() if i.end_time else None,
        "started_at": i.start_time.isoformat() if i.start_time else None,
        "resolved_at": i.end_time.isoformat() if i.end_time else None,
        "start_frame": i.start_frame,
        "end_frame": i.end_frame,
        "status": i.status,
        "severity": i.severity,
        "evidence_path": i.evidence_path,
        "metrics_snapshot": snap,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }
