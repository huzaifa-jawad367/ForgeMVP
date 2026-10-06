"""Incident trigger rules for Forge.

Defines the incident taxonomy and threshold-based evaluation logic that
determines when operational anomalies should be escalated to incidents.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from app.schema.contracts import FailureSubsystem


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
    noise_threshold: float = 1.0
    min_brightness: float = 50.0
    baseline_inference_time_ms: float = 20.0
    max_gpu_utilization: float = 98.0
    max_ack_age: float = 10.0


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


def attribute_root_cause(
    metrics: dict,
    config: TriggerConfig,
) -> Optional[Tuple[FailureSubsystem, str]]:
    """Attribute detected anomalies to one of the 7 failure subsystems.

    Args:
        metrics: Combined dictionary of frame metrics, system metrics, and inference results.
        config: Threshold configuration to evaluate against.

    Returns:
        A tuple of (FailureSubsystem, str) if a root cause is detected, otherwise None.
    """
    fps = metrics.get("fps", metrics.get("current_fps"))
    pipeline_active = metrics.get("pipeline_active", True)

    # 1. CAMERA_DISCONNECT: fps == 0 for > 3.0s while pipeline is active.
    seconds_since = metrics.get("seconds_since_last_frame")
    if (fps == 0 or (seconds_since is not None and seconds_since > 3.0)) and pipeline_active:
        return (FailureSubsystem.CAMERA_DISCONNECT, "Camera disconnected or no frames received for > 3.0s")

    anomaly_score = metrics.get("anomaly_score", 0.0)

    # 2. OPTICAL_DEFOCUS: Anomaly score > 0.50 correlated with blur_score < blur_threshold (defocus blur collapse).
    blur_score = metrics.get("blur_score")
    if anomaly_score > 0.50 and blur_score is not None and blur_score < config.blur_threshold:
        return (FailureSubsystem.OPTICAL_DEFOCUS, f"Defocus blur collapse detected (blur_score {blur_score:.2f} < {config.blur_threshold})")

    # 3. OPTICAL_SENSOR_NOISE: Anomaly score > 0.50 correlated with noise_score > noise_threshold.
    noise_score = metrics.get("noise_score")
    if anomaly_score > 0.50 and noise_score is not None and noise_score > config.noise_threshold:
        return (FailureSubsystem.OPTICAL_SENSOR_NOISE, f"Sensor noise detected (noise_score {noise_score:.2f} > {config.noise_threshold})")

    # 4. ENVIRONMENTAL_LIGHTING: brightness < min_brightness (lighting drop).
    brightness = metrics.get("brightness")
    if brightness is not None and brightness < config.min_brightness:
        return (FailureSubsystem.ENVIRONMENTAL_LIGHTING, f"Lighting drop detected (brightness {brightness:.2f} < {config.min_brightness})")

    # 5. MODEL_INFERENCE_STALL: inference_time_ms > 3x baseline while CPU/GPU load is normal (< 70%).
    inference_time_ms = metrics.get("inference_time_ms")
    cpu_percent = metrics.get("cpu_percent", 0.0)
    gpu_util = metrics.get("gpu_utilization", 0.0)
    if (inference_time_ms is not None
        and inference_time_ms > 3 * config.baseline_inference_time_ms
        and cpu_percent < 70.0
        and gpu_util < 70.0):
        return (FailureSubsystem.MODEL_INFERENCE_STALL, f"Inference stall detected ({inference_time_ms:.2f}ms > 3x baseline)")

    # 6. HARDWARE_GPU_EXHAUSTION: GPU utilization sustained >= 98% or gpu_temperature >= 85°C.
    gpu_temp = metrics.get("gpu_temperature")
    if (gpu_util >= config.max_gpu_utilization) or (gpu_temp is not None and gpu_temp >= 85.0):
        return (FailureSubsystem.HARDWARE_GPU_EXHAUSTION, f"GPU exhaustion detected (util: {gpu_util}%, temp: {gpu_temp}°C)")

    # 7. NETWORK_PARTITION: Edge queue growing continuously with ack_age > 10.0s.
    ack_age = metrics.get("ack_age")
    if ack_age is not None and ack_age > config.max_ack_age:
        return (FailureSubsystem.NETWORK_PARTITION, f"Network partition detected (ack_age {ack_age:.2f}s > {config.max_ack_age}s)")

    return None
