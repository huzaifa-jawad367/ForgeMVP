"""Telemetry exporter interface and composite telemetry manager.

Defines the abstract base classes used to report frame metrics, system metrics,
and incident events, facilitating easy integration with OpenTelemetry or other
export targets later.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class TelemetryExporter(ABC):
    """Abstract base class representing a telemetry destination (e.g. WebSocket, Database, OpenTelemetry)."""

    @abstractmethod
    def export_frame_metrics(self, source_id: str, metrics: Dict[str, Any]) -> None:
        """Export frame-level metrics (e.g. FPS, latency, confidence, blur, brightness)."""
        pass

    @abstractmethod
    def export_system_metrics(self, metrics: Dict[str, Any]) -> None:
        """Export system-level metrics (e.g. CPU, memory, GPU)."""
        pass

    @abstractmethod
    def export_incident(self, incident: Dict[str, Any]) -> None:
        """Export incident detection events."""
        pass


class CompositeTelemetryExporter(TelemetryExporter):
    """An exporter that broadcasts telemetry to multiple registered exporters."""

    def __init__(self) -> None:
        self._exporters: List[TelemetryExporter] = []

    def register_exporter(self, exporter: TelemetryExporter) -> None:
        """Add an exporter to the registry."""
        if exporter not in self._exporters:
            self._exporters.append(exporter)
            logger.info("Registered telemetry exporter: %s", exporter.__class__.__name__)

    def unregister_exporter(self, exporter: TelemetryExporter) -> None:
        """Remove an exporter from the registry."""
        if exporter in self._exporters:
            self._exporters.remove(exporter)
            logger.info("Unregistered telemetry exporter: %s", exporter.__class__.__name__)

    def export_frame_metrics(self, source_id: str, metrics: Dict[str, Any]) -> None:
        """Broadcast frame metrics to all exporters."""
        for exporter in self._exporters:
            try:
                exporter.export_frame_metrics(source_id, metrics)
            except Exception as e:
                logger.error(
                    "Exporter %s failed on export_frame_metrics: %s",
                    exporter.__class__.__name__,
                    e,
                    exc_info=True,
                )

    def export_system_metrics(self, metrics: Dict[str, Any]) -> None:
        """Broadcast system metrics to all exporters."""
        for exporter in self._exporters:
            try:
                exporter.export_system_metrics(metrics)
            except Exception as e:
                logger.error(
                    "Exporter %s failed on export_system_metrics: %s",
                    exporter.__class__.__name__,
                    e,
                    exc_info=True,
                )

    def export_incident(self, incident: Dict[str, Any]) -> None:
        """Broadcast incident events to all exporters."""
        for exporter in self._exporters:
            try:
                exporter.export_incident(incident)
            except Exception as e:
                logger.error(
                    "Exporter %s failed on export_incident: %s",
                    exporter.__class__.__name__,
                    e,
                    exc_info=True,
                )


# Global instance of composite exporter acting as our telemetry manager
telemetry_manager = CompositeTelemetryExporter()
