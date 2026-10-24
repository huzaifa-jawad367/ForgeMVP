import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import app.api.routes as routes
import app.storage.database as database
import main


class TestDemoIngest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            f"sqlite:///{Path(self.temporary.name) / 'backend.db'}",
            connect_args={"check_same_thread": False},
        )
        self.patches = [
            patch.object(database, "engine", self.engine),
            patch.object(database, "SessionLocal", sessionmaker(bind=self.engine, expire_on_commit=False)),
            patch.object(main._backend_incident_engine, "process_frame", return_value=[]),
        ]
        for patcher in self.patches:
            patcher.start()
        database.init_db()
        self.previous_processor = routes._edge_sync_processor
        routes.register_edge_sync_processor(main.process_edge_sync_batch)
        self.client = TestClient(main.create_app())

    def tearDown(self):
        self.client.close()
        routes.register_edge_sync_processor(self.previous_processor)
        for patcher in reversed(self.patches):
            patcher.stop()
        self.engine.dispose()
        self.temporary.cleanup()

    def batch(self, edge="demo-edge", payload_id=None, boot_id="demo-boot"):
        return {
            "edge_id": edge, "boot_id": boot_id, "source_id": "visa:pcb1",
            "schema_version": "1.0.0", "batch_id": str(uuid.uuid4()),
            "sequence_range": {"start": 1, "end": 1}, "transmitted_at_ms": 1,
            "frames": [{
                "payload_id": payload_id or str(uuid.uuid4()), "boot_id": boot_id,
                "frame_index": 1, "sequence_number": 1, "timestamp_ms": 1,
                "fps": 1, "inference_time_ms": 5,
                "system_metrics": {"cpu_percent": 1, "memory_percent": 2},
            }],
        }

    def test_committed_retry_is_deduplicated_and_exact_ids_acknowledged(self):
        batch = self.batch()
        expected_id = batch["frames"][0]["payload_id"]
        for expected_new, expected_duplicate in [(1, 0), (0, 1), (0, 1)]:
            response = self.client.post("/api/edge/sync", json=batch)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["frames_ingested"], expected_new)
            self.assertEqual(response.json()["frames_deduplicated"], expected_duplicate)
            self.assertEqual(response.json()["acknowledged_payload_ids"], [expected_id])
        with database.get_session() as session:
            self.assertEqual(session.query(database.FrameMetric).count(), 1)

    def test_failed_transaction_is_not_acknowledged_or_committed(self):
        batch = self.batch()
        with patch.object(main, "store_system_metric", side_effect=RuntimeError("disk unavailable")):
            response = self.client.post("/api/edge/sync", json=batch)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("acknowledged_payload_ids", response.json())
        with database.get_session() as session:
            self.assertEqual(session.query(database.FrameMetric).count(), 0)
        self.assertEqual(self.client.post("/api/edge/sync", json=batch).status_code, 200)

    def test_identity_and_reconciliation_are_edge_scoped(self):
        payload_id = str(uuid.uuid4())
        for edge in ["edge-a", "edge-b"]:
            self.assertEqual(self.client.post("/api/edge/sync", json=self.batch(edge, payload_id)).status_code, 200)
        with database.get_session() as session:
            self.assertEqual(session.query(database.FrameMetric).count(), 2)
        response = self.client.post("/api/demo/reconcile", json={
            "edge_id": "edge-a", "payload_ids": [payload_id, "missing"],
        })
        self.assertEqual(response.json()["committed_payload_ids"], [payload_id])
        self.assertEqual(response.json()["missing_payload_ids"], ["missing"])
        response = self.client.post("/api/demo/reconcile", json={
            "edge_id": "another-edge", "payload_ids": [payload_id],
        })
        self.assertEqual(response.json()["committed_count"], 0)

    def test_reusing_a_sequence_for_another_payload_is_not_a_valid_ack(self):
        self.assertEqual(self.client.post("/api/edge/sync", json=self.batch()).status_code, 200)
        self.assertEqual(self.client.post("/api/edge/sync", json=self.batch()).status_code, 503)

    def test_database_enforces_identity_without_the_helper(self):
        self.client.post("/api/edge/sync", json=self.batch())
        with self.assertRaises(IntegrityError):
            with database.get_session() as session:
                session.add(database.FrameMetric(
                    edge_id="demo-edge", payload_id="different", boot_id="demo-boot",
                    sequence_number=1, source_id=1, frame_index=1, timestamp_ms=1,
                    fps=1, inference_time_ms=5,
                ))

    def test_reconciliation_rejects_unbounded_or_invalid_requests(self):
        for payload_ids in [["x"] * 1001, [""], ["x" * 129]]:
            self.assertEqual(self.client.post("/api/demo/reconcile", json={
                "edge_id": "demo-edge", "payload_ids": payload_ids,
            }).status_code, 422)


if __name__ == "__main__":
    unittest.main()
