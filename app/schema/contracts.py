"""Forge Canonical Architectural Contracts, Enums, and Schema Definitions.

SINGLE SOURCE OF TRUTH for:
- 7 Root-cause failure subsystem classifications (MVP Spec Section 2.3)
- P0–P4 Tiered storage and buffer priority classifications (MVP Spec Section 2.2-C)
- Evidence audit log action types (MVP Spec Section 3.5)
- Standardized nanosecond monotonic lifecycle timestamps (MVP Spec Section 2.2-D)
- Wire protocol schema versioning and payload structures (MVP Spec Section 4)

All agents, services, and tests MUST import and reference these canonical constants
to guarantee zero architectural drift across parallel PRs.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict

SCHEMA_VERSION: str = "1.0.0"


# ---------------------------------------------------------------------------
# 1. Root-Cause Failure Attribution Taxonomy (MVP Spec 2.3)
# ---------------------------------------------------------------------------


class FailureSubsystem(str, Enum):
    """Canonical classification for vision pipeline anomaly root causes."""

    # Optical & Environmental Failures
    CAMERA_DISCONNECT = "FAILURE_SUBSYSTEM_CAMERA"
    OPTICAL_DEFOCUS = "FAILURE_OPTICAL_DEFOCUS"
    OPTICAL_SENSOR_NOISE = "FAILURE_OPTICAL_SENSOR_NOISE"
    ENVIRONMENTAL_LIGHTING = "FAILURE_ENVIRONMENTAL_LIGHTING"

    # Compute, Model & Hardware Failures
    MODEL_INFERENCE_STALL = "FAILURE_MODEL_INFERENCE_STALL"
    HARDWARE_GPU_EXHAUSTION = "FAILURE_HARDWARE_GPU_EXHAUSTION"

    # Network & Transport Failures
    NETWORK_PARTITION = "FAILURE_NETWORK_PARTITION"

    @property
    def display_name(self) -> str:
        """Human-readable display name for dashboard presentation."""
        return {
            self.CAMERA_DISCONNECT: "Camera Disconnect / Loss of Signal",
            self.OPTICAL_DEFOCUS: "Optical Defocus / Vibration Blur",
            self.OPTICAL_SENSOR_NOISE: "Optical Sensor Noise / Dirty Lens",
            self.ENVIRONMENTAL_LIGHTING: "Environmental Lighting Dropout",
            self.MODEL_INFERENCE_STALL: "Inference Latency Stall / Drift",
            self.HARDWARE_GPU_EXHAUSTION: "Hardware / GPU Saturation",
            self.NETWORK_PARTITION: "Network Transport Partition",
        }.get(self, self.value)

    @property
    def is_physical_sensor(self) -> bool:
        """Whether failure is caused by physical sensor or environmental optics."""
        return self in (
            self.CAMERA_DISCONNECT,
            self.OPTICAL_DEFOCUS,
            self.OPTICAL_SENSOR_NOISE,
            self.ENVIRONMENTAL_LIGHTING,
        )


# ---------------------------------------------------------------------------
# 2. Bounded Storage Priority Classification (MVP Spec 2.2-C)
# ---------------------------------------------------------------------------


class PriorityTier(str, Enum):
    """Strict storage and transmission priority classes for EdgeBuffer."""

    P0_INCIDENT = "P0"       # Confirmed incident evidence (LOCKED: never evict)
    P1_ANOMALY = "P1"        # Unconfirmed anomalies (evict at 80% high-watermark)
    P2_DIAGNOSTIC = "P2"     # UI thumbnails and keyframes (rotating N=100)
    P3_METRIC = "P3"         # Numerical telemetry (downsample when disk is constrained)
    P4_VIDEO = "P4"          # Nominal inspection video (ephemeral RAM ring only)


# ---------------------------------------------------------------------------
# 3. Privacy & Tamper-Evident Audit Logging (MVP Spec 3.5)
# ---------------------------------------------------------------------------


class AuditAction(str, Enum):
    """Actions recorded in immutable audit log when incident evidence is accessed."""

    VIEW = "VIEW"            # Operator opened incident detail modal / evidence image
    DOWNLOAD = "DOWNLOAD"    # Operator exported snapshot / evidence archive
    RESOLVE = "RESOLVE"      # Operator marked incident as resolved
    EXPORT = "EXPORT"        # System or operator bulk export of telemetry/dossier


# ---------------------------------------------------------------------------
# 4. Standardized Lifecycle Timestamp Contracts (MVP Spec 2.2-D)
# ---------------------------------------------------------------------------


class LifecycleTimestamps(TypedDict, total=False):
    """Monotonic nanosecond timestamp array tracking an inspection frame lifecycle.
    
    All stages use time.monotonic_ns() to decouple stage duration analysis
    from system wall-clock skew or NTP synchronization jumps.
    """

    captured_at_ns: int              # Monotonic time when frame was grabbed from sensor
    inference_started_at_ns: int     # Monotonic time when tensor dispatched to model
    inference_completed_at_ns: int   # Monotonic time when defect detections computed
    queued_at_ns: int                # Monotonic time when payload entered local buffer
    transmitted_at_ns: int           # Monotonic time when batch HTTP POST started
    received_at_ns: int              # Monotonic time when backend /api/edge/sync received batch
    persisted_at_ns: int             # Monotonic time when backend DB transaction committed


# ---------------------------------------------------------------------------
# 5. Schema v1.0.0 Payload Sub-Contracts (MVP Spec 4.1)
# ---------------------------------------------------------------------------


class OpticalQualityPayload(TypedDict, total=False):
    """Optical quality metrics computed before or during inference."""

    blur_score: float                # Laplacian variance
    noise_score: float               # High-frequency noise variance
    brightness: float                # Mean frame luminance (0.0–255.0)


class PrivacyPayload(TypedDict, total=False):
    """Worker PII redaction certification attached to each synced frame."""

    pii_redacted: bool               # True if pre-persistence redaction filter executed
    redaction_method: str            # e.g., "in_memory_gaussian_roi", "none"


class EdgeBufferStatsPayload(TypedDict, total=False):
    """Buffer queue and storage capacity telemetry reported by the edge node."""

    queue_size: int
    capacity: int
    total_synced: int
    total_dropped: int
    storage_used_bytes: int
    storage_max_bytes: int
