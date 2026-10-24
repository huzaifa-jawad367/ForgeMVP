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
    IncidentType.SENSOR_NOISE: "warning",
    IncidentType.LIGHTING_DROP: "warning",
    IncidentType.LOW_FPS: "warning",
    IncidentType.CAMERA_OFFLINE: "critical",
    IncidentType.HIGH_TEMPERATURE: "critical",
}


class IncidentEngine:
    """Per-source incident state machine with debouncing, hysteresis and delta tracking.

    Tracks which incidents are currently *active* and which have been
    *resolved*. Manages continuous telemetry attachment, delta threshold
    events, and hysteresis-based resolution to eliminate alert flooding.

    Args:
        config: Trigger thresholds to use for evaluation.
        evidence_manager: Shared evidence ring-buffer manager.
        recovery_threshold_frames: Number of consecutive clean frames
            required before resolving an active incident.
        delta_threshold_pct: Percentage point shift in degradation severity
            required to emit a severity delta event (default: 10%).
    """

    def __init__(
        self,
        config: TriggerConfig,
        evidence_manager: EvidenceManager,
        recovery_threshold_frames: int = 3,
        delta_threshold_pct: float = 10.0,
    ) -> None:
        self._config = config
        self._evidence = evidence_manager
        self._recovery_threshold = recovery_threshold_frames
        self._delta_threshold_pct = delta_threshold_pct

        # Keyed by IncidentType → incident record dict.
        self.active_incidents: Dict[IncidentType, Dict[str, Any]] = {}

        # Debounce: consecutive clean/normal frames per IncidentType
        self._consecutive_normal: Dict[IncidentType, int] = {}

        # Last reported metric value per IncidentType for delta detection
        self._last_metric_val: Dict[IncidentType, float] = {}

        # Flat archive of every incident (active + resolved).
        self._all_incidents: List[Dict[str, Any]] = []

    def _get_primary_metric(self, itype: IncidentType, metrics: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        """Return (current_metric_value, scale_denominator) for percentage delta calculation."""
        if itype == IncidentType.BLUR_SPIKE:
            return metrics.get("blur_score"), self._config.blur_threshold
        elif itype == IncidentType.SENSOR_NOISE:
            return metrics.get("noise_score"), self._config.noise_threshold
        elif itype == IncidentType.LIGHTING_DROP:
            return metrics.get("brightness"), self._config.min_brightness
        elif itype == IncidentType.CONFIDENCE_COLLAPSE:
            return metrics.get("mean_confidence"), self._config.baseline_confidence
        elif itype == IncidentType.LOW_FPS:
            return metrics.get("current_fps"), self._config.min_fps
        return None, None

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
            A list of incident event dicts (newly opened, severity delta,
            or cleared) for this frame.
        """
        # 1. Build the combined metrics dict expected by evaluate_triggers.
        fps = frame_metrics.get("current_fps", frame_metrics.get("fps", 0.0))
        combined: Dict[str, Any] = {
            "mean_confidence": frame_metrics.get("mean_confidence"),
            "num_detections": frame_metrics.get("num_detections", 0),
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

        incident_events: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        frame_index = getattr(frame_data, "frame_index", 0)

        # 3. Handle active & new incidents for triggered types
        for itype in triggered_types:
            # Active condition is firing: reset normal recovery counter
            self._consecutive_normal[itype] = 0
            curr_val, scale = self._get_primary_metric(itype, combined)

            if itype not in self.active_incidents:
                # OPEN NEW INCIDENT (Single initial event)
                incident_id = str(uuid4())

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
                    "end_frame": frame_index,
                    "status": "active",
                    "severity": _SEVERITY.get(itype, "warning"),
                    "evidence_path": evidence_result.get("evidence_dir"),
                    "metrics_snapshot": {**combined, **system_metrics},
                    "events": [
                        {
                            "event_type": "opened",
                            "timestamp": now.isoformat(),
                            "frame_index": frame_index,
                            "metric_value": curr_val,
                        }
                    ],
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
                self._last_metric_val[itype] = curr_val if curr_val is not None else 0.0
                self._all_incidents.append(record)
                incident_events.append(record)

                logger.warning(
                    "Incident OPENED: %s [%s] severity=%s frame=%d",
                    itype.value,
                    incident_id,
                    record["severity"],
                    frame_index,
                )

            else:
                # ALREADY ACTIVE: Maintain ONE continuous incident.
                # Update continuous telemetry without duplicating incident records.
                record = self.active_incidents[itype]
                record["end_frame"] = frame_index
                record["metrics_snapshot"] = {**combined, **system_metrics}

                # Check for significant delta (>= 10 percentage points shift)
                if curr_val is not None and scale and scale > 0:
                    last_val = self._last_metric_val.get(itype, curr_val)
                    delta_pct = (abs(curr_val - last_val) / scale) * 100.0
                    if delta_pct >= self._delta_threshold_pct:
                        delta_direction = "increased" if curr_val > last_val else "decreased"
                        delta_event = {
                            "event_type": "severity_delta",
                            "timestamp": now.isoformat(),
                            "frame_index": frame_index,
                            "previous_value": last_val,
                            "current_value": curr_val,
                            "delta_pct": round(delta_pct, 1),
                            "direction": delta_direction,
                            "description": f"{itype.value} {delta_direction} by {delta_pct:.1f}% ({last_val:.1f} -> {curr_val:.1f})",
                        }
                        if "events" not in record or not isinstance(record["events"], list):
                            record["events"] = []
                        record["events"].append(delta_event)
                        self._last_metric_val[itype] = curr_val

                        logger.info(
                            "Incident DELTA: %s [%s] %s",
                            itype.value,
                            record["id"],
                            delta_event["description"],
                        )
                        incident_events.append(record)

        # 4. Debounced resolution with hysteresis (require sustained recovery)
        resolved_types: List[IncidentType] = []
        for itype in list(self.active_incidents):
            if itype not in triggered_types:
                self._consecutive_normal[itype] = self._consecutive_normal.get(itype, 0) + 1
                if self._consecutive_normal[itype] >= self._recovery_threshold:
                    # Sustained recovery reached: emit cleared event
                    resolved_types.append(itype)

        for itype in resolved_types:
            record = self.active_incidents.pop(itype)
            self._consecutive_normal.pop(itype, None)
            self._last_metric_val.pop(itype, None)
            record["status"] = "resolved"
            record["end_time"] = now.isoformat()
            record["end_frame"] = frame_index
            if "events" not in record or not isinstance(record["events"], list):
                record["events"] = []
            record["events"].append({
                "event_type": "cleared",
                "timestamp": now.isoformat(),
                "frame_index": frame_index,
                "description": f"{itype.value} cleared on camera (stable for {self._recovery_threshold} frames)",
            })
            incident_events.append(record)

            logger.info(
                "Incident CLEARED: %s [%s] frame=%d",
                itype.value,
                record["id"],
                frame_index,
            )

        return incident_events

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_active_incidents(self) -> List[Dict[str, Any]]:
        """Return a snapshot of all currently active incidents."""
        return list(self.active_incidents.values())

    def get_all_incidents(self) -> List[Dict[str, Any]]:
        """Return every incident ever recorded (active + resolved)."""
        return list(self._all_incidents)
