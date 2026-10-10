import time
import unittest

import cv2
import numpy as np

from app.edge.privacy import redact_worker_pii


class TestPIIRedaction(unittest.TestCase):
    """Unit tests for the in-memory PII worker redaction logic."""

    def test_redact_worker_pii_no_skin(self):
        """Test with an image containing no skin tones (all black)."""
        img = np.zeros((256, 256, 3), dtype=np.uint8)

        start_t = time.perf_counter()
        res_img, was_redacted = redact_worker_pii(img)
        end_t = time.perf_counter()

        latency_ms = (end_t - start_t) * 1000
        self.assertFalse(was_redacted)
        self.assertTrue(np.array_equal(img, res_img))
        self.assertLessEqual(latency_ms, 25.0)

    def test_redact_worker_pii_with_skin(self):
        """Test with a synthetic image containing a skin-tone block."""
        img = np.zeros((256, 256, 3), dtype=np.uint8)

        # BGR representation of a skin color (e.g., RGB ~200, 150, 120 -> BGR ~120, 150, 200)
        # Check against typical YCrCb bounds
        # Let's use a known YCrCb skin value converted to BGR
        # Y=140, Cr=150, Cb=110
        # Instead, just fill a solid typical skin color in BGR: [100, 140, 210]
        img[50:150, 50:150] = [100, 140, 210]

        original_roi = img[50:150, 50:150].copy()

        start_t = time.perf_counter()
        res_img, was_redacted = redact_worker_pii(img, blur_kernel=31)
        end_t = time.perf_counter()

        latency_ms = (end_t - start_t) * 1000

        self.assertTrue(was_redacted)
        self.assertLessEqual(latency_ms, 25.0)

        # Check that the region has been changed (blurred)
        redacted_roi = res_img[50:150, 50:150]
        self.assertFalse(np.array_equal(original_roi, redacted_roi))


if __name__ == "__main__":
    unittest.main()
