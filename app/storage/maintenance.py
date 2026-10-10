import os
import time
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.storage.database import FrameMetric, SystemMetric, Incident, get_session, engine

logger = logging.getLogger(__name__)

def purge_expired_data(db_session: Session, telemetry_ttl_hours: float = 72.0, incident_ttl_days: float = 30.0) -> Dict[str, int]:
    now = datetime.now(timezone.utc)
    telemetry_threshold = now - timedelta(hours=telemetry_ttl_hours)
    incident_threshold = now - timedelta(days=incident_ttl_days)

    # 1. Delete expired telemetry
    fm_purged = db_session.query(FrameMetric).filter(FrameMetric.created_at < telemetry_threshold).delete(synchronize_session=False)
    sm_purged = db_session.query(SystemMetric).filter(SystemMetric.created_at < telemetry_threshold).delete(synchronize_session=False)
    metrics_purged = fm_purged + sm_purged

    # 2. Delete expired resolved incidents
    incidents_to_delete = db_session.query(Incident).filter(
        Incident.created_at < incident_threshold,
        Incident.status == "resolved"
    ).all()

    incidents_purged = 0
    for incident in incidents_to_delete:
        if incident.evidence_path and os.path.exists(incident.evidence_path):
            try:
                os.remove(incident.evidence_path)
            except Exception as e:
                logger.warning(f"Failed to delete evidence file {incident.evidence_path}: {e}")
        db_session.delete(incident)
        incidents_purged += 1

    db_session.commit()

    # 3. VACUUM
    # Execute outside transaction
    try:
        with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
            conn.execute(text("VACUUM"))
    except Exception as e:
        logger.error(f"Failed to vacuum database: {e}")

    return {"metrics_purged": metrics_purged, "incidents_purged": incidents_purged}

class MaintenanceWorker:
    def __init__(self, interval_seconds: float = 3600.0):
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._thread is not None:
            self._stop_event.set()
            self._thread.join()
            self._thread = None

    def _run(self):
        while not self._stop_event.is_set():
            try:
                with get_session() as session:
                    purged = purge_expired_data(session)
                    if purged["metrics_purged"] > 0 or purged["incidents_purged"] > 0:
                        logger.info(f"Purged expired data: {purged}")
            except Exception as e:
                logger.error(f"Error during automated maintenance: {e}")

            # Sleep in increments to allow fast shutdown
            for _ in range(int(self.interval_seconds)):
                if self._stop_event.is_set():
                    break
                time.sleep(1)
