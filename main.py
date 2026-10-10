"""Forge – main entry-point.

Boots the FastAPI application, initialises the database, and optionally
starts a real-time computer-vision pipeline in a background thread.

Usage::

    python main.py --input video.mp4 --port 8000
    python main.py --input 0          # webcam
    python main.py                     # API-only, start pipeline later via POST
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import base64
import psutil
import uvicorn
from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    EdgeSyncBatch,
    PipelineStartInput,
    register_edge_sync_processor,
    router,
)
from app.api.state import DEGRADATION_STATE, EDGE_STATE, PIPELINE_STATE
from app.incidents.evidence_manager import EvidenceManager
from app.incidents.incident_engine import IncidentEngine
from app.incidents.trigger_rules import TriggerConfig
from app.inference.efficientad_runner import EfficientADRunner
from app.inference.model_wrapper import Detection
from app.ingestion.dataset_stream_loader import (
    VisaDatasetStreamLoader,
    find_visa_root,
)
from app.storage.maintenance import MaintenanceWorker
from app.storage.database import (
    get_session,
    init_db,
    store_frame_metric,
    store_incident,
    store_system_metric,
)
from app.telemetry import telemetry_manager, websocket_exporter, websocket_manager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("forge")

# ---------------------------------------------------------------------------
# GPU helpers (best-effort; silently degrade when no NVIDIA GPU is present)
# ---------------------------------------------------------------------------


def _get_gpu_stats() -> Dict[str, Optional[float]]:
    """Return GPU utilisation, memory %, and temperature.

    Falls back to ``None`` values when *pynvml* is unavailable or no
    NVIDIA GPU is detected.
    """
    try:
        import pynvml  # type: ignore[import-untyped]

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        pynvml.nvmlShutdown()
        return {
            "gpu_utilization": float(util.gpu),
            "gpu_memory_percent": float(mem.used / mem.total * 100) if mem.total else 0.0,
            "gpu_temperature": float(temp),
        }
    except Exception:
        return {
            "gpu_utilization": None,
            "gpu_memory_percent": None,
            "gpu_temperature": None,
        }


# ---------------------------------------------------------------------------
# Frame-level metric computation
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Global frame buffer for real-time live streaming
# ---------------------------------------------------------------------------

LATEST_FRAME_JPEG: Optional[bytes] = None
LATEST_FRAME_LOCK = threading.Lock()


def _update_live_stream_frame(
    *,
    frame: np.ndarray,
    detections: list,
    fps: float,
    inference_time_ms: float,
    frame_index: int,
) -> None:
    """Render bounding boxes, defect heatmaps, and HUD diagnostics into a JPEG for live streaming."""
    global LATEST_FRAME_JPEG
    annotated = frame.copy()
    h, w = annotated.shape[:2]

    # Draw detections (red for anomaly/defect, green for normal)
    has_anomaly = False
    for det in detections:
        is_anom = "defect" in det.class_name.lower() or "anomaly" in det.class_name.lower()
        if is_anom:
            has_anomaly = True
        color = (0, 0, 255) if is_anom else (0, 255, 0)
        bx1, by1, bx2, by2 = [int(v) for v in det.bbox]
        cv2.rectangle(annotated, (bx1, by1), (bx2, by2), color, 2)
        label = f"{det.class_name.upper()} {det.confidence:.2f}"
        cv2.putText(
            annotated,
            label,
            (bx1, max(22, by1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )

    # Top HUD banner
    banner_color = (0, 0, 160) if has_anomaly else (15, 15, 25)
    cv2.rectangle(annotated, (0, 0), (w, 36), banner_color, -1)
    status_tag = "● DEFECT DETECTED" if has_anomaly else "● INSPECTION OK"
    status_col = (0, 0, 255) if has_anomaly else (0, 255, 120)

    hud_str = f"FRAME #{frame_index:04d} | {fps:.1f} FPS | LAT: {inference_time_ms:.1f}ms"
    noise_val = DEGRADATION_STATE.get("noise", 0.0)
    blur_val = DEGRADATION_STATE.get("blur", 0.0)
    if noise_val > 0:
        hud_str += f" | NOISE: {noise_val * 100:.0f}%"
    if blur_val > 0:
        hud_str += f" | BLUR: {blur_val * 100:.0f}%"

    cv2.putText(annotated, status_tag, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_col, 2, cv2.LINE_AA)
    cv2.putText(annotated, hud_str, (240, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 240, 255), 1, cv2.LINE_AA)

    ret, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if ret:
        with LATEST_FRAME_LOCK:
            LATEST_FRAME_JPEG = encoded.tobytes()


# ---------------------------------------------------------------------------
# Frame-level metric computation
# ---------------------------------------------------------------------------


def _compute_frame_metrics(
    frame: np.ndarray,
    detections: list,
    inference_time_ms: float,
    fps: float,
) -> Dict[str, Any]:
    """Derive quality, sensor noise, and detection metrics from a single frame."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    brightness = float(np.mean(gray))
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # High-frequency residual standard deviation as a robust image noise estimate
    blurred_gray = cv2.GaussianBlur(gray, (5, 5), 0)
    noise_std = float(np.std(cv2.absdiff(gray, blurred_gray)))
    noise_level = float(DEGRADATION_STATE.get("noise", 0.0) * 100.0)

    confidences = [d.confidence for d in detections] if detections else []
    mean_conf = float(np.mean(confidences)) if confidences else 0.0
    min_conf = float(np.min(confidences)) if confidences else 0.0

    has_anomaly = any(
        "defect" in d.class_name.lower() or "anomaly" in d.class_name.lower()
        for d in detections
    )

    return {
        "fps": fps,
        "inference_time_ms": inference_time_ms,
        "mean_confidence": mean_conf,
        "min_confidence": min_conf,
        "num_detections": len(detections),
        "brightness": brightness,
        "blur_score": blur_score,
        "noise_level": noise_level,
        "noise_score": noise_std,
        "has_anomaly": has_anomaly,
    }


