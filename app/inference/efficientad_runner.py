"""EfficientAD-medium inference runner for Forge.

Wraps the Hugging Face model ``thangkt/visionqc-efficientad-medium-pcb1``
for anomaly detection and defect localization on VisA PCB images/streams.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
import torch
from torchvision.transforms import functional as TF
from PIL import Image

from app.inference.model_wrapper import (
    BaseInferenceModel,
    Detection,
    InferenceResult,
)

logger = logging.getLogger(__name__)

HF_REPO_ID = "thangkt/visionqc-efficientad-medium-pcb1"
CKPT_FILENAME = "model-best.ckpt"


class EfficientADRunner(BaseInferenceModel):
    """Run EfficientAD-medium anomaly detection and defect localization.

    Parameters:
        ckpt_path: Path to local checkpoint or None to download from Hugging Face.
        threshold: Decision threshold for anomaly classification (default: 0.5).
        min_defect_area: Minimum contour pixel area to report as a bounding box.
        device: "cuda" or "cpu" (auto-detected if None).
    """

    def __init__(
        self,
        ckpt_path: Optional[str] = None,
        threshold: float = 0.5,
        min_defect_area: int = 50,
        device: Optional[str] = None,
        category: str = "pcb1",
    ) -> None:
        from anomalib.models import EfficientAd
        from huggingface_hub import hf_hub_download

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.threshold = threshold
        self.min_defect_area = min_defect_area
        self.target_size = (256, 256)

        if ckpt_path is None or not Path(ckpt_path).exists():
            logger.info("Resolving Hugging Face checkpoint for %s...", HF_REPO_ID)
            ckpt_path = hf_hub_download(repo_id=HF_REPO_ID, filename=CKPT_FILENAME)

        self._ckpt_path = ckpt_path
        logger.info("Loading EfficientAD weights from %s...", ckpt_path)

        data = torch.load(ckpt_path, map_location=self.device, weights_only=False)
        hparams = data.get("hyper_parameters", {})

        self._model = EfficientAd(
            model_size=hparams.get("model_size", "medium"),
            teacher_out_channels=hparams.get("teacher_out_channels", 384),
            padding=hparams.get("padding", False),
            pad_maps=hparams.get("pad_maps", True),
        )
        self._model.load_state_dict(data["state_dict"], strict=False)
        self._model.to(self.device)
        self._model.eval()

        self._model_name = "EfficientAD-medium-pcb1"
        logger.info("EfficientADRunner initialized on %s (Threshold: %.2f)", self.device, self.threshold)

    def predict(self, frame: np.ndarray) -> InferenceResult:
        """Run anomaly detection on a single BGR frame.

        Parameters:
            frame: Input BGR image (H×W×3, uint8).

        Returns:
            InferenceResult with defect bounding boxes and anomaly confidence.
        """
        t0 = time.perf_counter()
        h, w = frame.shape[:2]

        # Convert BGR to RGB PIL and resize to 256x256
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_frame).resize(self.target_size, Image.BILINEAR)
        tensor = TF.to_tensor(pil_img).unsqueeze(0).to(self.device)

        with torch.no_grad():
            out = self._model(tensor)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        score = float(out.pred_score.item())
        is_anomaly = bool(out.pred_label.item()) if hasattr(out, "pred_label") and out.pred_label is not None else (score >= self.threshold)

        detections: List[Detection] = []

        if is_anomaly:
            # Extract anomaly localization mask
            amap = out.anomaly_map.squeeze().cpu().numpy()
            amap_resized = cv2.resize(amap, (w, h))

            # Threshold anomaly heatmap to find defect regions
            binary_mask = (amap_resized >= self.threshold).astype(np.uint8) * 255
            contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            found_box = False
            for cnt in contours:
                if cv2.contourArea(cnt) >= self.min_defect_area:
                    bx, by, bw, bh = cv2.boundingRect(cnt)
                    detections.append(
                        Detection(
                            bbox=(float(bx), float(by), float(bx + bw), float(by + bh)),
                            class_name="defect",
                            confidence=round(score, 4),
                            class_id=1,
                        )
                    )
                    found_box = True

            # If anomaly score is high but no single contour exceeded threshold area,
            # report the global region with highest anomaly intensity
            if not found_box:
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(amap_resized)
                cx, cy = max_loc
                radius = 30
                bx1 = max(0, cx - radius)
                by1 = max(0, cy - radius)
                bx2 = min(w, cx + radius)
                by2 = min(h, cy + radius)
                detections.append(
                    Detection(
                        bbox=(float(bx1), float(by1), float(bx2), float(by2)),
                        class_name="anomaly_spot",
                        confidence=round(score, 4),
                        class_id=1,
                    )
                )

        return InferenceResult(
            detections=detections,
            inference_time_ms=round(elapsed_ms, 2),
            model_name=self._model_name,
        )
