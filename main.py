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
import psutil
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import PipelineStartInput, router
from app.api.state import DEGRADATION_STATE, PIPELINE_STATE
from app.incidents.evidence_manager import EvidenceManager
from app.incidents.incident_engine import IncidentEngine
from app.incidents.trigger_rules import TriggerConfig
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


def _compute_frame_metrics(
    frame: np.ndarray,
    detections: list,
    inference_time_ms: float,
    fps: float,
) -> Dict[str, Any]:
    """Derive quality and detection metrics from a single frame."""

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    brightness = float(np.mean(gray))
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    confidences = [d.confidence for d in detections] if detections else []
    mean_conf = float(np.mean(confidences)) if confidences else 0.0
    min_conf = float(np.min(confidences)) if confidences else 0.0

    return {
        "fps": fps,
        "inference_time_ms": inference_time_ms,
        "mean_confidence": mean_conf,
        "min_confidence": min_conf,
        "num_detections": len(detections),
        "brightness": brightness,
        "blur_score": blur_score,
    }


# ---------------------------------------------------------------------------
# Degradation helpers
# ---------------------------------------------------------------------------


def _apply_degradation(
    frame: np.ndarray,
    detections: list,
) -> tuple:
    """Mutate *frame* and *detections* according to ``DEGRADATION_STATE``."""
    blur_level = DEGRADATION_STATE.get("blur", 0.0)
    brightness_drop = DEGRADATION_STATE.get("brightness", 0.0)
    conf_drop = DEGRADATION_STATE.get("confidence", 0.0)
    extra_latency = DEGRADATION_STATE.get("latency", 0.0)

    # Blur – kernel size proportional to level (must be odd).
    if blur_level > 0:
        ksize = int(blur_level * 51) | 1  # ensure odd
        ksize = max(ksize, 3)
        frame = cv2.GaussianBlur(frame, (ksize, ksize), 0)

    # Brightness reduction – scale pixel values down.
    if brightness_drop > 0:
        factor = 1.0 - brightness_drop
        frame = np.clip(frame.astype(np.float32) * factor, 0, 255).astype(np.uint8)

    # Confidence scaling – reduce each detection's confidence.
    if conf_drop > 0:
        for det in detections:
            det.confidence *= (1.0 - conf_drop)

    # Latency injection.
    if extra_latency > 0:
        time.sleep(extra_latency / 1000.0)

    return frame, detections


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

# Sentinel used to signal shutdown.
_shutdown_event = threading.Event()


def _run_pipeline_blocking(source_input: str) -> None:  # noqa: C901 (complexity)
    """Blocking pipeline loop – meant to run in a daemon thread.

    Handles three input types:
    * **file** – a local video file
    * **webcam** – an integer index (e.g. ``"0"``)
    * **stream** – an RTSP / HTTP URL
    * **directory** – a folder of image files
    """
    logger.info("Pipeline starting with source: %s", source_input)

    # -- Determine input type --------------------------------------------------
    is_directory = os.path.isdir(source_input)
    is_webcam = source_input.isdigit()
    is_file = os.path.isfile(source_input)

    # -- Lazy-load the inference model ----------------------------------------
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
        if is_directory:
            _run_directory_pipeline(
                source_input, model, config, evidence_mgr, incident_engine,
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
                    if is_file:
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
) -> None:
    """Process every image in *directory* sequentially."""
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    files = sorted(
        f
        for f in os.listdir(directory)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTS
    )
    if not files:
        logger.warning("No image files found in %s", directory)
        return

    for idx, fname in enumerate(files):
        if _shutdown_event.is_set():
            break
        fpath = os.path.join(directory, fname)
        frame = cv2.imread(fpath)
        if frame is None:
            continue

        _process_single_frame(
            frame=frame,
            frame_index=idx,
            timestamp_ms=float(idx * 33),  # synthetic ~30fps timing
            fps=30.0,
            source_input=directory,
            model=model,
            evidence_mgr=evidence_mgr,
            incident_engine=incident_engine,
        )


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
    """Run a single frame through inference → metrics → incidents → DB."""

    # 1. Run inference (or use empty detections).
    if model is not None:
        try:
            inference_result = model.predict(frame)
            detections = inference_result.detections
            inference_time_ms = inference_result.inference_time_ms
        except Exception:
            logger.debug("Inference failed on frame %d", frame_index)
            detections = []
            inference_time_ms = 0.0
    else:
        detections = []
        inference_time_ms = 0.0

    # 2. Apply degradation.
    frame, detections = _apply_degradation(frame, detections)

    # 3. Compute frame-level metrics.
    frame_metrics = _compute_frame_metrics(frame, detections, inference_time_ms, fps)
    frame_metrics["current_fps"] = fps
    frame_metrics["seconds_since_last_frame"] = 1.0 / fps if fps > 0 else 0.0

    # 4. System metrics.
    system_metrics: Dict[str, Any] = {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent,
        **_get_gpu_stats(),
    }

    # 5. Push frame into evidence ring buffer.
    evidence_mgr.push_frame(frame, frame_index, timestamp_ms)

    # 6. Feed incident engine.
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

    # 7. Persist to database.
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
            })
            store_system_metric(session, system_metrics)

            stored_incidents = []
            for inc in new_incidents:
                stored = store_incident(session, inc)
                stored_incidents.append(stored)
    except Exception:
        logger.exception("Database write failed on frame %d", frame_index)
        stored_incidents = []

    # 7.5. Export telemetry.
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
        })

        telemetry_manager.export_system_metrics(system_metrics)

        for inc in stored_incidents:
            telemetry_manager.export_incident(_incident_to_dict(inc))
    except Exception:
        logger.exception("Telemetry export failed on frame %d", frame_index)

    # 8. Update pipeline state.
    PIPELINE_STATE["frames_processed"] = frame_index + 1
    PIPELINE_STATE["incidents_total"] += len(new_incidents)

    if frame_index % 100 == 0:
        logger.info(
            "Frame %d | fps=%.1f | detections=%d | conf=%.3f | blur=%.1f",
            frame_index,
            fps,
            frame_metrics["num_detections"],
            frame_metrics["mean_confidence"],
            frame_metrics["blur_score"],
        )


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
        
        yield
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

        thread = threading.Thread(
            target=_run_pipeline_blocking,
            args=(body.input,),
            daemon=True,
            name="forge-pipeline",
        )
        thread.start()

        # Give the thread a moment to update state.
        await asyncio.sleep(0.2)
        return {"status": "started", "source": body.input}

    # -- Static file mount for evidence images ------------------------------
    os.makedirs("outputs", exist_ok=True)
    app.mount(
        "/evidence",
        StaticFiles(directory="outputs"),
        name="evidence",
    )

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
        help="Path to video file, image directory, stream URL, or webcam index (e.g. 0).",
    )
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Bind address.")
    parser.add_argument("--port", type=int, default=8000, help="Bind port.")
    args = parser.parse_args()

    app = create_app()

    # If a source is provided on the CLI, start the pipeline in background.
    if args.input:
        pipeline_thread = threading.Thread(
            target=_run_pipeline_blocking,
            args=(args.input,),
            daemon=True,
            name="forge-pipeline",
        )
        pipeline_thread.start()
        logger.info("Pipeline thread launched for: %s", args.input)

    # Run the API server (blocks until Ctrl+C).
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received – shutting down.")
    finally:
        _shutdown_event.set()


if __name__ == "__main__":
    main()