# ---------------------------------------------------------------------------
# Degradation helpers (applied BEFORE inference for physical noise/blur)
# ---------------------------------------------------------------------------


def _apply_frame_degradation(frame: np.ndarray) -> np.ndarray:
    """Mutate frame with sensor noise, blur, and lighting drops BEFORE inference."""
    blur_level = DEGRADATION_STATE.get("blur", 0.0)
    brightness_drop = DEGRADATION_STATE.get("brightness", 0.0)
    noise_level = DEGRADATION_STATE.get("noise", 0.0)
    extra_latency = DEGRADATION_STATE.get("latency", 0.0)

    # 1. Sensor Gaussian Noise injection
    if noise_level > 0:
        sigma = float(noise_level * 55.0)
        gauss = np.random.normal(0, sigma, frame.shape).astype(np.float32)
        frame = np.clip(frame.astype(np.float32) + gauss, 0, 255).astype(np.uint8)

    # 2. Defocus Blur
    if blur_level > 0:
        ksize = int(blur_level * 51) | 1  # ensure odd
        ksize = max(ksize, 3)
        frame = cv2.GaussianBlur(frame, (ksize, ksize), 0)

    # 3. Brightness drop
    if brightness_drop > 0:
        factor = 1.0 - brightness_drop
        frame = np.clip(frame.astype(np.float32) * factor, 0, 255).astype(np.uint8)

    # 4. Latency injection
    if extra_latency > 0:
        time.sleep(extra_latency / 1000.0)

    return frame


def _apply_confidence_degradation(detections: list) -> list:
    """Scale down detection confidences if post-inference confidence degradation is active."""
    conf_drop = DEGRADATION_STATE.get("confidence", 0.0)
    if conf_drop > 0:
        for det in detections:
            det.confidence *= (1.0 - conf_drop)
    return detections


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

# Sentinel used to signal shutdown.
_shutdown_event = threading.Event()


