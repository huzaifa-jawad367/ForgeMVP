"""Forge Edge Service – standalone entry-point.

Runs model inference beside the camera / industrial conveyor, buffers payloads
locally, and synchronises telemetry and live streams to the central Forge backend.

Usage::

    python edge_service.py --input visa:pcb1 --backend http://localhost:8000 --fps 10
    python edge_service.py --input video.mp4 --edge-id conveyor-02
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

from app.edge.service import EdgeService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("edge")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Forge Edge Service – Local CV Inference, Buffering & Sync",
    )
    parser.add_argument(
        "--input",
        type=str,
        default="visa:pcb1",
        help="Input source: visa:<category>, video.mp4, webcam index, or image folder (default: visa:pcb1).",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="http://localhost:8000",
        help="URL of the central Forge backend (default: http://localhost:8000).",
    )
    parser.add_argument(
        "--edge-id",
        type=str,
        default="edge-node-01",
        help="Unique identifier for this edge device (default: edge-node-01).",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=10.0,
        help="Target processing rate in FPS (default: 10.0).",
    )
    parser.add_argument(
        "--sync-interval",
        type=float,
        default=0.2,
        help="Buffer sync check interval in seconds (default: 0.2).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=15,
        help="Maximum frames per sync batch (default: 15).",
    )
    parser.add_argument(
        "--buffer-size",
        type=int,
        default=5000,
        help="Maximum in-memory edge queue capacity (default: 5000).",
    )
    parser.add_argument(
        "--noise",
        type=float,
        default=0.0,
        help="Initial sensor noise level between 0.0 and 1.0 (default: 0.0).",
    )
    parser.add_argument(
        "--no-loop",
        action="store_true",
        help="Stop when end of dataset is reached instead of looping.",
    )
    args = parser.parse_args()

    service = EdgeService(
        edge_id=args.edge_id,
        source_input=args.input,
        backend_url=args.backend,
        target_fps=args.fps,
        sync_interval_s=args.sync_interval,
        batch_size=args.batch_size,
        buffer_max_size=args.buffer_size,
        loop=not args.no_loop,
        initial_noise=args.noise,
    )

    def handle_exit(sig, frame):
        logger.info("Signal received. Stopping edge service...")
        service.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    service.start()

    logger.info("Edge service is running. Press Ctrl+C to terminate.")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        service.stop()


if __name__ == "__main__":
    main()
