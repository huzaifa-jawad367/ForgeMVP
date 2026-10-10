import unittest
import numpy as np
import os
import shutil
import cv2
from fastapi.testclient import TestClient

from app.incidents.evidence_manager import EvidenceManager
from main import create_app
from app.storage.database import init_db, get_session, Incident, store_incident, get_audit_logs
from app.schema.contracts import AuditAction
from app.incidents.trigger_rules import IncidentType
from datetime import datetime, timezone

class TestROIAudit(unittest.TestCase):
    def setUp(self):
        init_db()
        self.app = create_app()
        self.client = TestClient(self.app)
        self.output_dir = "tests/test_outputs"
        os.makedirs(self.output_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)

    def test_roi_cropping_dimensions(self):
        manager = EvidenceManager(buffer_size=10, pre_incident_offset=1)

        # 100x100 white frame
        frame_pre = np.ones((100, 100, 3), dtype=np.uint8) * 255
        frame_inc = np.ones((100, 100, 3), dtype=np.uint8) * 255

        manager.push_frame(frame_pre, 1, 1000)
        manager.push_frame(frame_inc, 2, 1100)

        metrics = {
            "detections": [
                {"bbox": [20, 20, 40, 40]} # width=20, height=20, 20% margin = 4.
                # Crop should be from (16, 16) to (44, 44), size 28x28
            ]
        }

        result = manager.capture_evidence(
            incident_id="test_roi_inc",
            incident_frame_index=2,
            metrics_snapshot=metrics,
            output_dir=self.output_dir
        )

        inc_path = result["incident_frame_path"]
        pre_path = result["pre_frame_path"]

        self.assertTrue(os.path.exists(inc_path))
        self.assertTrue(os.path.exists(pre_path))

        img_inc = cv2.imread(inc_path)
        img_pre = cv2.imread(pre_path)

        self.assertEqual(img_inc.shape, (28, 28, 3))
        self.assertEqual(img_pre.shape, (28, 28, 3))

    def test_audit_logging_on_evidence_access(self):
        import uuid
        incident_id = f"test_audit_inc_id_{uuid.uuid4().hex[:8]}"
        with get_session() as session:
            store_incident(session, {
                "id": incident_id,
                "incident_type": "blur_spike",
                "start_time": datetime.now(timezone.utc),
                "start_frame": 1,
                "status": "active",
                "evidence_path": self.output_dir
            })

        resp = self.client.get(f"/api/incidents/{incident_id}/evidence", headers={"User-Agent": "test-agent"})
        self.assertEqual(resp.status_code, 200)

        resp_audit = self.client.get(f"/api/audit-logs?incident_id={incident_id}")
        self.assertEqual(resp_audit.status_code, 200)
        logs = resp_audit.json()

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["incident_id"], incident_id)
        self.assertEqual(logs[0]["action"], "VIEW")
        self.assertEqual(logs[0]["user_agent"], "test-agent")

if __name__ == '__main__':
    unittest.main()
