import base64
import io
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from app.edge.privacy import redact_image, redact_worker_pii
from app.edge.privacy_preview import MAX_INPUT_BYTES, process_privacy_preview


def image_bytes(image, format="PNG", **kwargs):
    output = io.BytesIO()
    Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).save(output, format=format, **kwargs)
    return output.getvalue()


def output_pixels(result):
    return cv2.imdecode(np.frombuffer(base64.b64decode(result["image_base64"]), np.uint8), cv2.IMREAD_COLOR)


class TestPrivacyPreview(unittest.TestCase):
    def setUp(self):
        self.image = np.zeros((160, 240, 3), np.uint8)
        self.image[35:125, 50:150] = [100, 140, 210]

    def test_preview_matches_production_and_does_not_mutate_source(self):
        original = self.image.copy()
        expected, changed = redact_worker_pii(self.image)
        result = process_privacy_preview(image_bytes(self.image))
        self.assertTrue(changed)
        np.testing.assert_array_equal(self.image, original)
        np.testing.assert_array_equal(output_pixels(result), expected)
        self.assertFalse(np.array_equal(expected, original))
        self.assertEqual(result["mime_type"], "image/png")
        self.assertEqual((result["width"], result["height"]), (240, 160))
        self.assertEqual(result["region_count"], len(result["regions"]))
        self.assertIn("skin", {region["source"] for region in result["regions"]})
        self.assertFalse(result["persisted"])
        self.assertGreaterEqual(result["processing_ms"], 0)

    def test_mask_uses_shared_regions(self):
        result = process_privacy_preview(image_bytes(self.image), mode="mask")
        expected, regions, _, _ = redact_image(self.image, mode="mask")
        np.testing.assert_array_equal(output_pixels(result), expected)
        self.assertEqual(result["regions"], regions)
        self.assertTrue(regions)
        for region in regions:
            x, y, w, h = (region[key] for key in ("x", "y", "width", "height"))
            self.assertFalse(output_pixels(result)[y:y+h, x:x+w].any())

    def test_no_detection_has_explicit_warning(self):
        black = np.zeros((80, 80, 3), np.uint8)
        result = process_privacy_preview(image_bytes(black))
        self.assertEqual(result["region_count"], 0)
        self.assertIn("No regions detected; review the output.", result["warnings"])
        np.testing.assert_array_equal(output_pixels(result), black)

    def test_narrow_image_does_not_create_zero_sized_detector_input(self):
        result = process_privacy_preview(image_bytes(np.zeros((4096, 1, 3), np.uint8)))
        self.assertEqual((result["width"], result["height"]), (1, 4096))

    def test_rejects_malformed_unsupported_truncated_and_large_inputs(self):
        encoded = image_bytes(self.image)
        for body in (b"", b"not an image", b"\xff\xd8\xffbad", encoded[:100],
                     b"x" * (MAX_INPUT_BYTES + 1), image_bytes(self.image, format="BMP")):
            with self.subTest(length=len(body)), self.assertRaises(ValueError):
                process_privacy_preview(body)
        with self.assertRaisesRegex(ValueError, "Mode"):
            process_privacy_preview(encoded, mode="unknown")

    def test_dimension_limit_rejects_before_pixel_decode(self):
        oversized = Image.new("RGB", (4097, 1))
        stream = io.BytesIO()
        oversized.save(stream, format="PNG")
        with patch.object(Image.Image, "load", side_effect=AssertionError("Unexpected pixel decode")):
            with self.assertRaisesRegex(ValueError, "4096"):
                process_privacy_preview(stream.getvalue())

    def test_exif_orientation_and_jpeg(self):
        exif = Image.Exif()
        exif[274] = 6
        result = process_privacy_preview(image_bytes(self.image, format="JPEG", exif=exif))
        self.assertEqual((result["width"], result["height"]), (160, 240))

    def test_face_regions_use_the_shared_detector(self):
        class Detector:
            def detectMultiScale(self, *args, **kwargs):
                return [(20, 20, 30, 40)]

        image = np.zeros((80, 80, 3), np.uint8)
        image[30:40, 30:40] = 255
        with patch("app.edge.privacy._face_detector", return_value=Detector()) as detector:
            result = process_privacy_preview(image_bytes(image), mode="mask")
        detector.assert_called_once()
        self.assertEqual(result["regions"], [{"x": 17, "y": 16, "width": 36, "height": 48, "source": "face"}])
        self.assertIn("haar", result["method"])

    def test_missing_cascade_is_reported(self):
        with patch("app.edge.privacy._face_detector", return_value=None):
            result = process_privacy_preview(image_bytes(self.image))
        self.assertEqual(result["method"], "ycrcb-skin-v1")
        self.assertTrue(any("Face detector unavailable" in warning for warning in result["warnings"]))

    def test_many_detections_have_bounded_metadata_without_omitting_regions(self):
        class Detector:
            def detectMultiScale(self, *args, **kwargs):
                return [(x, y, 3, 3) for x in range(5, 70, 4) for y in range(5, 70, 4)]

        image = np.zeros((80, 80, 3), np.uint8)
        image[30:40, 30:40] = 255
        with patch("app.edge.privacy._face_detector", return_value=Detector()):
            result = process_privacy_preview(image_bytes(image), mode="mask")
        self.assertEqual(result["region_count"], 1)
        self.assertEqual(result["regions"][0], {"x": 5, "y": 5, "width": 67, "height": 67, "source": "face"})
        self.assertTrue(any("merged" in warning for warning in result["warnings"]))

    def test_uniform_frame_does_not_initialize_expensive_face_detector(self):
        image = np.zeros((256, 256, 3), np.uint8)
        with patch("app.edge.privacy._face_detector", side_effect=AssertionError("Uniform frame loaded detector")):
            result = process_privacy_preview(image_bytes(image))
        self.assertEqual(result["method"], "ycrcb-skin-v1+uniform-frame-check-v1")
        self.assertTrue(any("face detection was skipped" in warning for warning in result["warnings"]))
        self.assertEqual(result["regions"], [])


if __name__ == "__main__":
    unittest.main()
