"""Bounded privacy previews. All image decoding and encoding stays in memory."""

import base64
import io
import time
import warnings

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.edge.privacy import redact_image


MAX_INPUT_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 4_000_000
MAX_DIMENSION = 4096


def process_privacy_preview(image_bytes: bytes, mode: str = "blur") -> dict:
    """Return a shared-redactor PNG and metadata, or ValueError for invalid input.

    Neither originals nor outputs are written to a file or persistent store.
    """
    started = time.perf_counter()
    if mode not in {"blur", "mask"}:
        raise ValueError("Mode must be blur or mask")
    if not image_bytes or len(image_bytes) > MAX_INPUT_BYTES:
        raise ValueError("Image must be nonempty and at most 5 MiB")
    if not (image_bytes.startswith(b"\x89PNG\r\n\x1a\n") or image_bytes.startswith(b"\xff\xd8\xff")):
        raise ValueError("Only JPEG and PNG images are supported")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(image_bytes)) as probe:
                if probe.format not in {"JPEG", "PNG"}:
                    raise ValueError("Only JPEG and PNG images are supported")
                width, height = probe.size
                if max(width, height) > MAX_DIMENSION or width * height > MAX_PIXELS:
                    raise ValueError("Image exceeds 4096 pixels per dimension or 4 million pixels")
                if getattr(probe, "n_frames", 1) != 1:
                    raise ValueError("Animated images are not supported")
                probe.verify()
            with Image.open(io.BytesIO(image_bytes)) as source:
                rgb = np.asarray(ImageOps.exif_transpose(source).convert("RGB"))
                image = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    except (UnidentifiedImageError, OSError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError("Image could not be decoded as a complete JPEG or PNG") from error

    output, regions, method, result_warnings = redact_image(image, mode=mode)
    if not regions:
        result_warnings.append("No regions detected; review the output.")
    result_warnings.append("Automatic detection can miss faces or skin and can mark non-person objects; review the output.")
    encoded_ok, encoded = cv2.imencode(".png", output)
    if not encoded_ok:
        raise ValueError("Processed image could not be encoded")
    height, width = output.shape[:2]
    return {"image_base64": base64.b64encode(encoded).decode("ascii"),
            "mime_type": "image/png", "width": width, "height": height,
            "regions": regions, "region_count": len(regions),
            "processing_ms": round((time.perf_counter() - started) * 1000, 2),
            "method": method, "mode": mode, "persisted": False,
            "warnings": result_warnings}
