import unittest
import uuid
import time
import asyncio
from app.api.routes import EdgeSyncBatch
from main import process_edge_sync_batch, init_db
from app.storage.database import get_session, FrameMetric
from app.schema.contracts import FailureSubsystem, PriorityTier, AuditAction, LifecycleTimestamps

class TestIdempotentIngest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        # Clear frame_metrics for clean state
        with get_session() as session:
            session.query(FrameMetric).delete()
            session.commit()

    def test_idempotent_ingestion(self):
        edge_id = str(uuid.uuid4())
        batch_id = str(uuid.uuid4())

        # Create a batch of 20 frames
        frames = []
        for i in range(20):
            frames.append({
                "frame_index": i,
                "timestamp_ms": float(i * 100),
                "fps": 10.0,
                "inference_time_ms": 15.0,
                "mean_confidence": 0.95,
                "min_confidence": 0.90,
                "num_detections": 1,
                "brightness": 128.0,
                "blur_score": 10.0,
                "noise_score": 2.0,
                "boot_id": edge_id,
                "sequence_number": i,
                "detections": [
                    {"class_name": "defect", "confidence": 0.95, "bbox": [10, 10, 50, 50]}
                ],
                "captured_at_ns": time.monotonic_ns(),
                "system_metrics": {"cpu_percent": 10.0, "memory_percent": 50.0},
            })

        batch_data = {
            "edge_id": edge_id,
            "source_id": "1",
            "batch_id": batch_id,
            "frames": frames,
            "edge_buffer_stats": {"queue_size": 20, "total_synced": 20, "total_dropped": 0},
            "latest_frame_jpeg": None,
        }

        batch = EdgeSyncBatch(**batch_data)

        # 1. First ingestion attempt (success)
        ingested, deduped = process_edge_sync_batch(batch)
        self.assertEqual(ingested, 20)
        self.assertEqual(deduped, 0)

        with get_session() as session:
            count = session.query(FrameMetric).count()
            self.assertEqual(count, 20)

        # 2. Second ingestion attempt (simulated retry)
        ingested, deduped = process_edge_sync_batch(batch)
        self.assertEqual(ingested, 0)
        self.assertEqual(deduped, 20)

        with get_session() as session:
            count = session.query(FrameMetric).count()
            self.assertEqual(count, 20) # Still 20

        # 3. Third ingestion attempt (simulated retry again)
        ingested, deduped = process_edge_sync_batch(batch)
        self.assertEqual(ingested, 0)
        self.assertEqual(deduped, 20)

        with get_session() as session:
            count = session.query(FrameMetric).count()
            self.assertEqual(count, 20) # Still 20

if __name__ == '__main__':
    unittest.main()
