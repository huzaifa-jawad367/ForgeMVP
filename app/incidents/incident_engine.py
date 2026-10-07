"""Incident lifecycle engine for Forge.

Orchestrates trigger evaluation, incident creation, evidence capture,
and resolution across successive frames.  This is the central state
machine that turns raw per-frame metrics into actionable incidents.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.incidents.evidence_manager import EvidenceManager
from app.incidents.trigger_rules import (
    IncidentType,
    TriggerConfig,
    evaluate_triggers,
    attribute_root_cause,
)

logger = logging.getLogger(__name__)

# Maps incident types to a severity level.
_SEVERITY: Dict[IncidentType, str] = {
    IncidentType.CONFIDENCE_COLLAPSE: "critical",
    IncidentType.BLUR_SPIKE: "warning",
    IncidentType.LOW_FPS: "warning",
    IncidentType.CAMERA_OFFLINE: "critical",
    IncidentType.HIGH_TEMPERATURE: "critical",
}


class IncidentEngine:
    """Per-source incident state machine.

    Tracks which incidents are currently *active* and which have been
    *resolved*.  Each call to :meth:`process_frame` advances the state
    by one frame tick.

    Args:
        config: Trigger thresholds to use for evaluation.
        evidence_manager: Shared evidence ring-buffer manager.
    """

    def __init__(
        self,
        config: TriggerConfig,
        evidence_manager: EvidenceManager,
    ) -> None:
        self._config = config
        self._evidence = evidence_manager

        # Keyed by IncidentType → incident record dict.
        self.active_incidents: Dict[IncidentType, Dict[str, Any]] = {}

        # Flat archive of every incident (active + resolved).
        self._all_incidents: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def process_frame(
        self,
        frame_data: Any,
        inference_result: Any,
        frame_metrics: Dict[str, Any],
        system_metrics: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Evaluate triggers and advance incident state for one frame.

        Args:
            frame_data: A ``FrameData`` instance from the ingestion layer.
            inference_result: An ``InferenceResult`` from the model wrapper.
            frame_metrics: Per-frame quality/detection metrics dict.
            system_metrics: Hardware telemetry dict (CPU, GPU, etc.).

        Returns:
            A list of *newly created* incident dicts for this frame (may
            be empty).
        """
        # 1. Build the combined metrics dict expected by evaluate_triggers.
        # Include all necessary metrics from frame_metrics, system_metrics, and inference_result
        # for root cause attribution heuristics.
        fps = frame_metrics.get("current_fps", frame_metrics.get("fps", 0.0))
        combined: Dict[str, Any] = {
            "mean_confidence": frame_metrics.get("mean_confidence"),
            "blur_score": frame_metrics.get("blur_score"),
            "current_fps": fps,
            "fps": fps,
            "seconds_since_last_frame": frame_metrics.get("seconds_since_last_frame"),
            "gpu_temperature": system_metrics.get("gpu_temperature"),
            "noise_score": frame_metrics.get("noise_score"),
            "brightness": frame_metrics.get("brightness"),
            "cpu_percent": system_metrics.get("cpu_percent"),
            "gpu_utilization": system_metrics.get("gpu_utilization"),
            "ack_age": frame_metrics.get("ack_age"),
            "pipeline_active": frame_metrics.get("pipeline_active", True),
        }
        if inference_result:
            if hasattr(inference_result, 'anomaly_score'):
                combined["anomaly_score"] = inference_result.anomaly_score
            elif isinstance(inference_result, dict):
                combined["anomaly_score"] = inference_result.get("anomaly_score", 0.0)

            if hasattr(inference_result, 'inference_time_ms'):
                combined["inference_time_ms"] = inference_result.inference_time_ms
            elif isinstance(inference_result, dict):
                combined["inference_time_ms"] = inference_result.get("inference_time_ms", 0.0)

        # 2. Evaluate which trigger types fire on this frame.
        triggered_types = set(evaluate_triggers(combined, self._config))

        new_incidents: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        # 3. Open new incidents for freshly triggered types.
        for itype in triggered_types:
            if itype not in self.active_incidents:
                incident_id = str(uuid4())
                frame_index = getattr(frame_data, "frame_index", 0)

                # Capture evidence (pre-frame + incident frame + metrics).
                evidence_result = self._evidence.capture_evidence(
                    incident_id=incident_id,
                    incident_frame_index=frame_index,
                    metrics_snapshot={**combined, **system_metrics},
                )

                record: Dict[str, Any] = {
                    "id": incident_id,
                    "incident_type": itype.value,
                    "source_id": getattr(frame_data, "source_id", None),
                    "start_time": now.isoformat(),
                    "end_time": None,
                    "start_frame": frame_index,
                    "end_frame": None,
                    "status": "active",
                    "severity": _SEVERITY.get(itype, "warning"),
                    "evidence_path": evidence_result.get("evidence_dir"),
                    "metrics_snapshot": {**combined, **system_metrics},
                }

                # Evaluate root cause attribution
                attribution_result = attribute_root_cause({**combined, **system_metrics}, self._config)
                if attribution_result:
                    subsystem, reason = attribution_result
                    record["subsystem_attribution"] = subsystem.value
                    record["root_cause_reason"] = reason
                else:
                    record["subsystem_attribution"] = None
                    record["root_cause_reason"] = None

                self.active_incidents[itype] = record
                self._all_incidents.append(record)
                new_incidents.append(record)

                logger.warning(
                    "Incident OPENED: %s [%s] severity=%s frame=%d",
                    itype.value,
                    incident_id,
                    record["severity"],
                    frame_index,
                )

        # 4. Resolve incidents whose triggers are no longer firing.
        resolved_types = [
            itype
            for itype in list(self.active_incidents)
            if itype not in triggered_types
        ]
        for itype in resolved_types:
            record = self.active_incidents.pop(itype)
            record["status"] = "resolved"
            record["end_time"] = now.isoformat()
            record["end_frame"] = getattr(frame_data, "frame_index", None)

            logger.info(
                "Incident RESOLVED: %s [%s]",
                itype.value,
                record["id"],
            )

        return new_incidents

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_active_incidents(self) -> List[Dict[str, Any]]:
        """Return a snapshot of all currently active incidents."""
        return list(self.active_incidents.values())

    def get_all_incidents(self) -> List[Dict[str, Any]]:
        """Return every incident ever recorded (active + resolved)."""
        return list(self._all_incidents)
