"""Bounded process-local experiment ledger; transport and capture share one barrier."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import threading
import time
import uuid


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class DemoController:
    def __init__(self, service):
        self.service = service
        self._commands = threading.Lock()
        self.run = None
        self.events = deque(maxlen=100)
        self.samples = deque(maxlen=300)
        self._event_id = 0
        self._deadline = None
        self._started = None
        self._recovery_started = None
        self._last_sample = 0.
        self._admitted = set()
        self._rejected = set()
        self._evicted = set()
        self._acknowledged = set()
        self._thread = None
        self._persistence_error_baseline = 0

    def start_monitor(self):
        if not self._thread or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._monitor, daemon=True, name="edge-demo-observer")
            self._thread.start()

    def _monitor(self):
        while not self.service._shutdown_event.wait(.2):
            with self.service._sync_condition:
                self._tick()

    def _event(self, kind, message):
        self._event_id += 1
        self.events.append(dict(id=self._event_id, at=utc_now(), type=kind, message=message))

    def _tick(self):
        now = time.monotonic()
        if self._deadline is not None and now >= self._deadline:
            self._resume()
        if now - self._last_sample >= 1:
            stats = self.service.buffer.get_stats()
            self.samples.append(dict(at=utc_now(), queue_size=stats['queue_size'],
                                     total_synced=stats['total_synced'], total_dropped=stats['total_dropped'],
                                     paused=self.service._sync_paused))
            self._last_sample = now

    def _pause_barrier(self):
        self.service._sync_paused = True
        while self.service._sync_in_flight:
            self.service._sync_condition.wait(timeout=.25)

    def start_run(self, offline_seconds=10):
        if isinstance(offline_seconds, bool) or not isinstance(offline_seconds, (int, float)) or not 2 <= offline_seconds <= 30:
            raise ValueError("offline_seconds must be between 2 and 30")
        with self._commands, self.service._sync_condition:
            if self.run and self.run['phase'] in ('offline', 'recovering'):
                raise RuntimeError("An experiment is already active")
            self._deadline = None
            self._pause_barrier()
            self._admitted, self._rejected, self._evicted, self._acknowledged = set(), set(), set(), set()
            self._persistence_error_baseline = self.service.buffer.persistence_errors
            self._started = time.monotonic()
            self._recovery_started = None
            self._deadline = self._started + offline_seconds
            self.run = dict(id=str(uuid.uuid4()), phase='offline', started_at=utc_now(),
                            offline_seconds=offline_seconds, capture_closed=False)
            self._event('run_started', 'Sync paused; capture continues into the durable queue.')
            return self.snapshot()

    def set_paused(self, paused):
        with self._commands, self.service._sync_condition:
            if paused:
                previous_deadline = self._deadline
                self._deadline = None
                self._pause_barrier()
                if self.run and self.run['phase'] == 'offline':
                    self._deadline = previous_deadline
                else:
                    self._deadline = time.monotonic() + 60
                self._event('sync_paused', 'Sync paused; capture continues. Automatic reconnect is enabled.')
            else:
                self._resume()
            return self.snapshot()

    def _resume(self):
        self.service._sync_paused = False
        self._deadline = None
        if self.run and self.run['phase'] == 'offline':
            self.run['capture_closed'] = True
            self.run['phase'] = 'recovering'
            self._recovery_started = time.monotonic()
            self._settle()
        self._event('sync_resumed', 'Sync restored; queued payloads are eligible for delivery.')
        self.service._sync_condition.notify_all()

    def reset(self):
        with self._commands, self.service._sync_condition:
            was_active = bool(self.run and self.run['phase'] in ('offline', 'recovering'))
            self._resume()
            self.run = None
            self.events.clear()
            self.samples.clear()
            if was_active:
                self._event('run_cancelled', 'Experiment cancelled. Queued data remains intact.')
            self._event('reset', 'Presentation reset; sync enabled and stored records preserved.')
            return self.snapshot()

    def captured(self, payload_id, admitted, evicted):
        # Called under the service lock, atomically with buffer admission.
        if not self.run:
            return
        self._evicted.update(self._admitted.intersection(evicted))
        if self.run['phase'] == 'offline':
            (self._admitted if admitted else self._rejected).add(payload_id)
            if len(self._admitted) + len(self._rejected) >= 1000:
                self._event('cohort_limit', 'Capture window sealed at 1000 payload identities.')
                self._resume()
        self._settle()

    def acknowledged(self, payload_ids):
        if self.run:
            self._acknowledged.update(self._admitted.intersection(payload_ids))
            self._settle()

    def _settle(self):
        if not self.run or not self.run['capture_closed'] or self.run['phase'] not in ('recovering', 'failed'):
            return
        if self._evicted or self._rejected or self.service.buffer.persistence_errors > self._persistence_error_baseline:
            self.run['phase'] = 'failed'
            self.run.setdefault('elapsed_seconds', time.monotonic() - self._started)
            self.run.setdefault('persistence_errors', self.service.buffer.persistence_errors - self._persistence_error_baseline)
        elif self._admitted <= self._acknowledged:
            self.run['phase'] = 'complete'
            self.run['elapsed_seconds'] = time.monotonic() - self._started
            self.run['persistence_errors'] = self.service.buffer.persistence_errors - self._persistence_error_baseline
            self._event('run_acknowledged', 'All admitted run payloads acknowledged. Verify backend reconciliation.')
            self.run['recovery_seconds'] = time.monotonic() - self._recovery_started

    def snapshot(self):
        with self.service._sync_condition:
            self._tick()
            s = self.service
            now = time.monotonic()
            buffer_stats = s.buffer.get_stats()
            self._settle()
            run = None
            if self.run:
                pending = self._admitted - self._acknowledged - self._evicted
                run = dict(self.run, persistence_errors=self.run.get('persistence_errors', self.service.buffer.persistence_errors - self._persistence_error_baseline),
                           remaining_offline_seconds=max(0, self._deadline - now) if self._deadline else 0,
                           captured_count=len(self._admitted) + len(self._rejected), admitted_count=len(self._admitted),
                           rejected_count=len(self._rejected), evicted_count=len(self._evicted),
                           acknowledged_count=len(self._acknowledged), pending_count=len(pending),
                           payload_ids=sorted(self._admitted), acknowledged_payload_ids=sorted(self._acknowledged),
                           pending_payload_ids=sorted(pending), rejected_payload_ids=sorted(self._rejected),
                           evicted_payload_ids=sorted(self._evicted), elapsed_seconds=self.run.get('elapsed_seconds', now - self._started),
                           recovery_seconds=self.run.get('recovery_seconds'))
            alive = bool(s._inference_thread and s._inference_thread.is_alive())
            return dict(edge_id=s.edge_id, boot_id=s.boot_id, source_id=s.source_input,
                        observed_at=utc_now(), is_running=not s._shutdown_event.is_set() and alive,
                        capture_alive=alive, inference_alive=alive,
                        capture_age_seconds=now - s._last_capture_mono if s._last_capture_mono else None,
                        frames_processed=s.frames_processed, fps=s._observed_fps, inference_time_ms=s._inference_time_ms,
                        sync=dict(paused=s._sync_paused, connected=s.is_connected, in_flight=s._sync_in_flight,
                                  last_ack_age_seconds=now - s._last_ack_mono if s._last_ack_mono else None,
                                  round_trip_ms=s._round_trip_ms, total_attempts=s._sync_attempts,
                                  total_retries=s._sync_retries, total_deduplicated=s._sync_deduplicated,
                                  last_error=s._sync_error,
                                  next_retry_seconds=max(0, s._next_sync_mono - now) if s._sync_error and not s._sync_paused else None),
                        buffer=buffer_stats, run=run, events=list(self.events), samples=list(self.samples))
