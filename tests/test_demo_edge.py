"""Exact-cohort demo controls, durable queue failure paths and replay identity."""
import io
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.edge.buffer import EdgeBuffer, EdgePayload
from app.edge.demo import DemoController
from app.edge.demo_api import create_demo_app
from app.edge.service import EdgeService
from app.schema.contracts import PriorityTier


class Response(io.BytesIO):
    status = 200


def acknowledge(request, **kwargs):
    package = json.loads(request.data)
    return Response(json.dumps(dict(status='ack', edge_id=package['edge_id'], batch_id=package['batch_id'],
                                    frames_ingested=len(package['frames']), frames_deduplicated=0,
                                    acknowledged_payload_ids=[p['payload_id'] for p in package['frames']], controls={})).encode())


class DemoEdgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.model_patch = patch.object(EdgeService, '_init_model')
        self.model_patch.start()
        self.addCleanup(self.model_patch.stop)
        self.addCleanup(self.tmp.cleanup)
        self.service = EdgeService(db_path=str(Path(self.tmp.name) / 'edge.db'))
        self.service.demo = DemoController(self.service)

    def payload(self, name):
        return EdgePayload(payload_id=name, boot_id=self.service.boot_id)

    def test_offline_exact_cohort_and_ongoing_capture(self):
        s = self.service
        s.admit_payload(self.payload('before'))
        s.demo.start_run(2)
        for name in ('run-1', 'run-2'):
            s.admit_payload(self.payload(name))
        with patch('urllib.request.urlopen', side_effect=acknowledge) as transport:
            s._sync_once()
            transport.assert_not_called()
            self.assertEqual(s.demo.snapshot()['run']['pending_count'], 2)
            s.demo.set_paused(False)
            s.admit_payload(self.payload('after'))
            s._sync_once()
        run = s.demo.snapshot()['run']
        self.assertEqual(run['payload_ids'], ['run-1', 'run-2'])
        self.assertEqual(run['acknowledged_count'], 2)
        self.assertEqual(run['phase'], 'complete')
        self.assertEqual(s.buffer.get_stats()['persisted_rows'], 0)

    def test_completed_result_is_stable_after_later_storage_errors(self):
        s = self.service
        s.demo.start_run(2)
        s.admit_payload(self.payload('completed'))
        s.demo.set_paused(False)
        with patch('urllib.request.urlopen', side_effect=acknowledge):
            s._sync_once()
        completed = s.demo.snapshot()['run']
        s.buffer.persistence_errors += 1
        with patch('app.edge.demo.time.monotonic', return_value=time.monotonic() + 100):
            later = s.demo.snapshot()['run']
        self.assertEqual(later['phase'], 'complete')
        self.assertEqual(later['elapsed_seconds'], completed['elapsed_seconds'])
        self.assertEqual(later['persistence_errors'], 0)

    def test_auto_reconnect_without_browser(self):
        s = self.service
        s.demo.start_run(2)
        s.admit_payload(self.payload('automatic'))
        s.demo._deadline = time.monotonic() + .02
        s.demo.start_monitor()
        self.addCleanup(s.stop)
        deadline = time.monotonic() + 2
        while s._sync_paused and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertFalse(s._sync_paused)
        self.assertTrue(s.demo.snapshot()['run']['capture_closed'])
        with patch('urllib.request.urlopen', side_effect=acknowledge):
            s._sync_once()
        self.assertEqual(s.demo.snapshot()['run']['phase'], 'complete')

    def test_pause_barrier_waits_for_inflight_and_excludes_previous_ack(self):
        s = self.service
        s.admit_payload(self.payload('preexisting'))
        entered, release, paused = threading.Event(), threading.Event(), threading.Event()
        def slow_ack(request, **kwargs):
            entered.set()
            release.wait(2)
            return acknowledge(request)
        def start():
            s.demo.start_run(2)
            paused.set()
        with patch('urllib.request.urlopen', side_effect=slow_ack):
            sync_thread = threading.Thread(target=s._sync_once)
            sync_thread.start()
            self.assertTrue(entered.wait(1))
            pause_thread = threading.Thread(target=start)
            pause_thread.start()
            time.sleep(.03)
            self.assertFalse(paused.is_set())
            # Admission remains possible while a command waits for an ACK.
            s.admit_payload(self.payload('during-barrier'))
            release.set()
            sync_thread.join(2)
            pause_thread.join(2)
        self.assertTrue(paused.is_set())
        s.admit_payload(self.payload('cohort'))
        self.assertEqual(s.demo.snapshot()['run']['payload_ids'], ['cohort'])

    def test_invalid_ack_and_timeout_retain_retryable_payload(self):
        s = self.service
        s.admit_payload(self.payload('kept'))
        for result in (Response(b'{"status":"ack"}'), TimeoutError('lost ACK')):
            with patch('urllib.request.urlopen', side_effect=result if isinstance(result, Exception) else None,
                       return_value=result):
                s._sync_once()
            self.assertEqual(s.buffer.size(), 1)
            self.assertTrue(s.demo.snapshot()['sync']['last_error'])
        with patch('urllib.request.urlopen', side_effect=acknowledge):
            s._sync_once()
        self.assertEqual(s.buffer.size(), 0)
        self.assertEqual(s.demo.snapshot()['sync']['total_retries'], 2)

    def test_insert_and_delete_failures_do_not_publish_memory_changes(self):
        s = self.service
        s.demo.start_run(2)
        with patch('app.edge.buffer.sqlite3.connect', side_effect=sqlite3.OperationalError('disk failure')):
            self.assertFalse(s.admit_payload(self.payload('rejected')))
        self.assertEqual(s.buffer.size(), 0)
        self.assertEqual(s.demo.snapshot()['run']['rejected_payload_ids'], ['rejected'])
        s.admit_payload(self.payload('retained'))
        with patch('app.edge.buffer.sqlite3.connect', side_effect=sqlite3.OperationalError('delete failure')):
            self.assertEqual(s.buffer.ack_batch(['retained']), 0)
        self.assertEqual(s.buffer.size(), 1)
        self.assertEqual(s.buffer.total_synced, 0)
        self.assertEqual(s.buffer.get_stats()['persisted_rows'], 1)
        s.demo.set_paused(False)
        self.assertEqual(s.demo.snapshot()['run']['phase'], 'failed')

    def test_eviction_insert_rollback_preserves_old_payload(self):
        buffer = EdgeBuffer(max_size=2, db_path=str(Path(self.tmp.name) / 'small.db'))
        self.assertTrue(buffer.push(EdgePayload(payload_id='old')))
        with patch('app.edge.buffer.json.dumps', side_effect=ValueError('serialization failure')):
            self.assertFalse(buffer.push(EdgePayload(payload_id='new')))
        self.assertEqual(buffer.peek_batch()[0].payload_id, 'old')
        self.assertEqual(buffer.get_stats()['persisted_rows'], 1)
        self.assertEqual(buffer.total_enqueued, 1)

    def test_restart_replay_preserves_original_boot_and_payload(self):
        old = self.service
        old.admit_payload(self.payload('original'))
        restarted = EdgeService(db_path=old.buffer.db_path)
        self.assertNotEqual(restarted.boot_id, old.boot_id)
        packages = []
        def capture(request, **kwargs):
            packages.append(json.loads(request.data))
            return acknowledge(request)
        with patch('urllib.request.urlopen', side_effect=capture):
            restarted._sync_once()
        self.assertEqual(packages[0]['boot_id'], old.boot_id)
        self.assertEqual(packages[0]['frames'][0]['boot_id'], old.boot_id)
        self.assertEqual(packages[0]['frames'][0]['payload_id'], 'original')
        self.assertEqual(restarted.buffer.size(), 0)

    def test_evicted_and_rejected_cohorts_cannot_claim_success(self):
        s = self.service
        s.buffer.max_size = 1
        s.demo.start_run(2)
        s.admit_payload(self.payload('evicted'))
        s.admit_payload(self.payload('replacement'))
        s.demo.set_paused(False)
        with patch('urllib.request.urlopen', side_effect=acknowledge):
            s._sync_once()
        run = s.demo.snapshot()['run']
        self.assertEqual(run['phase'], 'failed')
        self.assertEqual(run['evicted_payload_ids'], ['evicted'])
        self.assertEqual(run['acknowledged_payload_ids'], ['replacement'])
        s.demo.start_run(2)
        protected = self.payload('protected')
        protected.priority = PriorityTier.P0_INCIDENT
        self.assertTrue(s.admit_payload(protected))
        protected2 = self.payload('rejected')
        protected2.priority = PriorityTier.P0_INCIDENT
        self.assertFalse(s.admit_payload(protected2))
        s.demo.set_paused(False)
        self.assertEqual(s.demo.snapshot()['run']['rejected_payload_ids'], ['rejected'])

    def test_old_persistence_error_does_not_poison_new_experiment(self):
        s = self.service
        s.buffer.persistence_errors = 5
        s.demo.start_run(2)
        s.admit_payload(self.payload('new-run'))
        s.demo.set_paused(False)
        with patch('urllib.request.urlopen', side_effect=acknowledge):
            s._sync_once()
        run = s.demo.snapshot()['run']
        self.assertEqual(run['phase'], 'complete')
        self.assertEqual(run['persistence_errors'], 0)
        s.demo.start_run(2)
        s.admit_payload(self.payload('write-error'))
        s.demo.set_paused(False)
        with patch('urllib.request.urlopen', side_effect=acknowledge), patch.object(s.buffer, 'ack_batch', return_value=0):
            s.buffer.persistence_errors += 1
            s._sync_once()
        with patch('urllib.request.urlopen', side_effect=acknowledge):
            s._sync_once()
        self.assertEqual(s.demo.snapshot()['run']['phase'], 'failed')
        self.assertEqual(s.demo.snapshot()['run']['persistence_errors'], 1)

    def test_manual_pause_failsafe_and_bounded_ledgers(self):
        s = self.service
        s.demo.set_paused(True)
        self.assertLessEqual(s.demo._deadline - time.monotonic(), 60)
        with s._sync_condition:
            s.demo._deadline = time.monotonic() - 1
            s.demo._tick()
        self.assertFalse(s._sync_paused)
        for i in range(110):
            s.demo._event('bounded', str(i))
        self.assertEqual(len(s.demo.events), 100)
        s.demo.start_run(2)
        for i in range(1001):
            s.admit_payload(self.payload(f'bounded-{i}'))
        run = s.demo.snapshot()['run']
        self.assertTrue(run['capture_closed'])
        self.assertEqual(len(run['payload_ids']), 1000)
        self.assertFalse(s._sync_paused)

    def test_privacy_concurrency_is_bounded(self):
        client = TestClient(create_demo_app(self.service))
        entered, release = threading.Event(), threading.Event()
        results = []
        def process(*args):
            entered.set()
            release.wait(2)
            return {'persisted': False}
        def first_request():
            results.append(client.post('/api/demo/privacy', content=b'raw-image').status_code)
        with patch('app.edge.privacy_preview.process_privacy_preview', side_effect=process):
            first = threading.Thread(target=first_request)
            first.start()
            self.assertTrue(entered.wait(1))
            self.assertEqual(client.post('/api/demo/privacy', content=b'another-image').status_code, 429)
            release.set()
            first.join(2)
        self.assertEqual(results, [200])
        self.assertEqual(self.service.buffer.size(), 0)

    def test_api_origins_bounds_reset_and_validation(self):
        client = TestClient(create_demo_app(self.service))
        self.assertEqual(client.get('/api/demo/status', headers={'Origin': 'https://evil.example'}).status_code, 403)
        self.assertEqual(client.get('/api/demo/status', headers={'Origin': 'http://localhost:8000'}).status_code, 200)
        self.assertEqual(client.post('/api/demo/sync', json={'paused': 'false'}).status_code, 400)
        self.assertEqual(client.post('/api/demo/run', json={'offline_seconds': 90}).status_code, 400)
        self.assertEqual(client.post('/api/demo/run', json={'offline_seconds': 2}).status_code, 200)
        self.assertEqual(client.post('/api/demo/run', json={'offline_seconds': 2}).status_code, 409)
        self.service.admit_payload(self.payload('preserved'))
        result = client.post('/api/demo/reset').json()
        self.assertIsNone(result['run'])
        self.assertFalse(result['sync']['paused'])
        self.assertEqual(self.service.buffer.size(), 1)
        self.assertEqual(client.post('/api/demo/privacy', content=b'x' * (5 * 1024 * 1024 + 1)).status_code, 413)
        self.assertEqual(client.post('/api/demo/privacy', content=b'bad').status_code, 400)
        self.assertEqual(client.get('/api/demo/status').headers['cache-control'], 'no-store')


if __name__ == '__main__':
    unittest.main()
