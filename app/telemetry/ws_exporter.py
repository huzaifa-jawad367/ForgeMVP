"""WebSocket telemetry exporter implementation.

Manages active WebSocket connections from the dashboard frontend and broadcasts
metrics and incidents using a thread-safe scheduler.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from app.telemetry.reporter import TelemetryExporter

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """Manages active WebSocket connections and broadcasts messages thread-safely."""

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the active asyncio loop from the main FastAPI thread."""
        self.loop = loop
        logger.info("WebSocketConnectionManager bound to asyncio event loop.")

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new connection and add it to the active pool."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected. Active connections: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a connection from the active pool."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket client disconnected. Active connections: %d", len(self.active_connections))

    def broadcast_sync(self, message: Dict[str, Any]) -> None:
        """Broadcast a JSON message to all connected clients from a synchronous thread.

        Schedules the async transmission on the main event loop thread-safely.
        """
        if not self.active_connections:
            return

        if self.loop is None:
            logger.warning("Cannot broadcast: asyncio event loop is not set.")
            return

        async def _send_to_all():
            for connection in list(self.active_connections):
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.debug("Failed to send json to WebSocket client: %s. Disconnecting.", e)
                    self.disconnect(connection)

        # Submit the send task to the main event loop
        asyncio.run_coroutine_threadsafe(_send_to_all(), self.loop)


class WebSocketTelemetryExporter(TelemetryExporter):
    """Telemetry exporter that broadcasts events over WebSockets."""

    def __init__(self, manager: WebSocketConnectionManager) -> None:
        self.manager = manager

    def export_frame_metrics(self, source_id: str, metrics: Dict[str, Any]) -> None:
        """Serialize and broadcast frame-level metrics."""
        self.manager.broadcast_sync({
            "type": "frame_metrics",
            "source_id": source_id,
            "data": metrics,
        })

    def export_system_metrics(self, metrics: Dict[str, Any]) -> None:
        """Serialize and broadcast system/hardware metrics."""
        self.manager.broadcast_sync({
            "type": "system_metrics",
            "data": metrics,
        })

    def export_incident(self, incident: Dict[str, Any]) -> None:
        """Serialize and broadcast incident events."""
        self.manager.broadcast_sync({
            "type": "incident",
            "data": incident,
        })


# Create global instances of connection manager and exporter
websocket_manager = WebSocketConnectionManager()
websocket_exporter = WebSocketTelemetryExporter(websocket_manager)

