import unittest
import uuid
import time
from app.edge.buffer import EdgeBuffer, EdgePayload
from app.schema.contracts import PriorityTier

class TestTieredBuffer(unittest.TestCase):
    def test_tiered_eviction(self):
        # Create a buffer with capacity 10, db_path=None to avoid disk state leakage
        buffer = EdgeBuffer(max_size=10, db_path=None)

        # Fill with 5 P0 payloads
        for i in range(5):
            payload = EdgePayload(
                payload_id=f"p0-{i}",
                frame_index=i,
                priority=PriorityTier.P0_INCIDENT,
            )
            buffer.push(payload)

        # Pushing 5 P3 items. Since high watermark is 80% (8 items),
        # pushing the 9th and 10th item will trigger eviction.
        for i in range(5):
            payload = EdgePayload(
                payload_id=f"p3-{i}",
                frame_index=i+5,
                priority=PriorityTier.P3_METRIC,
            )
            buffer.push(payload)

        # Now push 5 more P0 payloads.
        for i in range(5):
            payload = EdgePayload(
                payload_id=f"new-p0-{i}",
                frame_index=i+10,
                priority=PriorityTier.P0_INCIDENT,
            )
            buffer.push(payload)

        # Now all P3 items should be evicted.
        stats = buffer.get_stats()
        self.assertEqual(stats["p3_count"], 0)
        self.assertEqual(stats["p0_count"], 10)

        # Verify 100% of P0 incident payloads survive (the original 5 + the new 5)
        remaining_ids = [p.payload_id for p in buffer.peek_batch(20)]
        for i in range(5):
            self.assertIn(f"p0-{i}", remaining_ids)
            self.assertIn(f"new-p0-{i}", remaining_ids)

        for i in range(5):
            self.assertNotIn(f"p3-{i}", remaining_ids)

if __name__ == '__main__':
    unittest.main()
