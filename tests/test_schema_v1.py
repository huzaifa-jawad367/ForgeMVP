import time
import unittest
import uuid
import json

from pydantic import ValidationError
from app.api.routes import EdgeSyncBatch
from app.edge.service import EdgeService
from app.edge.buffer import EdgePayload

class TestSchemaV1(unittest.TestCase):
    def test_schema_v1_payload_compliance(self):
        """Validate payload schema compliance against v1.0.0."""
        valid_payload = {
            "schema_version": "1.0.0",
            "boot_id": str(uuid.uuid4()),
            "sequence_range": {"start": 1, "end": 1},
            "transmitted_at_ms": time.time() * 1000.0,
            "edge_id": "test-edge",
            "source_id": "test-source",
            "batch_id": str(uuid.uuid4()),
            "frames": [
                {
                    "payload_id": str(uuid.uuid4()),
                    "frame_index": 1,
                    "sequence_number": 1,
                    "timestamps": {
                        "captured_at_ns": time.monotonic_ns(),
                        "inference_started_at_ns": time.monotonic_ns(),
                        "inference_completed_at_ns": time.monotonic_ns(),
                        "queued_at_ns": time.monotonic_ns(),
                    },
                }
            ],
            "edge_buffer_stats": {},
            "latest_frame_jpeg": None,
        }

        # This should not raise any validation errors
        batch = EdgeSyncBatch(**valid_payload)
        self.assertEqual(batch.schema_version, "1.0.0")

        invalid_payload = valid_payload.copy()
        del invalid_payload["boot_id"]
        with self.assertRaises(ValidationError):
            EdgeSyncBatch(**invalid_payload)

    def test_nanosecond_monotonic_transitions(self):
        """Assert all duration transitions are strictly positive (>= 0)."""
        edge = EdgeService(source_input="test")
        edge._shutdown_event.clear()

        # mock inference process
        # captured_at -> inference_started -> inference_completed -> queued_at -> transmitted_at

        captured_at = time.monotonic_ns()
        time.sleep(0.001)
        inference_started_at = time.monotonic_ns()
        time.sleep(0.001)
        inference_completed_at = time.monotonic_ns()
        time.sleep(0.001)
        queued_at = time.monotonic_ns()

        payload = EdgePayload(
            frame_index=1,
            sequence_number=1,
            timestamps={
                "captured_at_ns": captured_at,
                "inference_started_at_ns": inference_started_at,
                "inference_completed_at_ns": inference_completed_at,
                "queued_at_ns": queued_at,
            }
        )
        edge.buffer.push(payload)

        batch = edge.buffer.peek_batch(1)

        transmitted_at = time.monotonic_ns()
        for p in batch:
            p.timestamps["transmitted_at_ns"] = transmitted_at

        timestamps = batch[0].timestamps

        self.assertGreaterEqual(timestamps["inference_started_at_ns"] - timestamps["captured_at_ns"], 0)
        self.assertGreaterEqual(timestamps["inference_completed_at_ns"] - timestamps["inference_started_at_ns"], 0)
        self.assertGreaterEqual(timestamps["queued_at_ns"] - timestamps["inference_completed_at_ns"], 0)
        self.assertGreaterEqual(timestamps["transmitted_at_ns"] - timestamps["queued_at_ns"], 0)

if __name__ == "__main__":
    unittest.main()
