import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.storage.database import Base, FrameMetric, SystemMetric, Incident
from app.storage.maintenance import purge_expired_data

class TestTTLMaintenance(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp()
        self.engine = create_engine(f"sqlite:///{self.temp_db_path}")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

        self.temp_evidence_fd, self.temp_evidence_path = tempfile.mkstemp()

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

        try:
            os.close(self.temp_evidence_fd)
        except OSError:
            pass

        if os.path.exists(self.temp_evidence_path):
            os.remove(self.temp_evidence_path)

    def test_purge_expired_data(self):
        with self.SessionLocal() as session:
            now = datetime.now(timezone.utc)

            # 1. Telemetry 73 hours ago (should be deleted)
            fm_old = FrameMetric(
                source_id=1,
                frame_index=0,
                timestamp_ms=10.0,
                fps=10.0,
                mean_confidence=0.9,
                inference_time_ms=10.0,
                created_at=now - timedelta(hours=73)
            )
            sm_old = SystemMetric(
                cpu_percent=50.0,
                memory_percent=50.0,
                created_at=now - timedelta(hours=73)
            )

            # 2. Telemetry 10 hours ago (should be kept)
            fm_new = FrameMetric(
                source_id=1,
                frame_index=0,
                timestamp_ms=10.0,
                fps=10.0,
                mean_confidence=0.1,
                inference_time_ms=10.0,
                created_at=now - timedelta(hours=10)
            )
            sm_new = SystemMetric(
                cpu_percent=10.0,
                memory_percent=10.0,
                created_at=now - timedelta(hours=10)
            )

            # 3. Incident 31 days ago (should be deleted, evidence unlinked)
            inc_old_resolved = Incident(
                id="old_resolved_incident",
                incident_type="test",
                start_time=now - timedelta(days=32),
                start_frame=0,
                status="resolved",
                evidence_path=self.temp_evidence_path,
                created_at=now - timedelta(days=31)
            )

            # 4. Incident 31 days ago, but active (should be kept)
            inc_old_active = Incident(
                id="old_active_incident",
                incident_type="test",
                start_time=now - timedelta(days=32),
                start_frame=0,
                status="active",
                created_at=now - timedelta(days=31)
            )

            # 5. Incident 10 days ago, resolved (should be kept)
            inc_new_resolved = Incident(
                id="new_resolved_incident",
                incident_type="test",
                start_time=now - timedelta(days=11),
                start_frame=0,
                status="resolved",
                created_at=now - timedelta(days=10)
            )

            session.add_all([fm_old, sm_old, fm_new, sm_new, inc_old_resolved, inc_old_active, inc_new_resolved])
            session.commit()

            # Execute purge
            from unittest.mock import patch
            with patch("app.storage.maintenance.engine", self.engine):
                result = purge_expired_data(session)

            # Verify results
            self.assertEqual(result["metrics_purged"], 2)
            self.assertEqual(result["incidents_purged"], 1)

            # Verify database contents
            self.assertEqual(session.query(FrameMetric).count(), 1)
            self.assertEqual(session.query(SystemMetric).count(), 1)

            incidents = session.query(Incident).all()
            self.assertEqual(len(incidents), 2)
            self.assertNotIn("old_resolved_incident", [i.id for i in incidents])

            # Verify file deletion
            self.assertFalse(os.path.exists(self.temp_evidence_path))

if __name__ == "__main__":
    unittest.main()