def _run_pipeline_blocking(
    source_input: str,
    target_fps: float = 10.0,
    loop: bool = True,
    model_name: Optional[str] = None,
) -> None:  # noqa: C901 (complexity)
    """Blocking pipeline loop – meant to run in a daemon thread.

    Handles four input types:
    * **visa:<category>** – continuous conveyor-belt stream of VisA anomaly images
    * **file** – a local video file
    * **webcam** – an integer index (e.g. ``"0"``)
    * **stream** – an RTSP / HTTP URL
    * **directory** – a folder of image files
    """
    logger.info(
        "Pipeline starting with source: %s (fps=%.1f, loop=%s, model=%s)",
        source_input,
        target_fps,
        loop,
        model_name,
    )

    # -- Determine input type --------------------------------------------------
    is_visa = source_input.lower().startswith("visa")
    is_directory = os.path.isdir(source_input) if not is_visa else False
    is_webcam = source_input.isdigit() if not is_visa else False
    is_file = os.path.isfile(source_input) if not is_visa else False

    # -- Model selection ------------------------------------------------------
    model: Any = None
    if is_visa or model_name == "efficientad":
        cat = "pcb1"
        if ":" in source_input:
            cat = source_input.split(":", 1)[1].strip()
        try:
            logger.info("Initializing EfficientADRunner for VisA category '%s'...", cat)
            model = EfficientADRunner(category=cat)
        except Exception:
            logger.exception("Failed to initialize EfficientADRunner, falling back to default model.")

    if model is None:
        try:
            from app.inference.model_wrapper import get_inference_model  # type: ignore[import]
            model = get_inference_model()
        except Exception:
            logger.warning(
                "Inference model not available – pipeline will run without detections."
            )
            model = None

    # -- Initialise incident subsystem ----------------------------------------
    config = TriggerConfig()
    evidence_mgr = EvidenceManager(buffer_size=30, pre_incident_offset=5)
    incident_engine = IncidentEngine(config=config, evidence_manager=evidence_mgr)

    # -- Update shared state --------------------------------------------------
    PIPELINE_STATE["is_running"] = True
    PIPELINE_STATE["source"] = source_input
    PIPELINE_STATE["frames_processed"] = 0
    PIPELINE_STATE["incidents_total"] = 0
    PIPELINE_STATE["start_time"] = datetime.now(timezone.utc).isoformat()

    frame_counter = 0
    last_frame_time = time.time()

    try:
        if is_visa:
            cat = "pcb1"
            if ":" in source_input:
                cat = source_input.split(":", 1)[1].strip()
            loader = VisaDatasetStreamLoader(category=cat, target_fps=target_fps, loop=loop)
            try:
                for stream_frame in loader.stream():
                    if _shutdown_event.is_set():
                        break
                    _process_single_frame(
                        frame=stream_frame.frame,
                        frame_index=stream_frame.frame_index,
                        timestamp_ms=stream_frame.timestamp_ms,
                        fps=stream_frame.fps,
                        source_input=source_input,
                        model=model,
                        evidence_mgr=evidence_mgr,
                        incident_engine=incident_engine,
                    )
            finally:
                loader.stop()

        elif is_directory:
            _run_directory_pipeline(
                source_input, model, config, evidence_mgr, incident_engine, loop=loop
            )
        else:
            # Video file, webcam, or stream URL.
            cap_input: Any = int(source_input) if is_webcam else source_input
            cap = cv2.VideoCapture(cap_input)
            if not cap.isOpened():
                logger.error("Cannot open video source: %s", source_input)
                return

            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

            while not _shutdown_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    if is_file and loop:
                        logger.info("End of video reached, rewinding to beginning.")
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    elif is_file:
                        logger.info("End of video file reached.")
                        break
                    # For streams/webcams retry briefly.
                    time.sleep(0.1)
                    continue

                now = time.time()
                elapsed = now - last_frame_time
                measured_fps = 1.0 / elapsed if elapsed > 0 else fps
                last_frame_time = now
                timestamp_ms = cap.get(cv2.CAP_PROP_POS_MSEC)

                _process_single_frame(
                    frame=frame,
                    frame_index=frame_counter,
                    timestamp_ms=timestamp_ms,
                    fps=measured_fps,
                    source_input=source_input,
                    model=model,
                    evidence_mgr=evidence_mgr,
                    incident_engine=incident_engine,
                )
                frame_counter += 1

            cap.release()
    except Exception:
        logger.exception("Pipeline crashed")
    finally:
        PIPELINE_STATE["is_running"] = False
        logger.info(
            "Pipeline stopped after %d frames", PIPELINE_STATE["frames_processed"]
        )


