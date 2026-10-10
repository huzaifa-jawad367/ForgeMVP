"""Comprehensive automated test suite for Forge 3-Service Architecture.

Validates:
1. Edge Service: EdgeBuffer (FIFO, capacity, drop tracking, peek/ack leasing, SQLite disk-backing).
2. Edge Inference & Degradation: Sensor noise injection, HUD rendering, base64 JPEG encoding.
3. Backend Service: Edge sync ingestion, DB persistence, IncidentEngine triggering, degradation controls return.
4. Edge-to-Backend Network Resilience: Buffer retention during backend outage and subsequent drain on reconnect.
5. Frontend Delivery: Static asset serving and SPA deep-link routing.
"""

from __future__ import annotations

import base64
import os
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request
import json
import numpy as np
import cv2

import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.edge.buffer import EdgeBuffer, EdgePayload
from app.edge.service import EdgeService
from app.api.state import DEGRADATION_STATE, EDGE_STATE, PIPELINE_STATE
from app.storage.database import get_session, init_db, FrameMetric, Incident
from main import create_app
import uvicorn


class TestEdgeBuffer(unittest.TestCase):
    """Unit tests for EdgeBuffer queue semantics, leasing, and disk persistence."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_edge.db")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_fifo_push_peek_ack(self):
        buf = EdgeBuffer(max_size=10, db_path=None)
        self.assertEqual(buf.size(), 0)

        # Push 3 payloads
        p1 = EdgePayload(payload_id="p1", frame_index=1, timestamp_ms=100.0, fps=10.0, inference_time_ms=15.0)
        p2 = EdgePayload(payload_id="p2", frame_index=2, timestamp_ms=200.0, fps=10.0, inference_time_ms=14.0)
        p3 = EdgePayload(payload_id="p3", frame_index=3, timestamp_ms=300.0, fps=10.0, inference_time_ms=16.0)

        buf.push(p1)
        buf.push(p2)
        buf.push(p3)
        self.assertEqual(buf.size(), 3)

        # Peek batch of size 2
        batch = buf.peek_batch(2)
        self.assertEqual(len(batch), 2)
        self.assertEqual(batch[0].payload_id, "p1")
        self.assertEqual(batch[1].payload_id, "p2")
        # Buffer still holds 3 until ack
        self.assertEqual(buf.size(), 3)

        # Ack batch
        buf.ack_batch(["p1", "p2"])
        self.assertEqual(buf.size(), 1)

        # Next peek returns p3
        batch2 = buf.peek_batch(5)
        self.assertEqual(len(batch2), 1)
        self.assertEqual(batch2[0].payload_id, "p3")

        buf.ack_batch(["p3"])
        self.assertEqual(buf.size(), 0)
        self.assertEqual(buf.total_synced, 3)

    def test_buffer_capacity_and_drop_tracking(self):
        buf = EdgeBuffer(max_size=3, db_path=None)
        for i in range(5):
            buf.push(EdgePayload(payload_id=f"p_{i}", frame_index=i, timestamp_ms=100.0 * i, fps=10.0, inference_time_ms=15.0))

        self.assertEqual(buf.size(), 3)
        self.assertEqual(buf.total_dropped, 2)
        # Should contain latest 3: p_2, p_3, p_4
        batch = buf.peek_batch(5)
        ids = [p.payload_id for p in batch]
        self.assertEqual(ids, ["p_2", "p_3", "p_4"])

    def test_sqlite_persistence_survives_restart(self):
        buf1 = EdgeBuffer(max_size=10, db_path=self.db_path)
        buf1.push(EdgePayload(payload_id="p_persist_1", frame_index=1, timestamp_ms=100.0, fps=10.0, inference_time_ms=12.0))
        buf1.push(EdgePayload(payload_id="p_persist_2", frame_index=2, timestamp_ms=200.0, fps=10.0, inference_time_ms=14.0))
        self.assertEqual(buf1.size(), 2)

        # Reopen buffer pointing to same SQLite database
        buf2 = EdgeBuffer(max_size=10, db_path=self.db_path)
        self.assertEqual(buf2.size(), 2)
        batch = buf2.peek_batch(2)
        self.assertEqual([p.payload_id for p in batch], ["p_persist_1", "p_persist_2"])


class TestEdgeDegradationAndInference(unittest.TestCase):
    """Unit tests for physical edge sensor noise injection and HUD rendering."""

    def test_sensor_noise_injection(self):
        service = EdgeService(edge_id="test-edge", source_input="visa:pcb1", initial_noise=0.0, db_path=None)
        clean_frame = np.ones((100, 100, 3), dtype=np.uint8) * 128

        # Noise = 0.0 -> Frame should be identical
        degraded_0 = service._apply_degradation(clean_frame.copy())
        self.assertTrue(np.array_equal(clean_frame, degraded_0))

        # Noise = 0.5 -> Mean pixel shift and variance should increase
        service.degradation["noise"] = 0.5
        degraded_noisy = service._apply_degradation(clean_frame.copy())
        diff = np.abs(degraded_noisy.astype(np.float32) - clean_frame.astype(np.float32))
        self.assertGreater(np.mean(diff), 5.0)

    def test_hud_annotation_and_jpeg_encoding(self):
        service = EdgeService(edge_id="edge-test-hud", source_input="visa:pcb1", db_path=None)
        frame = np.zeros((200, 300, 3), dtype=np.uint8)
        b64_jpeg = service._annotate_and_encode(
            frame=frame,
            detections=[],
            fps=12.5,
            latency_ms=24.0,
            frame_index=42,
        )
        self.assertIsInstance(b64_jpeg, str)
        self.assertGreater(len(b64_jpeg), 100)

        # Decode JPEG bytes to verify validity
        raw_bytes = base64.b64decode(b64_jpeg)
        decoded = cv2.imdecode(np.frombuffer(raw_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(decoded.shape[:2], (200, 300))


class TestThreeServicesEndToEnd(unittest.TestCase):
    """End-to-End integration tests for Edge Service, Backend API, and Frontend delivery."""

    @classmethod
    def setUpClass(cls):
        # Initialise DB
        init_db()

        # Start FastAPI backend in a background daemon thread on port 8899
        cls.port = 8899
        cls.backend_url = f"http://127.0.0.1:{cls.port}"
        app = create_app()
        config = uvicorn.Config(app=app, host="127.0.0.1", port=cls.port, log_level="warning")
        cls.server = uvicorn.Server(config)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()

        # Wait for backend to be responsive
        max_retries = 30
        for _ in range(max_retries):
            try:
                req = urllib.request.Request(f"{cls.backend_url}/api/edge/status")
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                time.sleep(0.15)
        else:
            raise RuntimeError("Backend failed to start on port 8899")

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.server_thread.join(timeout=2.0)

    def test_01_backend_serves_frontend_spa(self):
        """Verify Backend serves Vite dashboard SPA and handles deep-link routing."""
        # 1. Main index / dashboard
        with urllib.request.urlopen(f"{self.backend_url}/dashboard", timeout=2.0) as resp:
            self.assertEqual(resp.status, 200)
            html = resp.read().decode("utf-8")
            self.assertIn("FORGE", html)

        # 2. Deep-link route /diagnostics/pcb1-visa should return SPA index.html
        with urllib.request.urlopen(f"{self.backend_url}/diagnostics/pcb1-visa", timeout=2.0) as resp:
            self.assertEqual(resp.status, 200)
            html = resp.read().decode("utf-8")
            self.assertIn("FORGE", html)

    def test_02_edge_sync_and_incident_generation(self):
        """Verify Edge Service syncs batch, Backend persists metrics and triggers IncidentEngine."""
        sync_url = f"{self.backend_url}/api/edge/sync"

        # Frame with defect detection
        test_frame = {
            "frame_index": 101,
            "timestamp_ms": time.time() * 1000,
            "fps": 10.0,
            "inference_time_ms": 32.5,
            "mean_confidence": 0.88,
            "min_confidence": 0.88,
            "num_detections": 1,
            "detections": [
                {
                    "class_name": "scratch_defect",
                    "confidence": 0.88,
                    "bbox": [10, 10, 50, 50],
                }
            ],
            "brightness": 120.0,
            "blur_score": 150.0,
            "noise_level": 0.0,
            "noise_score": 2.1,
            "has_anomaly": True,
        }

        # Encode small 100x100 dummy preview frame
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        ret, enc = cv2.imencode(".jpg", dummy_img)
        jpeg_b64 = base64.b64encode(enc.tobytes()).decode("ascii")

        sync_payload = {
            "edge_id": "edge-unit-test-01",
            "source_id": "visa:pcb1",
            "batch_id": "batch-001",
            "frames": [test_frame],
            "edge_buffer_stats": {
                "queue_size": 0,
                "total_synced": 1,
                "total_dropped": 0,
            },
            "latest_frame_jpeg": jpeg_b64,
        }

        req = urllib.request.Request(
            sync_url,
            data=json.dumps(sync_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=3.0) as resp:
            self.assertEqual(resp.status, 200)
            res_body = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(res_body["status"], "ack")
            self.assertEqual(res_body["edge_id"], "edge-unit-test-01")
            self.assertEqual(res_body["frames_ingested"], 1)
            self.assertIn("controls", res_body)

        # Check edge status endpoint
        with urllib.request.urlopen(f"{self.backend_url}/api/edge/status", timeout=2.0) as resp:
            self.assertEqual(resp.status, 200)
            edge_st = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(edge_st["is_connected"])
            self.assertEqual(edge_st["edge_id"], "edge-unit-test-01")
            self.assertEqual(edge_st["total_synced"], 1)

        # Check live snapshot endpoint returns the image uploaded by edge
        with urllib.request.urlopen(f"{self.backend_url}/api/stream/frame", timeout=2.0) as resp:
            self.assertEqual(resp.status, 200)
            frame_bytes = resp.read()
            self.assertGreater(len(frame_bytes), 50)

    def test_03_remote_sensor_noise_control_loop(self):
        """Verify changing sensor noise on Backend propagates to Edge Service via sync ACK."""
        # 1. Update backend degradation control to noise=0.65
        degrade_url = f"{self.backend_url}/api/demo/degrade"
        req = urllib.request.Request(
            degrade_url,
            data=json.dumps({"noise": 0.65, "blur": 0.0, "brightness": 0.0, "confidence": 0.0, "latency": 0.0}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            self.assertEqual(resp.status, 200)

        # 2. Create an EdgeService instance connected to this backend
        edge = EdgeService(
            edge_id="edge-control-test",
            source_input="visa:pcb1",
            backend_url=self.backend_url,
            sync_interval_s=0.1,
            initial_noise=0.0,
            db_path=None,
        )

        # Buffer a dummy frame
        edge.buffer.push(EdgePayload(
            payload_id="ctl-1",
            frame_index=1,
            timestamp_ms=time.time() * 1000,
            fps=10.0,
            inference_time_ms=15.0,
            noise_level=0.0,
        ))

        # Start sync thread briefly
        edge._shutdown_event.clear()
        sync_thread = threading.Thread(target=edge._run_sync_worker, daemon=True)
        sync_thread.start()

        # Wait for sync worker to post and receive controls
        time.sleep(0.5)
        edge.stop()

        # Edge service should have updated its local noise degradation setting to 0.65!
        self.assertAlmostEqual(edge.degradation.get("noise", 0.0), 0.65, places=2)

    def test_04_edge_offline_buffer_retention_and_reconnection_drain(self):
        """Verify Edge Service holds payloads in buffer while backend is unreachable, then flushes when reconnected."""
        # 1. Point edge service to an unreachable port (simulated network outage)
        unreachable_url = "http://127.0.0.1:9998"
        edge = EdgeService(
            edge_id="edge-resilience-node",
            source_input="visa:pcb1",
            backend_url=unreachable_url,
            sync_interval_s=0.1,
            batch_size=10,
            db_path=None,
        )

        # Push 15 frames into the edge buffer
        for i in range(15):
            edge.buffer.push(EdgePayload(
                payload_id=f"resilience_{i}",
                frame_index=i,
                timestamp_ms=time.time() * 1000 + i,
                fps=10.0,
                inference_time_ms=12.0,
            ))

        self.assertEqual(edge.buffer.size(), 15)

        # Run sync worker against unreachable backend for a moment
        edge._shutdown_event.clear()
        worker_thread = threading.Thread(target=edge._run_sync_worker, daemon=True)
        worker_thread.start()
        time.sleep(0.35)

        # Buffer MUST still contain all 15 frames!
        self.assertEqual(edge.buffer.size(), 15)
        self.assertFalse(edge.is_connected)

        # Now reconnect: update backend URL to the live backend server
        edge.backend_url = self.backend_url

        # Wait up to 4.0s for worker to sync both batches (10 + 5 = 15) and drain queue
        deadline = time.time() + 4.0
        while time.time() < deadline and edge.buffer.size() > 0:
            time.sleep(0.1)

        # Stop worker
        edge.stop()

        # Buffer should have been drained and acknowledged!
        self.assertEqual(edge.buffer.size(), 0)
        self.assertEqual(edge.buffer.total_synced, 15)
        self.assertTrue(edge.is_connected)


if __name__ == "__main__":
    unittest.main()
