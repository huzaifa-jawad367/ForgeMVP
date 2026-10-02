"""Incident trigger rules for Forge.

Defines the incident taxonomy and threshold-based evaluation logic that
determines when operational anomalies should be escalated to incidents.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List


class IncidentType(str, Enum):
    """Enumeration of all recognised incident categories."""

    CONFIDENCE_COLLAPSE = "confidence_collapse"
    BLUR_SPIKE = "blur_spike"
    LOW_FPS = "low_fps"
    CAMERA_OFFLINE = "camera_offline"
    HIGH_TEMPERATURE = "high_temperature"


@dataclass
class TriggerConfig:
    """Configurable thresholds for each incident trigger.

    Attributes:
        confidence_collapse_ratio: Fraction of baseline confidence below
            which a confidence collapse is flagged (e.g. 0.7 means trigger
            when mean_confidence < 0.7 * baseline_confidence).
        blur_threshold: Laplacian-variance score below which a frame is
            considered too blurry.
        min_fps: Minimum acceptable frames-per-second before LOW_FPS fires.
        offline_timeout_s: Seconds of silence before declaring a camera
            offline.
        max_gpu_temp: Maximum GPU temperature (°C) before HIGH_TEMPERATURE.
        baseline_confidence: Expected steady-state mean confidence used as
            the reference point for collapse detection.
    """

    confidence_collapse_ratio: float = 0.7
    blur_threshold: float = 50.0
    min_fps: float = 10.0
    offline_timeout_s: float = 5.0
    max_gpu_temp: float = 85.0
    baseline_confidence: float = 0.75


def evaluate_triggers(
    metrics: dict,
    config: TriggerConfig,
) -> List[IncidentType]:
    """Evaluate all trigger rules against the supplied metrics.

    Args:
        metrics: Dictionary with the following expected keys:
            - ``mean_confidence`` (float): Average detection confidence for
              the current frame.
            - ``blur_score`` (float): Laplacian variance of the frame.
            - ``current_fps`` (float): Measured throughput in FPS.
            - ``seconds_since_last_frame`` (float): Elapsed time since the
              previous frame was received.
            - ``gpu_temperature`` (float | None): Current GPU temp in °C,
              or *None* when unavailable.
        config: Threshold configuration to evaluate against.

    Returns:
        A list of :class:`IncidentType` values whose conditions are met.
    """

    triggered: List[IncidentType] = []

    # --- Confidence collapse ---
    mean_conf = metrics.get("mean_confidence")
    if mean_conf is not None:
        threshold = config.confidence_collapse_ratio * config.baseline_confidence
        if mean_conf < threshold:
            triggered.append(IncidentType.CONFIDENCE_COLLAPSE)

    # --- Blur spike (low Laplacian variance → blurry) ---
    blur_score = metrics.get("blur_score")
    if blur_score is not None and blur_score < config.blur_threshold:
        triggered.append(IncidentType.BLUR_SPIKE)

    # --- Low FPS ---
    current_fps = metrics.get("current_fps")
    if current_fps is not None and current_fps < config.min_fps:
        triggered.append(IncidentType.LOW_FPS)

    # --- Camera offline ---
    seconds_since = metrics.get("seconds_since_last_frame")
    if seconds_since is not None and seconds_since > config.offline_timeout_s:
        triggered.append(IncidentType.CAMERA_OFFLINE)

    # --- High GPU temperature ---
    gpu_temp = metrics.get("gpu_temperature")
    if gpu_temp is not None and gpu_temp > config.max_gpu_temp:
        triggered.append(IncidentType.HIGH_TEMPERATURE)

    return triggered
