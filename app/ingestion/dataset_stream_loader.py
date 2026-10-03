"""Continuous dataset stream loader for VisA anomaly inspection.

Simulates a factory conveyor belt camera feed by continuously streaming
normal and defective PCB images in a configurable loop at a target FPS.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterator, List, Optional

import cv2
import numpy as np

from app.ingestion import FrameData

logger = logging.getLogger(__name__)

# Search paths for VisA dataset root
POTENTIAL_VISA_ROOTS = [
    Path("../data/VisA_20220922").resolve(),
    Path("./data/VisA_20220922").resolve(),
    Path("data/VisA_20220922").resolve(),
    Path("C:/Users/Huzaifa Jawad/projects/personal/data/VisA_20220922").resolve(),
]


def find_visa_root() -> Optional[Path]:
    """Find the VisA dataset directory across common search paths."""
    for p in POTENTIAL_VISA_ROOTS:
        if p.exists() and p.is_dir():
            return p
    return None


class VisaDatasetStreamLoader:
    """Stream VisA images sequentially in a loop simulating a live conveyor belt.

    Parameters:
        category: VisA object category (e.g. 'pcb1', 'pcb2', 'capsules').
        target_fps: Playback / streaming rate (default: 10.0 FPS).
        anomaly_interval: Inject 1 anomaly frame every N normal frames (default: 8).
        loop: Whether to loop indefinitely when reaching the end of the dataset.
        visa_root: Custom root path to VisA dataset (optional).
    """

    def __init__(
        self,
        category: str = "pcb1",
        *,
        target_fps: float = 10.0,
        anomaly_interval: int = 8,
        loop: bool = True,
        visa_root: Optional[Path | str] = None,
    ) -> None:
        self.category = category.lower().replace("visa:", "")
        self.target_fps = max(target_fps, 1.0)
        self.frame_interval_s = 1.0 / self.target_fps
        self.anomaly_interval = max(anomaly_interval, 1)
        self.loop = loop
        self._stopped = False

        # Resolve VisA root
        root = Path(visa_root).resolve() if visa_root else find_visa_root()
        if not root or not root.exists():
            raise FileNotFoundError(
                f"VisA dataset root not found in {POTENTIAL_VISA_ROOTS}. "
                "Ensure data/VisA_20220922 exists."
            )
        self.visa_root = root

        cat_dir = self.visa_root / self.category
        if not cat_dir.exists():
            raise FileNotFoundError(f"VisA category '{self.category}' not found at {cat_dir}")

        # Collect normal and anomaly images
        norm_dir = cat_dir / "Data" / "Images" / "Normal"
        anom_dir = cat_dir / "Data" / "Images" / "Anomaly"

        self.normal_files: List[Path] = sorted(
            [f for f in norm_dir.iterdir() if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png"]]
        ) if norm_dir.exists() else []

        self.anomaly_files: List[Path] = sorted(
            [f for f in anom_dir.iterdir() if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png"]]
        ) if anom_dir.exists() else []

        if not self.normal_files and not self.anomaly_files:
            raise ValueError(f"No images found for category '{self.category}' in {cat_dir}")

        logger.info(
            "VisaDatasetStreamLoader initialized for '%s': %d normal, %d anomalies (Pacing: %.1f FPS, Anomaly Interval: 1/%d)",
            self.category,
            len(self.normal_files),
            len(self.anomaly_files),
            self.target_fps,
            self.anomaly_interval,
        )

    def stop(self) -> None:
        """Signal the stream to stop yielding frames."""
        self._stopped = True

    def stream(self) -> Iterator[FrameData]:
        """Convenience generator alias for iter(self)."""
        return iter(self)

    def __iter__(self) -> Iterator[FrameData]:
        frame_counter = 0
        norm_idx = 0
        anom_idx = 0
        start_time = time.time()
        last_frame_wall_time = time.time()

        source_id = f"visa:{self.category}"

        while not self._stopped:
            # Decide whether to yield normal or anomaly
            is_anomaly_turn = (
                len(self.anomaly_files) > 0
                and (frame_counter > 0 and frame_counter % self.anomaly_interval == 0)
            )

            if is_anomaly_turn:
                img_path = self.anomaly_files[anom_idx % len(self.anomaly_files)]
                anom_idx += 1
                label = "anomaly"
            else:
                img_path = self.normal_files[norm_idx % len(self.normal_files)]
                norm_idx += 1
                label = "normal"

            frame = cv2.imread(str(img_path))
            if frame is not None:
                # Calculate timing
                now = time.time()
                elapsed_since_last = now - last_frame_wall_time

                # Sleep to maintain paced target FPS
                sleep_needed = self.frame_interval_s - elapsed_since_last
                if sleep_needed > 0:
                    time.sleep(sleep_needed)
                    now = time.time()

                actual_fps = 1.0 / (now - last_frame_wall_time) if (now - last_frame_wall_time) > 0 else self.target_fps
                last_frame_wall_time = now
                timestamp_ms = (now - start_time) * 1000.0

                frame_data = FrameData(
                    frame=frame,
                    frame_index=frame_counter,
                    timestamp_ms=timestamp_ms,
                    source_id=source_id,
                    fps=round(actual_fps, 2),
                )
                frame_counter += 1
                yield frame_data

            # Check loop condition
            if not self.loop and norm_idx >= len(self.normal_files) and anom_idx >= len(self.anomaly_files):
                logger.info("Finished dataset pass and loop is disabled.")
                break
