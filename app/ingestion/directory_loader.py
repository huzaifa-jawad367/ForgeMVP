"""Scan a directory for video files and yield ``VideoLoader`` instances.

Usage::

    for loader in DirectoryLoader("/data/clips"):
        for frame_data in loader:
            process(frame_data)
        loader.release()
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from app.ingestion.video_loader import VideoLoader

logger = logging.getLogger(__name__)

_VIDEO_EXTENSIONS: frozenset[str] = frozenset({".mp4", ".avi", ".mkv", ".mov"})


class DirectoryLoader:
    """Discover and iterate over video files within a directory tree.

    Parameters:
        directory: Path to a directory containing video files.
        recursive: If ``True`` (default), search subdirectories recursively.

    Raises:
        NotADirectoryError: If *directory* does not exist or is not a directory.
    """

    def __init__(self, directory: str | Path, *, recursive: bool = True) -> None:
        self._directory = Path(directory).resolve()

        if not self._directory.is_dir():
            raise NotADirectoryError(
                f"Directory not found or not a directory: {self._directory}"
            )

        glob_pattern = "**/*" if recursive else "*"
        self._video_files: list[Path] = sorted(
            p
            for p in self._directory.glob(glob_pattern)
            if p.is_file() and p.suffix.lower() in _VIDEO_EXTENSIONS
        )

        logger.info(
            "Found %d video file(s) in %s", len(self._video_files), self._directory
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def video_files(self) -> list[Path]:
        """Sorted list of discovered video file paths."""
        return list(self._video_files)

    # ------------------------------------------------------------------
    # Iterator protocol
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[VideoLoader]:
        for path in self._video_files:
            try:
                yield VideoLoader(path)
            except (ValueError, FileNotFoundError) as exc:
                logger.warning("Skipping %s: %s", path.name, exc)

    def __len__(self) -> int:
        return len(self._video_files)

    def __repr__(self) -> str:
        return (
            f"DirectoryLoader(directory={str(self._directory)!r}, "
            f"videos={len(self._video_files)})"
        )