def _run_directory_pipeline(
    directory: str,
    model: Any,
    config: TriggerConfig,
    evidence_mgr: EvidenceManager,
    incident_engine: IncidentEngine,
    loop: bool = True,
) -> None:
    """Process every image in *directory* sequentially, optionally looping."""
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    files = sorted(
        f
        for f in os.listdir(directory)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTS
    )
    if not files:
        logger.warning("No image files found in %s", directory)
        return

    frame_counter = 0
    while not _shutdown_event.is_set():
        for fname in files:
            if _shutdown_event.is_set():
                break
            fpath = os.path.join(directory, fname)
            frame = cv2.imread(fpath)
            if frame is None:
                continue

            _process_single_frame(
                frame=frame,
                frame_index=frame_counter,
                timestamp_ms=float(frame_counter * 33),  # synthetic ~30fps timing
                fps=30.0,
                source_input=directory,
                model=model,
                evidence_mgr=evidence_mgr,
                incident_engine=incident_engine,
            )
            frame_counter += 1
            time.sleep(0.033)
        if not loop:
            break


@dataclass
class _FakeFrameData:
    """Minimal stand-in for ``FrameData`` when the ingestion layer is
    not yet wired up."""

    frame: np.ndarray
    frame_index: int
    timestamp_ms: float
    source_id: str
    fps: float


@dataclass
class _FakeInferenceResult:
    """Minimal stand-in for ``InferenceResult``."""

    detections: list
    inference_time_ms: float
    model_name: str


def _process_single_frame(
    *,
    frame: np.ndarray,
    frame_index: int,
    timestamp_ms: float,
    fps: float,
    source_input: str,
    model: Any,
    evidence_mgr: EvidenceManager,
    incident_engine: IncidentEngine,
) -> None:
    """Run a single frame through degradation → inference → metrics → incidents → DB."""

    # 1. Physical sensor noise, blur, and lighting degradation BEFORE inference!
    frame = _apply_frame_degradation(frame)

    # 2. Run inference on degraded frame
    if model is not None:
        try:
            inference_result = model.predict(frame)
            detections = inference_result.detections
            inference_time_ms = inference_result.inference_time_ms
        except Exception:
            logger.debug("Inference failed on frame %d", frame_index, exc_info=True)
            detections = []
            inference_time_ms = 0.0
    else:
        detections = []
        inference_time_ms = 0.0

    # 3. Post-inference confidence degradation if configured
    detections = _apply_confidence_degradation(detections)

    # 4. Render overlay for live streaming buffer
    _update_live_stream_frame(
        frame=frame,
        detections=detections,
        fps=fps,
        inference_time_ms=inference_time_ms,
        frame_index=frame_index,
    )

    # 5. Compute frame-level metrics.
    frame_metrics = _compute_frame_metrics(frame, detections, inference_time_ms, fps)
    frame_metrics["current_fps"] = fps
    frame_metrics["seconds_since_last_frame"] = 1.0 / fps if fps > 0 else 0.0

    # 6. System metrics.
    system_metrics: Dict[str, Any] = {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent,
        **_get_gpu_stats(),
    }

    # 7. Push frame into evidence ring buffer.
    evidence_mgr.push_frame(frame, frame_index, timestamp_ms)

    # 8. Feed incident engine.
    frame_data = _FakeFrameData(
        frame=frame,
        frame_index=frame_index,
        timestamp_ms=timestamp_ms,
        source_id=source_input,
        fps=fps,
    )
    inf_result = _FakeInferenceResult(
        detections=detections,
        inference_time_ms=inference_time_ms,
        model_name=model.__class__.__name__ if model else "none",
    )
    new_incidents = incident_engine.process_frame(
        frame_data, inf_result, frame_metrics, system_metrics
    )

    # 9. Persist to database.
    try:
        with get_session() as session:
            store_frame_metric(session, {
                "source_id": 1,  # default source id
                "frame_index": frame_index,
                "timestamp_ms": timestamp_ms,
                "fps": fps,
                "inference_time_ms": inference_time_ms,
                "mean_confidence": frame_metrics["mean_confidence"],
                "min_confidence": frame_metrics["min_confidence"],
                "num_detections": frame_metrics["num_detections"],
                "brightness": frame_metrics["brightness"],
                "blur_score": frame_metrics["blur_score"],
                "noise_score": frame_metrics["noise_score"],
            })
            store_system_metric(session, system_metrics)

            stored_incidents = []
            for inc in new_incidents:
                stored = store_incident(session, inc)
                stored_incidents.append(stored)
    except Exception:
        logger.exception("Database write failed on frame %d", frame_index)
        stored_incidents = []

    # 10. Export telemetry.
    try:
        from app.api.routes import _incident_to_dict

        telemetry_manager.export_frame_metrics(source_input, {
            "id": frame_index,
            "source_id": 1,
            "frame_index": frame_index,
            "timestamp_ms": timestamp_ms,
            "fps": fps,
            "inference_time_ms": inference_time_ms,
            "mean_confidence": frame_metrics["mean_confidence"],
            "min_confidence": frame_metrics["min_confidence"],
            "num_detections": frame_metrics["num_detections"],
            "brightness": frame_metrics["brightness"],
            "blur_score": frame_metrics["blur_score"],
            "noise_level": frame_metrics["noise_level"],
            "noise_score": frame_metrics["noise_score"],
            "has_anomaly": frame_metrics["has_anomaly"],
        })

        telemetry_manager.export_system_metrics(system_metrics)

        for inc in stored_incidents:
            telemetry_manager.export_incident(_incident_to_dict(inc))
    except Exception:
        logger.exception("Telemetry export failed on frame %d", frame_index)

    # 11. Update pipeline state.
    PIPELINE_STATE["frames_processed"] = frame_index + 1
    PIPELINE_STATE["incidents_total"] += len(new_incidents)

    if frame_index % 25 == 0:
        logger.info(
            "Frame %d | fps=%.1f | detections=%d | conf=%.3f | noise=%.1f | blur=%.1f",
            frame_index,
            fps,
            frame_metrics["num_detections"],
            frame_metrics["mean_confidence"],
            frame_metrics["noise_level"],
            frame_metrics["blur_score"],
        )


