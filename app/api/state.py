"""Shared mutable application state for Forge.

These module-level dictionaries are the single source of truth for
runtime state that must be visible to both the API layer and the
processing pipeline.  They are intentionally plain dicts so that they
can be read/written from any thread without import-time side effects.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Degradation controls (set via the demo API, consumed by the pipeline)
# ---------------------------------------------------------------------------
DEGRADATION_STATE: Dict[str, float] = {
    "blur": 0.0,        # 0.0 = no blur, 1.0 = max blur
    "brightness": 0.0,  # 0.0 = normal, 1.0 = fully dark
    "noise": 0.0,       # 0.0 = clean, 1.0 = heavy sensor noise
    "confidence": 0.0,  # 0.0 = normal, 1.0 = drop to zero
    "latency": 0.0,     # extra milliseconds to inject
}

# ---------------------------------------------------------------------------
# Pipeline telemetry (written by the pipeline, read by the status API)
# ---------------------------------------------------------------------------
PIPELINE_STATE: Dict[str, Any] = {
    "is_running": False,
    "source": None,
    "frames_processed": 0,
    "incidents_total": 0,
    "start_time": None,
}

# ---------------------------------------------------------------------------
# Edge service telemetry (reported by edge nodes via /api/edge/sync)
# ---------------------------------------------------------------------------
EDGE_STATE: Dict[str, Any] = {
    "is_connected": False,
    "edge_id": None,
    "source_id": None,
    "last_seen": None,
    "last_seen_seconds_ago": None,
    "queue_size": 0,
    "total_synced": 0,
    "total_dropped": 0,
    "fps": 0.0,
    "latency_ms": 0.0,
}
