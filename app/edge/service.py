"""Edge service implementation.

Runs continuous computer-vision anomaly inference beside the camera, injects
sensor noise/perturbations, buffers payloads in a local queue, and synchronises
telemetry and incident streams with the central Forge backend.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import psutil

from app.edge.buffer import EdgeBuffer, EdgePayload
from app.inference.efficientad_runner import EfficientADRunner
from app.ingestion.dataset_stream_loader import VisaDatasetStreamLoader

logger = logging.getLogger("forge.edge")


def _get_hardware_telemetry() -> Dict[str, Any]:
    """Collect edge system metrics (CPU, RAM, and NVIDIA GPU if present)."""
    metrics: Dict[str, Any] = {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent,
        "gpu_utilization": None,
        "gpu_memory_percent": None,
        "gpu_temperature": None,
    }
    try:
        import pynvml  # type: ignore[import-untyped]

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        pynvml.nvmlShutdown()
        metrics["gpu_utilization"] = float(util.gpu)
        metrics["gpu_memory_percent"] = float(mem.used / mem.total * 100) if mem.total else 0.0
        metrics["gpu_temperature"] = float(temp)
    except Exception:
        pass
    return metrics


class EdgeService:
    """Edge processing service with local inference, buffer queue, and backend sync."""

    def __init__(
        self,
        edge_id: str = "edge-node-01",
        source_input: str = "visa:pcb1",
        backend_url: str = "http://localhost:8000",
        target_fps: float = 10.0,
        sync_interval_s: float = 0.2,
        batch_size: int = 15,
        buffer_max_size: int = 5000,
        db_path: Optional[str] = "outputs/edge_buffer.db",
        loop: bool = True,
        initial_noise: float = 0.0,
    ) -> None:
        self.edge_id = edge_id
        self.source_input = source_input
        self.backend_url = backend_url.rstrip("/")
        self.target_fps = target_fps
        self.sync_interval_s = sync_interval_s
        self.batch_size = batch_size
        self.loop = loop

        self.boot_id = str(uuid.uuid4())
        self.sequence_number = 0

        # 1. Local Edge Buffer
        self.buffer = EdgeBuffer(max_size=buffer_max_size, db_path=db_path)

        # 2. Local Degradation State (controllable remotely via backend sync)
        self.degradation: Dict[str, float] = {
            "noise": initial_noise,
            "blur": 0.0,
            "brightness": 0.0,
            "confidence": 0.0,
            "latency": 0.0,
        }

        # 3. Model setup
        self.model: Any = None
        self._init_model()

        # 4. Concurrency controls
        self._shutdown_event = threading.Event()
        self._inference_thread: Optional[threading.Thread] = None
        self._sync_thread: Optional[threading.Thread] = None

        self._latest_jpeg_b64: Optional[str] = None
        self._latest_jpeg_lock = threading.Lock()

        self.frames_processed = 0
        self.is_connected = False
        self.last_sync_time = 0.0

    def _init_model(self) -> None:
        """Initialise the edge inference model."""
        category = "pcb1"
        if ":" in self.source_input:
            category = self.source_input.split(":", 1)[1].strip()

        logger.info("[%s] Initialising EfficientAD on edge for category '%s'...", self.edge_id, category)
        try:
            self.model = EfficientADRunner(category=category)
        except Exception:
            logger.exception("[%s] Failed to load EfficientAD, attempting fallback model...", self.edge_id)
            try:
                from app.inference.model_wrapper import get_inference_model
                self.model = get_inference_model()
            except Exception:
                logger.error("[%s] No model could be loaded on edge.", self.edge_id)
                self.model = None

    def start(self) -> None:
        """Start edge inference and background sync worker."""
        self._shutdown_event.clear()

        # Inference loop thread
        self._inference_thread = threading.Thread(
            target=self._run_inference_loop,
            daemon=True,
            name=f"{self.edge_id}-inference",
        )
        self._inference_thread.start()

        # Sync worker thread
        self._sync_thread = threading.Thread(
            target=self._run_sync_worker,
            daemon=True,
            name=f"{self.edge_id}-sync",
        )
        self._sync_thread.start()

        logger.info(
            "[%s] Edge Service started. Source: %s, Backend: %s, Target FPS: %.1f",
            self.edge_id,
            self.source_input,
            self.backend_url,
            self.target_fps,
        )

    def stop(self) -> None:
        """Stop edge service gracefully."""
        self._shutdown_event.set()
        if self._inference_thread and self._inference_thread.is_alive():
            self._inference_thread.join(timeout=2.0)
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=2.0)
        logger.info("[%s] Edge Service stopped. Total frames processed: %d", self.edge_id, self.frames_processed)

    def _apply_degradation(self, frame: np.ndarray) -> np.ndarray:
        """Apply physical sensor noise, blur, and lighting drop on the edge."""
        noise_level = self.degradation.get("noise", 0.0)
        blur_level = self.degradation.get("blur", 0.0)
        brightness_drop = self.degradation.get("brightness", 0.0)
        latency_ms = self.degradation.get("latency", 0.0)

        # 1. Sensor Gaussian Noise injection
        if noise_level > 0:
            sigma = float(noise_level * 55.0)
            gauss = np.random.normal(0, sigma, frame.shape).astype(np.float32)
            frame = np.clip(frame.astype(np.float32) + gauss, 0, 255).astype(np.uint8)

        # 2. Defocus blur
        if blur_level > 0:
            ksize = int(blur_level * 51) | 1
            ksize = max(ksize, 3)
            frame = cv2.GaussianBlur(frame, (ksize, ksize), 0)

        # 3. Lighting drop
        if brightness_drop > 0:
            factor = 1.0 - brightness_drop
            frame = np.clip(frame.astype(np.float32) * factor, 0, 255).astype(np.uint8)

        # 4. Latency
        if latency_ms > 0:
            time.sleep(latency_ms / 1000.0)

        return frame

    def _annotate_and_encode(
        self,
        frame: np.ndarray,
        detections: list,
        fps: float,
        latency_ms: float,
        frame_index: int,
    ) -> str:
        """Draw HUD and defect bounding boxes, returning a base64 encoded JPEG."""
        annotated = frame.copy()
        h, w = annotated.shape[:2]

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
        status_tag = f"● EDGE [{self.edge_id}] DEFECT" if has_anomaly else f"● EDGE [{self.edge_id}] OK"
        status_col = (0, 0, 255) if has_anomaly else (0, 255, 120)

        noise_val = self.degradation.get("noise", 0.0)
        hud_str = f"FRAME #{frame_index:04d} | {fps:.1f} FPS | LAT: {latency_ms:.1f}ms"
        if noise_val > 0:
            hud_str += f" | NOISE: {noise_val * 100:.0f}%"

        cv2.putText(annotated, status_tag, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_col, 2, cv2.LINE_AA)
        cv2.putText(annotated, hud_str, (260, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 240, 255), 1, cv2.LINE_AA)

        ret, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret:
            b64 = base64.b64encode(encoded.tobytes()).decode("ascii")
            with self._latest_jpeg_lock:
                self._latest_jpeg_b64 = b64
            return b64
        return ""

    def _run_inference_loop(self) -> None:
        """Stream camera frames, run edge inference, and push to EdgeBuffer."""
        logger.info("[%s] Inference loop started.", self.edge_id)

        is_visa = self.source_input.lower().startswith("visa")
        if is_visa:
            category = "pcb1"
            if ":" in self.source_input:
                category = self.source_input.split(":", 1)[1].strip()
            loader = VisaDatasetStreamLoader(
                category=category,
                target_fps=self.target_fps,
                loop=self.loop,
                anomaly_interval=8,
            )
            stream_gen = loader.stream()
        else:
            stream_gen = None

        frame_counter = 0
        last_frame_time = time.time()

        while not self._shutdown_event.is_set():
            # 1. Fetch next frame
            captured_at_ns = time.monotonic_ns()
            if stream_gen is not None:
                try:
                    stream_frame = next(stream_gen)
                    frame = stream_frame.frame
                    timestamp_ms = stream_frame.timestamp_ms
                    measured_fps = stream_frame.fps
                except StopIteration:
                    logger.info("[%s] End of dataset reached.", self.edge_id)
                    break
            else:
                time.sleep(1.0 / self.target_fps)
                frame = np.zeros((256, 256, 3), dtype=np.uint8)
                timestamp_ms = time.time() * 1000.0
                measured_fps = self.target_fps

            now = time.time()
            elapsed = now - last_frame_time
            if stream_gen is None and elapsed > 0:
                measured_fps = 1.0 / elapsed
            last_frame_time = now

            # 2. Physical noise injection
            degraded_frame = self._apply_degradation(frame)

            # 3. Model inference on edge
            detections = []
            inference_time_ms = 0.0
            inference_started_at_ns = time.monotonic_ns()
            if self.model is not None:
                try:
                    inf_res = self.model.predict(degraded_frame)
                    detections = inf_res.detections
                    inference_time_ms = inf_res.inference_time_ms
                except Exception:
                    logger.debug("[%s] Inference error on frame %d", self.edge_id, frame_counter)
            inference_completed_at_ns = time.monotonic_ns()

            # 4. Compute metrics
            gray = cv2.cvtColor(degraded_frame, cv2.COLOR_BGR2GRAY) if len(degraded_frame.shape) == 3 else degraded_frame
            brightness = float(np.mean(gray))
            blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            blurred_gray = cv2.GaussianBlur(gray, (5, 5), 0)
            noise_std = float(np.std(cv2.absdiff(gray, blurred_gray)))
            noise_level = float(self.degradation.get("noise", 0.0) * 100.0)

            confs = [d.confidence for d in detections] if detections else []
            mean_conf = float(np.mean(confs)) if confs else 0.0
            min_conf = float(np.min(confs)) if confs else 0.0
            has_anomaly = any("defect" in d.class_name.lower() or "anomaly" in d.class_name.lower() for d in detections)

            # 5. Annotate frame and encode JPEG preview
            jpeg_b64 = self._annotate_and_encode(
                frame=degraded_frame,
                detections=detections,
                fps=measured_fps,
                latency_ms=inference_time_ms,
                frame_index=frame_counter,
            )

            # 6. Format detections list
            det_dicts = [
                {
                    "class_name": d.class_name,
                    "confidence": float(d.confidence),
                    "bbox": [float(v) for v in d.bbox],
                }
                for d in detections
            ]

            # 7. Collect edge system metrics
            sys_metrics = _get_hardware_telemetry()

            # 8. Create payload and push to edge buffer
            self.sequence_number += 1
            payload = EdgePayload(
                payload_id=str(uuid.uuid4()),
                frame_index=frame_counter,
                sequence_number=self.sequence_number,
                timestamp_ms=timestamp_ms,
                fps=measured_fps,
                inference_time_ms=inference_time_ms,
                mean_confidence=mean_conf,
                min_confidence=min_conf,
                num_detections=len(detections),
                detections=det_dicts,
                brightness=brightness,
                blur_score=blur_score,
                noise_level=noise_level,
                noise_score=noise_std,
                has_anomaly=has_anomaly,
                system_metrics=sys_metrics,
                frame_jpeg_b64=jpeg_b64 if frame_counter % 2 == 0 else None,  # Sync keyframes regularly
                timestamps={
                    "captured_at_ns": captured_at_ns,
                    "inference_started_at_ns": inference_started_at_ns,
                    "inference_completed_at_ns": inference_completed_at_ns,
                    "queued_at_ns": time.monotonic_ns(),
                }
            )
            self.buffer.push(payload)

            frame_counter += 1
            self.frames_processed = frame_counter

            if frame_counter % 20 == 0:
                logger.info(
                    "[%s] Frame #%04d | Rate: %.1f FPS | Latency: %.1f ms | Anomaly: %s | Buffer: %d",
                    self.edge_id,
                    frame_counter,
                    measured_fps,
                    inference_time_ms,
                    has_anomaly,
                    self.buffer.size(),
                )

    def _run_sync_worker(self) -> None:
        """Batch and sync buffered payloads to Forge central backend."""
        while not self._shutdown_event.is_set():
            time.sleep(self.sync_interval_s)
            sync_url = f"{self.backend_url}/api/edge/sync"

            # Peek a batch from the edge buffer
            batch = self.buffer.peek_batch(self.batch_size)
            if not batch:
                continue

            with self._latest_jpeg_lock:
                latest_jpeg = self._latest_jpeg_b64

            # Prepare sync batch package
            transmitted_at_ms = time.time() * 1000.0
            transmitted_at_ns = time.monotonic_ns()

            # Inject transmitted_at_ns into frames
            frames_dict = []
            for p in batch:
                p_dict = p.to_dict()
                if "timestamps" in p_dict:
                    p_dict["timestamps"]["transmitted_at_ns"] = transmitted_at_ns
                frames_dict.append(p_dict)

            sequence_start = batch[0].sequence_number if batch else 0
            sequence_end = batch[-1].sequence_number if batch else 0

            from app.schema.contracts import SCHEMA_VERSION
            payload_data = {
                "schema_version": SCHEMA_VERSION,
                "boot_id": self.boot_id,
                "sequence_range": {"start": sequence_start, "end": sequence_end},
                "transmitted_at_ms": transmitted_at_ms,
                "edge_id": self.edge_id,
                "source_id": self.source_input,
                "batch_id": str(uuid.uuid4()),
                "frames": frames_dict,
                "edge_buffer_stats": self.buffer.get_stats(),
                "latest_frame_jpeg": latest_jpeg,
            }

            try:
                json_bytes = json.dumps(payload_data).encode("utf-8")
                req = urllib.request.Request(
                    sync_url,
                    data=json_bytes,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    if resp.status == 200:
                        body_resp = json.loads(resp.read().decode("utf-8"))
                        # Acknowledge synced items from edge buffer
                        synced_ids = [p.payload_id for p in batch]
                        self.buffer.ack_batch(synced_ids)

                        self.is_connected = True
                        self.last_sync_time = time.time()

                        # Apply any control updates sent back by the backend (e.g. noise injection)
                        controls = body_resp.get("controls", {})
                        if "noise" in controls:
                            self.degradation["noise"] = float(controls["noise"])
                        if "blur" in controls:
                            self.degradation["blur"] = float(controls["blur"])
                        if "brightness" in controls:
                            self.degradation["brightness"] = float(controls["brightness"])
                        if "confidence" in controls:
                            self.degradation["confidence"] = float(controls["confidence"])
                        if "latency" in controls:
                            self.degradation["latency"] = float(controls["latency"])

            except Exception as e:
                self.is_connected = False
                logger.warning(
                    "[%s] Backend unreachable at %s (%s). Retaining %d frames in edge buffer.",
                    self.edge_id,
                    sync_url,
                    e,
                    self.buffer.size(),
                )