# ---------------------------------------------------------------------------
# Edge Sync Ingestion Processor
# ---------------------------------------------------------------------------

_backend_evidence_mgr = EvidenceManager(buffer_size=30, pre_incident_offset=5)
_backend_incident_engine = IncidentEngine(config=TriggerConfig(), evidence_manager=_backend_evidence_mgr)


def process_edge_sync_batch(batch: EdgeSyncBatch) -> int:
    """Process a batch of inference frames synced from an edge device."""
    global LATEST_FRAME_JPEG

    # 1. Update live preview stream if edge sent a keyframe JPEG
    if batch.latest_frame_jpeg:
        try:
            raw_bytes = base64.b64decode(batch.latest_frame_jpeg)
            with LATEST_FRAME_LOCK:
                LATEST_FRAME_JPEG = raw_bytes
        except Exception as e:
            logger.debug("Failed to decode edge stream frame: %s", e)

    # 2. Update pipeline state to reflect active edge processing
    PIPELINE_STATE["is_running"] = True
    PIPELINE_STATE["source"] = f"{batch.source_id} (Edge: {batch.edge_id})"
    if not PIPELINE_STATE["start_time"]:
        PIPELINE_STATE["start_time"] = datetime.now(timezone.utc).isoformat()

    ingested_count = 0
    for frame in batch.frames:
        frame_index = frame.get("frame_index", 0)
        timestamp_ms = frame.get("timestamp_ms", 0.0)
        fps = frame.get("fps", 0.0)
        inference_time_ms = frame.get("inference_time_ms", 0.0)
        system_metrics = frame.get("system_metrics") or _get_gpu_stats()

        stored_incidents = []
        try:
            with get_session() as session:
                store_frame_metric(session, {
                    "source_id": 1,
                    "frame_index": frame_index,
                    "timestamp_ms": timestamp_ms,
                    "fps": fps,
                    "inference_time_ms": inference_time_ms,
                    "mean_confidence": frame.get("mean_confidence", 0.0),
                    "min_confidence": frame.get("min_confidence", 0.0),
                    "num_detections": frame.get("num_detections", 0),
                    "brightness": frame.get("brightness", 0.0),
                    "blur_score": frame.get("blur_score", 0.0),
                    "noise_score": frame.get("noise_score", 0.0),
                })
                if system_metrics:
                    store_system_metric(session, system_metrics)

                # Feed Incident Engine
                raw_dets = frame.get("detections", [])
                dets = [
                    Detection(
                        class_name=d["class_name"],
                        confidence=d["confidence"],
                        bbox=tuple(d["bbox"]),
                    )
                    for d in raw_dets
                ]
                frame_data = _FakeFrameData(
                    frame=np.zeros((1, 1, 3), dtype=np.uint8),
                    frame_index=frame_index,
                    timestamp_ms=timestamp_ms,
                    source_id=batch.source_id,
                    fps=fps,
                )
                inf_result = _FakeInferenceResult(
                    detections=dets,
                    inference_time_ms=inference_time_ms,
                    model_name=f"EfficientAD ({batch.edge_id})",
                )
                new_incidents = _backend_incident_engine.process_frame(
                    frame_data, inf_result, frame, system_metrics
                )
                for inc in new_incidents:
                    stored = store_incident(session, inc)
                    stored_incidents.append(stored)

        except Exception as e:
            logger.debug("Database write for edge frame %d: %s", frame_index, e)

        # Telemetry export to frontend WebSocket
        try:
            from app.api.routes import _incident_to_dict

            telemetry_manager.export_frame_metrics(batch.source_id, {
                "id": frame_index,
                "source_id": 1,
                "frame_index": frame_index,
                "timestamp_ms": timestamp_ms,
                "fps": fps,
                "inference_time_ms": inference_time_ms,
                "mean_confidence": frame.get("mean_confidence", 0.0),
                "min_confidence": frame.get("min_confidence", 0.0),
                "num_detections": frame.get("num_detections", 0),
                "brightness": frame.get("brightness", 0.0),
                "blur_score": frame.get("blur_score", 0.0),
                "noise_level": frame.get("noise_level", 0.0),
                "noise_score": frame.get("noise_score", 0.0),
                "has_anomaly": frame.get("has_anomaly", False),
                "edge_id": batch.edge_id,
                "edge_buffer_size": batch.edge_buffer_stats.get("queue_size", 0),
                "edge_total_synced": batch.edge_buffer_stats.get("total_synced", 0),
            })
            if system_metrics:
                telemetry_manager.export_system_metrics(system_metrics)
            for inc in stored_incidents:
                telemetry_manager.export_incident(_incident_to_dict(inc))
        except Exception as e:
            logger.debug("Telemetry export for edge frame %d: %s", frame_index, e)

        PIPELINE_STATE["frames_processed"] += 1
        PIPELINE_STATE["incidents_total"] += len(stored_incidents)
        ingested_count += 1

    return ingested_count


# ---------------------------------------------------------------------------
# FastAPI application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Initialise database tables on startup."""
        init_db()
        logger.info("Database initialised.")
        
        # Setup telemetry WebSocket loop and register exporter
        websocket_manager.set_loop(asyncio.get_running_loop())
        telemetry_manager.register_exporter(websocket_exporter)
        
        # Register edge sync processor
        register_edge_sync_processor(process_edge_sync_batch)
        logger.info("Edge sync processor registered.")
        
        maintenance_worker = MaintenanceWorker(interval_seconds=3600.0)
        maintenance_worker.start()
        logger.info("Maintenance worker started.")

        yield
        maintenance_worker.stop()
        _shutdown_event.set()

        logger.info("Forge shutting down.")

    app = FastAPI(
        title="Forge – CV Observability",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS – allow everything during development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes.
    app.include_router(router)

    # -- Telemetry Streaming WebSocket ----------------------------------------
    @app.websocket("/ws/telemetry")
    async def websocket_telemetry_endpoint(websocket: WebSocket, pipelineId: Optional[str] = None):
        """Stream real-time frame/system metrics and incident notifications."""
        await websocket_manager.connect(websocket)
        try:
            while True:
                # Keep connection alive, receive any dummy heartbeats/data if client sends them
                await websocket.receive_text()
        except WebSocketDisconnect:
            websocket_manager.disconnect(websocket)
        except Exception as e:
            logger.error("Error in telemetry websocket connection: %s", e)
            websocket_manager.disconnect(websocket)

    # -- Dynamic pipeline start endpoint ------------------------------------
    @app.post("/api/pipeline/start", tags=["Pipeline"])
    async def start_pipeline(body: PipelineStartInput) -> Any:
        """Start the processing pipeline with the given input source."""
        if PIPELINE_STATE["is_running"]:
            return {"status": "already_running", "source": PIPELINE_STATE["source"]}

        _shutdown_event.clear()
        target_fps = body.fps if body.fps is not None else 10.0
        thread = threading.Thread(
            target=_run_pipeline_blocking,
            args=(body.input, target_fps, body.loop, body.model),
            daemon=True,
            name="forge-pipeline",
        )
        thread.start()

        # Give the thread a moment to update state.
        await asyncio.sleep(0.2)
        return {
            "status": "started",
            "source": body.input,
            "fps": target_fps,
            "loop": body.loop,
            "model": body.model,
        }

    # -- Pipeline stop endpoint ---------------------------------------------
    @app.post("/api/pipeline/stop", tags=["Pipeline"])
    async def stop_pipeline() -> Any:
        """Stop the currently running computer-vision pipeline."""
        if not PIPELINE_STATE["is_running"]:
            return {"status": "not_running"}
        _shutdown_event.set()
        PIPELINE_STATE["is_running"] = False
        return {"status": "stopping"}

    # -- Live MJPEG stream endpoint -----------------------------------------
    @app.get("/api/stream/live", tags=["Streaming"])
    async def live_video_stream():
        """MJPEG video stream endpoint for real-time frontend monitoring."""
        async def frame_generator():
            while not _shutdown_event.is_set():
                with LATEST_FRAME_LOCK:
                    frame_bytes = LATEST_FRAME_JPEG
                if frame_bytes is not None:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                    )
                    await asyncio.sleep(0.04)  # ~25 fps max poll
                else:
                    await asyncio.sleep(0.1)

        return StreamingResponse(
            frame_generator(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    # -- Snapshot JPEG endpoint ---------------------------------------------
    @app.get("/api/stream/frame", tags=["Streaming"])
    async def latest_frame_snapshot():
        """Return the latest single JPEG snapshot."""
        with LATEST_FRAME_LOCK:
            frame_bytes = LATEST_FRAME_JPEG
        if frame_bytes is None:
            raise HTTPException(status_code=404, detail="No frame available yet")
        return Response(content=frame_bytes, media_type="image/jpeg")

    # -- Static file mount for evidence images ------------------------------
    os.makedirs("outputs", exist_ok=True)
    app.mount(
        "/evidence",
        StaticFiles(directory="outputs"),
        name="evidence",
    )

    # -- Mount dashboard SPA if built ---------------------------------------
    dist_dir = os.path.join(os.path.dirname(__file__), "dashboard", "dist")
    if os.path.isdir(dist_dir):
        assets_dir = os.path.join(dist_dir, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            target = os.path.join(dist_dir, full_path)
            if full_path and os.path.isfile(target):
                return FileResponse(target)
            return FileResponse(os.path.join(dist_dir, "index.html"))

    return app


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Forge – Computer Vision Observability System",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to video file, image directory, stream URL, webcam index, or visa:category (e.g. visa:pcb1).",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=10.0,
        help="Target frames per second for stream playback/processing (default: 10.0).",
    )
    parser.add_argument(
        "--loop",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Loop dataset or video stream indefinitely (default: True).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Inference model to use: efficientad or mock (default: auto).",
    )
    parser.add_argument(
        "--noise",
        type=float,
        default=0.0,
        help="Initial sensor noise level (0.0 to 1.0).",
    )
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Bind address.")
    parser.add_argument("--port", type=int, default=8000, help="Bind port.")
    args = parser.parse_args()

    # Pre-configure degradation if requested on CLI
    if args.noise > 0.0:
        DEGRADATION_STATE["noise"] = float(args.noise)
        logger.info("Initial sensor noise level set to: %.2f", args.noise)

    app = create_app()

    # If a source is provided on the CLI, start the pipeline in background.
    if args.input:
        _shutdown_event.clear()
        pipeline_thread = threading.Thread(
            target=_run_pipeline_blocking,
            args=(args.input, args.fps, args.loop, args.model),
            daemon=True,
            name="forge-pipeline",
        )
        pipeline_thread.start()
        logger.info(
            "Pipeline thread launched for: %s (fps=%.1f, loop=%s, model=%s)",
            args.input,
            args.fps,
            args.loop,
            args.model,
        )

    # Run the API server (blocks until Ctrl+C).
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received – shutting down.")
    finally:
        _shutdown_event.set()


if __name__ == "__main__":
    main()
