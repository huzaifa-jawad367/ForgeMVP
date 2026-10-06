# FORGE — Jules Autonomous PR Prompts Pack

> **Purpose:** Pre-packaged, copy-paste-ready task prompts for dispatching each PR to Google's Jules agent.
> **Reference Specs:** [`docs/MVP_SPEC.md`](MVP_SPEC.md), [`docs/ARCHITECTURE.md`](ARCHITECTURE.md), [`ROADMAP.md`](../ROADMAP.md)

---

## Global Architectural Constraints & Testing Instructions

Every task prompt below contains the shared architectural lock to ensure parallel executions do not drift:

```text
CRITICAL ARCHITECTURAL CONSTRAINTS: 
- Do NOT invent new column names, JSON payload keys, or failure strings.
  Import existing constants from app.schema.contracts (FailureSubsystem, PriorityTier, AuditAction, LifecycleTimestamps, SCHEMA_VERSION)
  and app.storage.database (FrameMetric, Incident, AuditLog, get_session, engine). 
- Do NOT run live EfficientAD inference or download the VisA dataset.
  Use synthetic image arrays (e.g. np.zeros((256, 256, 3), dtype=np.uint8)) and mocked inference result dictionaries. 
- Verify tests pass: Run python -m unittest tests/test_three_services.py and add dedicated unit tests for your changes. 

Testing & Mocking Instructions for Jules: 
- Do NOT run live EfficientAD inference or download the VisA dataset. 
- Rely on mocked frames and simulated inference results: 
  - Use synthetic image frames (e.g. np.zeros((256, 256, 3), dtype=np.uint8) or test fixtures). 
  - For inference outputs, mock or stub the detection dictionaries and anomaly scores (e.g. {"anomaly_score": 0.85, "is_anomalous": True, "detections": [...]}). 
- Validation Command: 
  python -m unittest tests/test_three_services.py [your_new_test_file.py]
- Ensure all tests run purely on CPU, in-memory or SQLite temporary files, and complete within seconds without external network dependencies. 

⚠️ ARCHITECTURAL CONSTRAINT: 
- Do NOT invent new database column names, JSON payload keys, or error/failure strings. 
- Import the canonical constants from app/schema/contracts.py and app/storage/database.py. 
- All failure attribution types must match FailureSubsystem. All priority classes must match PriorityTier.
```

---

# ⚡ STAGE 1 (PARALLEL FOUNDATIONS)

---

## 📋 PR 1.1: Schema v1.0.0 & Nanosecond Lifecycle Timestamps

```markdown
Task: PR 1.1 — Schema v1.0.0 & Nanosecond Lifecycle Timestamps

CRITICAL ARCHITECTURAL CONSTRAINTS:
Do NOT invent new column names, JSON payload keys, or failure strings. Import existing constants from app.schema.contracts (FailureSubsystem, PriorityTier, AuditAction, LifecycleTimestamps, SCHEMA_VERSION) and app.storage.database (FrameMetric, Incident, AuditLog).
Do NOT run live EfficientAD inference or download the VisA dataset. Use synthetic image arrays (e.g. np.zeros((256, 256, 3), dtype=np.uint8)) and mocked inference result dictionaries.
Verify tests pass: Run python -m unittest tests/test_three_services.py and add dedicated unit tests for your changes.

Testing & Mocking Instructions for Jules:
Do NOT run live EfficientAD inference or download the VisA dataset.
Rely on mocked frames and simulated inference results:
Use synthetic image frames (e.g. np.zeros((256, 256, 3), dtype=np.uint8) or test fixtures).
For inference outputs, mock or stub the detection dictionaries and anomaly scores (e.g. {"anomaly_score": 0.85, "is_anomalous": True, "detections": [...]}).
Validation Command:
Run fast unit and integration tests using:
python -m unittest tests/test_three_services.py tests/test_schema_v1.py
Ensure all tests run purely on CPU, in-memory or SQLite temporary files, and complete within seconds without external network dependencies.

⚠️ ARCHITECTURAL CONSTRAINT:
Do NOT invent new database column names, JSON payload keys, or error/failure strings.
Import the canonical constants from app/schema/contracts.py and app/storage/database.py.
All failure attribution types must match FailureSubsystem. All priority classes must match PriorityTier.

OBJECTIVE & DETAILED SPECIFICATION:
Upgrade the edge sync payload and backend FastAPI route to Schema v1.0.0 with monotonic nanosecond time semantics as specified in docs/MVP_SPEC.md (Section 4.1).

TARGET FILES:
- app/api/routes.py (Update EdgeSyncBatch Pydantic schema)
- app/edge/service.py (Update EdgeService batch generation)
- app/edge/buffer.py (Preserve payload timestamps)
- tests/test_schema_v1.py (New test file)

DELIVERABLES:
1. In app/edge/service.py:
   - Generate a persistent UUID `boot_id` once at EdgeService __init__.
   - Increment a strictly monotonic `sequence_number: int` per captured frame.
   - Record nanosecond monotonic clocks via `time.monotonic_ns()`:
     - captured_at_ns: when frame grabbed
     - inference_started_at_ns: before model call
     - inference_completed_at_ns: after model call
     - queued_at_ns: when added to EdgeBuffer
     - transmitted_at_ns: when HTTP POST initiated
2. In app/api/routes.py:
   - Update `EdgeSyncBatch` to require:
     - schema_version: str (default SCHEMA_VERSION = "1.0.0")
     - boot_id: str
     - sequence_range: Dict[str, int] (e.g. {"start": int, "end": int})
     - transmitted_at_ms: float
     - frames: List[Dict[str, Any]] containing "timestamps" (LifecycleTimestamps)
   - When received, populate `received_at_ns` in the batch context.
3. Write `tests/test_schema_v1.py`:
   - Validate payload schema compliance against v1.0.0.
   - Assert all duration transitions (inference_completed_at_ns - inference_started_at_ns, etc.) are strictly positive (>= 0).
```

---

## 📋 PR 1.2: Backend Unique Index & Idempotent Ingestion Engine

```markdown
Task: PR 1.2 — Backend Unique Index & Idempotent Ingestion Engine

CRITICAL ARCHITECTURAL CONSTRAINTS:
Do NOT invent new column names, JSON payload keys, or failure strings. Import existing constants from app.schema.contracts (FailureSubsystem, PriorityTier, AuditAction, LifecycleTimestamps) and app.storage.database (FrameMetric, Incident, AuditLog).
Do NOT run live EfficientAD inference or download the VisA dataset. Use synthetic image arrays (e.g. np.zeros((256, 256, 3), dtype=np.uint8)) and mocked inference result dictionaries.
Verify tests pass: Run python -m unittest tests/test_three_services.py and add dedicated unit tests for your changes.

Testing & Mocking Instructions for Jules:
Do NOT run live EfficientAD inference or download the VisA dataset.
Rely on mocked frames and simulated inference results:
Use synthetic image frames (e.g. np.zeros((256, 256, 3), dtype=np.uint8) or test fixtures).
For inference outputs, mock or stub the detection dictionaries and anomaly scores (e.g. {"anomaly_score": 0.85, "is_anomalous": True, "detections": [...]}).
Validation Command:
Run fast unit and integration tests using:
python -m unittest tests/test_three_services.py tests/test_idempotent_ingest.py
Ensure all tests run purely on CPU, in-memory or SQLite temporary files, and complete within seconds without external network dependencies.

⚠️ ARCHITECTURAL CONSTRAINT:
Do NOT invent new database column names, JSON payload keys, or error/failure strings.
Import the canonical constants from app/schema/contracts.py and app/storage/database.py.
All failure attribution types must match FailureSubsystem. All priority classes must match PriorityTier.

OBJECTIVE & DETAILED SPECIFICATION:
Implement idempotent frame ingestion on the backend to prevent duplicate rows when network ACKs are dropped or batches are retried (docs/MVP_SPEC.md Section 2.2-B).

TARGET FILES:
- app/storage/database.py (Add idempotent insert helper or query filter)
- app/api/routes.py (Update edge_sync response with dedup metrics)
- main.py (Update process_edge_sync_batch)
- tests/test_idempotent_ingest.py (New test file)

DELIVERABLES:
1. In app/storage/database.py:
   - Implement `store_frame_metric_idempotent(session, metric_data) -> Tuple[Optional[FrameMetric], bool]`:
     - Checks if a record with `(source_id, boot_id, sequence_number)` already exists when boot_id is non-empty.
     - If exists, return (existing_record, False).
     - If not, insert and return (new_record, True).
2. In main.py (`process_edge_sync_batch`):
   - Record `persisted_at_ns` before database commit.
   - Track `ingested_count` and `deduplicated_count`.
   - Only feed `IncidentEngine` and increment `PIPELINE_STATE["frames_processed"]` if the frame is NOT a duplicate.
3. In app/api/routes.py:
   - Return `"frames_ingested": ingested_count` and `"frames_deduplicated": deduplicated_count` in `/api/edge/sync` HTTP 200 response.
4. Write `tests/test_idempotent_ingest.py`:
   - Send an identical batch of 20 frames 3 consecutive times to `process_edge_sync_batch`.
   - Assert database contains exactly 20 records (0 duplicates).
   - Assert response returns `frames_deduplicated == 20` on retries.
```

---

## 📋 PR 2.1: 7-Subsystem Root-Cause Failure Attribution Engine

```markdown
Task: PR 2.1 — 7-Subsystem Root-Cause Failure Attribution Engine

CRITICAL ARCHITECTURAL CONSTRAINTS:
Do NOT invent new column names, JSON payload keys, or failure strings. Import existing constants from app.schema.contracts (FailureSubsystem, PriorityTier, AuditAction, LifecycleTimestamps) and app.storage.database (FrameMetric, Incident, AuditLog).
Do NOT run live EfficientAD inference or download the VisA dataset. Use synthetic image arrays (e.g. np.zeros((256, 256, 3), dtype=np.uint8)) and mocked inference result dictionaries.
Verify tests pass: Run python -m unittest tests/test_three_services.py and add dedicated unit tests for your changes.

Testing & Mocking Instructions for Jules:
Do NOT run live EfficientAD inference or download the VisA dataset.
Rely on mocked frames and simulated inference results:
Use synthetic image frames (e.g. np.zeros((256, 256, 3), dtype=np.uint8) or test fixtures).
For inference outputs, mock or stub the detection dictionaries and anomaly scores (e.g. {"anomaly_score": 0.85, "is_anomalous": True, "detections": [...]}).
Validation Command:
Run fast unit and integration tests using:
python -m unittest tests/test_three_services.py tests/test_failure_attribution.py
Ensure all tests run purely on CPU, in-memory or SQLite temporary files, and complete within seconds without external network dependencies.

⚠️ ARCHITECTURAL CONSTRAINT:
Do NOT invent new database column names, JSON payload keys, or error/failure strings.
Import the canonical constants from app/schema/contracts.py and app/storage/database.py.
All failure attribution types must match FailureSubsystem. All priority classes must match PriorityTier.

OBJECTIVE & DETAILED SPECIFICATION:
Implement rule heuristics in the Incident Engine to attribute detected anomalies to one of the 7 failure subsystems defined in docs/MVP_SPEC.md (Section 2.3).

TARGET FILES:
- app/incidents/incident_engine.py
- app/incidents/trigger_rules.py
- tests/test_failure_attribution.py (New test file)

DELIVERABLES:
1. In app/incidents/incident_engine.py and trigger_rules.py:
   - Implement root-cause classification logic returning a tuple:
     `(subsystem_attribution: FailureSubsystem, root_cause_reason: str)`
   - Implement the 7 exact heuristics from MVP_SPEC.md Section 2.3:
     1. CAMERA_DISCONNECT: fps == 0 for > 3.0s while pipeline is active.
     2. OPTICAL_DEFOCUS: Anomaly score > 0.50 correlated with blur_score < blur_threshold (defocus blur collapse).
     3. OPTICAL_SENSOR_NOISE: Anomaly score > 0.50 correlated with noise_score > noise_threshold.
     4. ENVIRONMENTAL_LIGHTING: brightness < min_brightness (lighting drop).
     5. MODEL_INFERENCE_STALL: inference_time_ms > 3x baseline while CPU/GPU load is normal (< 70%).
     6. HARDWARE_GPU_EXHAUSTION: GPU utilization sustained >= 98% or gpu_temperature >= 85°C.
     7. NETWORK_PARTITION: Edge queue growing continuously with ack_age > 10.0s.
2. In app/incidents/incident_engine.py:
   - When an incident is created, populate `subsystem_attribution` and `root_cause_reason` in the returned Incident object.
   - Include `subsystem_attribution` in telemetry export payloads.
3. Write `tests/test_failure_attribution.py`:
   - Unit tests feeding synthetic metric combinations for each of the 7 heuristics.
   - Assert that each failure mode produces the exact corresponding `FailureSubsystem` enum value.
```

---

## 📋 PR 2.2: Incident Dossier UI Presentation & Attribution Badge

```markdown
Task: PR 2.2 — Incident Dossier UI Presentation & Attribution Badge

CRITICAL ARCHITECTURAL CONSTRAINTS:
Do NOT invent new column names, JSON payload keys, or failure strings. Import existing constants from app.schema.contracts (FailureSubsystem, PriorityTier, AuditAction, LifecycleTimestamps) and app.storage.database (FrameMetric, Incident, AuditLog).
Do NOT run live EfficientAD inference or download the VisA dataset. Use synthetic image arrays (e.g. np.zeros((256, 256, 3), dtype=np.uint8)) and mocked inference result dictionaries.
Verify tests pass: Run python -m unittest tests/test_three_services.py and check frontend build if node/npm is available.

Testing & Mocking Instructions for Jules:
Do NOT run live EfficientAD inference or download the VisA dataset.
Rely on mocked frames and simulated inference results.
Validation Command:
Run fast unit and integration tests using:
python -m unittest tests/test_three_services.py
Ensure all tests run purely on CPU, in-memory or SQLite temporary files, and complete within seconds without external network dependencies.

⚠️ ARCHITECTURAL CONSTRAINT:
Do NOT invent new database column names, JSON payload keys, or error/failure strings.
Import the canonical constants from app/schema/contracts.py and app/storage/database.py.
All failure attribution types must match FailureSubsystem. All priority classes must match PriorityTier.

OBJECTIVE & DETAILED SPECIFICATION:
Update the React frontend dashboard incident components to display the root-cause subsystem attribution badge and lifecycle latency waterfall bar (docs/MVP_SPEC.md Section 5 Step 10).

TARGET FILES:
- dashboard/src/components/IncidentModal.jsx
- dashboard/src/components/IncidentFeed.jsx
- dashboard/src/App.css

DELIVERABLES:
1. In dashboard/src/components/IncidentModal.jsx:
   - Render a prominent root-cause attribution badge showing `subsystem_attribution` and `root_cause_reason`.
   - Color code badges:
     - Optical failures (Defocus, Noise, Light) -> Amber/Yellow
     - Hardware/Camera failures -> Red/Crimson
     - Network failures -> Orange
     - Model stall -> Purple/Cyan
   - Add a "Lifecycle Latency Waterfall" bar visualizing time spent in:
     Capture -> Inference -> Queue -> Wire Transport -> DB Persistence (using ns timestamps from evidence).
2. In dashboard/src/components/IncidentFeed.jsx:
   - Show a compact subsystem pill (e.g., "[OPTICAL: BLUR]", "[HARDWARE: GPU]") beside each incident item.
3. In dashboard/src/App.css:
   - Add responsive CSS styles for attribution badges and the latency waterfall bar.
```

---

## 📋 PR 4.1: Edge-Side Pre-Persistence Worker PII Redaction

```markdown
Task: PR 4.1 — Edge-Side Pre-Persistence Worker PII Redaction

CRITICAL ARCHITECTURAL CONSTRAINTS:
Do NOT invent new column names, JSON payload keys, or failure strings. Import existing constants from app.schema.contracts (FailureSubsystem, PriorityTier, AuditAction, LifecycleTimestamps, PrivacyPayload) and app.storage.database (FrameMetric, Incident, AuditLog).
Do NOT run live EfficientAD inference or download the VisA dataset. Use synthetic image arrays (e.g. np.zeros((256, 256, 3), dtype=np.uint8)) and mocked inference result dictionaries.
Verify tests pass: Run python -m unittest tests/test_three_services.py and add dedicated unit tests for your changes.

Testing & Mocking Instructions for Jules:
Do NOT run live EfficientAD inference or download the VisA dataset.
Rely on mocked frames and simulated inference results:
Use synthetic image frames (e.g. np.zeros((256, 256, 3), dtype=np.uint8) or test fixtures).
For inference outputs, mock or stub the detection dictionaries and anomaly scores (e.g. {"anomaly_score": 0.85, "is_anomalous": True, "detections": [...]}).
Validation Command:
Run fast unit and integration tests using:
python -m unittest tests/test_three_services.py tests/test_pii_redaction.py
Ensure all tests run purely on CPU, in-memory or SQLite temporary files, and complete within seconds without external network dependencies.

⚠️ ARCHITECTURAL CONSTRAINT:
Do NOT invent new database column names, JSON payload keys, or error/failure strings.
Import the canonical constants from app/schema/contracts.py and app/storage/database.py.
All failure attribution types must match FailureSubsystem. All priority classes must match PriorityTier.

OBJECTIVE & DETAILED SPECIFICATION:
Implement an in-memory worker PII redaction filter in OpenCV/NumPy executed immediately upon frame capture before any data touches the buffer or inference models (GDPR Art. 5/25 and Betriebsrat compliance, docs/MVP_SPEC.md Section 3.1).

TARGET FILES:
- app/edge/privacy.py (New module)
- app/edge/service.py (Hook redaction into ingest pipeline)
- tests/test_pii_redaction.py (New test file)

DELIVERABLES:
1. Create `app/edge/privacy.py`:
   - Implement `redact_worker_pii(image: np.ndarray, blur_kernel: int = 31) -> Tuple[np.ndarray, bool]`:
     - Detect potential human skin/hand/face regions using fast HSV / YCrCb skin-color thresholding in OpenCV or Haar cascades.
     - Apply heavy Gaussian blur (kernel >= 31) or solid black masking to the detected bounding boxes in memory.
     - Return the redacted image array and a boolean flag `was_redacted`.
     - Target execution time <= 15 ms on CPU.
2. In `app/edge/service.py`:
   - Pass captured frames through `redact_worker_pii` before inference and before pushing into `EdgeBuffer`.
   - Set `"privacy": {"pii_redacted": True, "redaction_method": "in_memory_gaussian_roi"}` in the frame payload.
3. Write `tests/test_pii_redaction.py`:
   - Test synthetic frame with a flesh-tone / skin-colored region.
   - Assert region is blurred/masked in output.
   - Assert processing latency overhead is <= 25 ms.
```

---

## 📋 PR 4.2: ROI-Only Evidence Cropping & Tamper-Evident Audit Log

```markdown
Task: PR 4.2 — ROI-Only Evidence Cropping & Tamper-Evident Audit Log

CRITICAL ARCHITECTURAL CONSTRAINTS:
Do NOT invent new column names, JSON payload keys, or failure strings. Import existing constants from app.schema.contracts (FailureSubsystem, PriorityTier, AuditAction, LifecycleTimestamps) and app.storage.database (FrameMetric, Incident, AuditLog, store_audit_log, get_audit_logs).
Do NOT run live EfficientAD inference or download the VisA dataset. Use synthetic image arrays (e.g. np.zeros((256, 256, 3), dtype=np.uint8)) and mocked inference result dictionaries.
Verify tests pass: Run python -m unittest tests/test_three_services.py and add dedicated unit tests for your changes.

Testing & Mocking Instructions for Jules:
Do NOT run live EfficientAD inference or download the VisA dataset.
Rely on mocked frames and simulated inference results:
Use synthetic image frames (e.g. np.zeros((256, 256, 3), dtype=np.uint8) or test fixtures).
For inference outputs, mock or stub the detection dictionaries and anomaly scores (e.g. {"anomaly_score": 0.85, "is_anomalous": True, "detections": [...]}).
Validation Command:
Run fast unit and integration tests using:
python -m unittest tests/test_three_services.py tests/test_roi_audit.py
Ensure all tests run purely on CPU, in-memory or SQLite temporary files, and complete within seconds without external network dependencies.

⚠️ ARCHITECTURAL CONSTRAINT:
Do NOT invent new database column names, JSON payload keys, or error/failure strings.
Import the canonical constants from app/schema/contracts.py and app/storage/database.py.
All failure attribution types must match FailureSubsystem. All priority classes must match PriorityTier.

OBJECTIVE & DETAILED SPECIFICATION:
Enforce data minimization by cropping incident evidence images to defect ROIs, and record immutable audit logs whenever incident evidence is accessed (docs/MVP_SPEC.md Section 3.2 & 3.5).

TARGET FILES:
- app/incidents/evidence_manager.py (Add ROI cropping)
- app/api/routes.py (Log audit entries on evidence endpoints)
- tests/test_roi_audit.py (New test file)

DELIVERABLES:
1. In app/incidents/evidence_manager.py:
   - When saving incident evidence snapshots to disk, crop peripheral background if defect bounding boxes exist, saving only the inspection target Region of Interest (ROI) with a 20% margin.
   - Discard full continuous conveyor background images.
2. In app/api/routes.py:
   - In `/api/incidents/{incident_id}/evidence` (GET) and any snapshot download route:
     - Record an entry in `audit_logs` using `store_audit_log(session, ...)`:
       - incident_id: incident_id
       - action: AuditAction.VIEW.value (or AuditAction.DOWNLOAD.value)
       - client_ip: request.client.host
       - user_agent: request.headers.get("user-agent")
3. Add endpoint `GET /api/audit-logs`:
   - Returns paginated list of `AuditLog` records for compliance inspections.
4. Write `tests/test_roi_audit.py`:
   - Verify that incident evidence contains cropped ROI dimensions rather than unbounded full images.
   - Verify that accessing the incident evidence endpoint creates a new `AuditLog` row in SQLite.
```

---

## 📋 PR 5.1: Automated TTL Retention & Cryptographic DB Vacuuming

```markdown
Task: PR 5.1 — Automated TTL Retention & Cryptographic DB Vacuuming

CRITICAL ARCHITECTURAL CONSTRAINTS:
Do NOT invent new column names, JSON payload keys, or failure strings. Import existing constants from app.schema.contracts (FailureSubsystem, PriorityTier, AuditAction, LifecycleTimestamps) and app.storage.database (FrameMetric, Incident, AuditLog, get_session, engine).
Do NOT run live EfficientAD inference or download the VisA dataset. Use synthetic image arrays (e.g. np.zeros((256, 256, 3), dtype=np.uint8)) and mocked inference result dictionaries.
Verify tests pass: Run python -m unittest tests/test_three_services.py and add dedicated unit tests for your changes.

Testing & Mocking Instructions for Jules:
Do NOT run live EfficientAD inference or download the VisA dataset.
Rely on mocked frames and simulated inference results:
Use synthetic image frames (e.g. np.zeros((256, 256, 3), dtype=np.uint8) or test fixtures).
For inference outputs, mock or stub the detection dictionaries and anomaly scores (e.g. {"anomaly_score": 0.85, "is_anomalous": True, "detections": [...]}).
Validation Command:
Run fast unit and integration tests using:
python -m unittest tests/test_three_services.py tests/test_ttl_maintenance.py
Ensure all tests run purely on CPU, in-memory or SQLite temporary files, and complete within seconds without external network dependencies.

⚠️ ARCHITECTURAL CONSTRAINT:
Do NOT invent new database column names, JSON payload keys, or error/failure strings.
Import the canonical constants from app/schema/contracts.py and app/storage/database.py.
All failure attribution types must match FailureSubsystem. All priority classes must match PriorityTier.

OBJECTIVE & DETAILED SPECIFICATION:
Implement background automated TTL data pruning (72-hour routine telemetry, 30-day incident dossiers) and SQLite vacuuming to guarantee GDPR storage limitation (docs/MVP_SPEC.md Section 3.4).

TARGET FILES:
- app/storage/maintenance.py (New module)
- main.py (Register maintenance task in lifespan)
- tests/test_ttl_maintenance.py (New test file)

DELIVERABLES:
1. Create `app/storage/maintenance.py`:
   - Implement `purge_expired_data(db_session, telemetry_ttl_hours: float = 72.0, incident_ttl_days: float = 30.0) -> Dict[str, int]`:
     - Delete rows from `frame_metrics` and `system_metrics` where `created_at < now - timedelta(hours=telemetry_ttl_hours)`.
     - Delete resolved incidents and unlink associated evidence files from `outputs/incidents/` where `created_at < now - timedelta(days=incident_ttl_days)`.
     - Execute `VACUUM` on SQLite database to reclaim disk pages.
     - Return count of purged records: `{"metrics_purged": int, "incidents_purged": int}`.
   - Implement `MaintenanceWorker` background thread running every 1 hour (configurable).
2. In `main.py`:
   - Start `MaintenanceWorker` in the FastAPI `lifespan` context and stop on shutdown.
3. Write `tests/test_ttl_maintenance.py`:
   - Seed database with synthetic records older than 73 hours and resolved incidents older than 31 days.
   - Run `purge_expired_data`.
   - Assert old records are deleted, recent records remain intact, and evidence files are unlinked.
```

---

# 🛡️ STAGE 2 (STORAGE RESILIENCE)

---

## 📋 PR 3.1: P0–P4 Tiered Queue & High-Watermark Eviction Policies

```markdown
Task: PR 3.1 — P0–P4 Tiered Queue & High-Watermark Eviction Policies

CRITICAL ARCHITECTURAL CONSTRAINTS:
Do NOT invent new column names, JSON payload keys, or failure strings. Import existing constants from app.schema.contracts (FailureSubsystem, PriorityTier, AuditAction, LifecycleTimestamps) and app.storage.database (FrameMetric, Incident, AuditLog).
Do NOT run live EfficientAD inference or download the VisA dataset. Use synthetic image arrays (e.g. np.zeros((256, 256, 3), dtype=np.uint8)) and mocked inference result dictionaries.
Verify tests pass: Run python -m unittest tests/test_three_services.py and add dedicated unit tests for your changes.

Testing & Mocking Instructions for Jules:
Do NOT run live EfficientAD inference or download the VisA dataset.
Rely on mocked frames and simulated inference results:
Use synthetic image frames (e.g. np.zeros((256, 256, 3), dtype=np.uint8) or test fixtures).
For inference outputs, mock or stub the detection dictionaries and anomaly scores (e.g. {"anomaly_score": 0.85, "is_anomalous": True, "detections": [...]}).
Validation Command:
Run fast unit and integration tests using:
python -m unittest tests/test_three_services.py tests/test_tiered_buffer.py
Ensure all tests run purely on CPU, in-memory or SQLite temporary files, and complete within seconds without external network dependencies.

⚠️ ARCHITECTURAL CONSTRAINT:
Do NOT invent new database column names, JSON payload keys, or error/failure strings.
Import the canonical constants from app/schema/contracts.py and app/storage/database.py.
All failure attribution types must match FailureSubsystem. All priority classes must match PriorityTier.

OBJECTIVE & DETAILED SPECIFICATION:
Implement prioritized P0–P4 buffer eviction and disk watermark thresholds in EdgeBuffer to protect the edge host filesystem while strictly preserving P0 incident evidence (docs/MVP_SPEC.md Section 2.2-C).

TARGET FILES:
- app/edge/buffer.py
- app/edge/service.py
- tests/test_tiered_buffer.py (New test file)

DELIVERABLES:
1. In `app/edge/buffer.py`:
   - Add `priority: PriorityTier` to `EdgePayload` (defaulting to P3_METRIC).
   - In `EdgeBuffer.push()`:
     - Check buffer capacity against `high_watermark = 0.80` (80% capacity):
       - If size >= 80%: drop incoming or oldest P3/P2/P1 payloads to make room.
       - P0_INCIDENT payloads are LOCKED and must NEVER be evicted.
     - Check disk fullness: if edge host disk >= 95% full, activate circuit breaker (halt local caching, log critical alarm).
   - Add priority-aware queue counters: `get_stats()` returns counts for P0, P1, P2, P3, and total drops.
2. In `app/edge/service.py`:
   - Classify payloads when creating them:
     - If frame has active defect/incident -> `PriorityTier.P0_INCIDENT`
     - If frame anomaly_score > 0.50 -> `PriorityTier.P1_ANOMALY`
     - If keyframe JPEG preview -> `PriorityTier.P2_DIAGNOSTIC`
     - Nominal frame metrics -> `PriorityTier.P3_METRIC`
3. Write `tests/test_tiered_buffer.py`:
   - Fill a buffer of capacity 10 with 5 P0 payloads and 5 P3 payloads.
   - Push additional P0 payloads.
   - Assert all P3 payloads are evicted, but 100% of P0 incident payloads survive.
```

---

# 🏁 STAGE 3 (ACCEPTANCE HARNESS)

---

## 📋 PR 6.1: 10-Step Automated Acceptance Test Harness & Benchmarks

```markdown
Task: PR 6.1 — 10-Step Automated Acceptance Test Harness & Benchmarks

CRITICAL ARCHITECTURAL CONSTRAINTS:
Do NOT invent new column names, JSON payload keys, or failure strings. Import existing constants from app.schema.contracts (FailureSubsystem, PriorityTier, AuditAction, LifecycleTimestamps) and app.storage.database (FrameMetric, Incident, AuditLog).
Do NOT run live EfficientAD inference or download the VisA dataset. Use synthetic image arrays (e.g. np.zeros((256, 256, 3), dtype=np.uint8)) and mocked inference result dictionaries.
Verify tests pass: Run python -m unittest tests/test_three_services.py and run the new acceptance test harness.

Testing & Mocking Instructions for Jules:
Do NOT run live EfficientAD inference or download the VisA dataset.
Rely on mocked frames and simulated inference results:
Use synthetic image frames (e.g. np.zeros((256, 256, 3), dtype=np.uint8) or test fixtures).
For inference outputs, mock or stub the detection dictionaries and anomaly scores (e.g. {"anomaly_score": 0.85, "is_anomalous": True, "detections": [...]}).
Validation Command:
Run fast unit and integration tests using:
python -m unittest tests/test_mvp_acceptance_protocol.py
Ensure all tests run purely on CPU, in-memory or SQLite temporary files, and complete within seconds without external network dependencies.

⚠️ ARCHITECTURAL CONSTRAINT:
Do NOT invent new database column names, JSON payload keys, or error/failure strings.
Import the canonical constants from app/schema/contracts.py and app/storage/database.py.
All failure attribution types must match FailureSubsystem. All priority classes must match PriorityTier.

OBJECTIVE & DETAILED SPECIFICATION:
Create the comprehensive automated test suite implementing the 10-Step Verification Protocol from docs/MVP_SPEC.md (Section 5) and asserting all quantitative criteria from Section 6.

TARGET FILES:
- tests/test_mvp_acceptance_protocol.py (New comprehensive test suite)

DELIVERABLES:
1. Create `tests/test_mvp_acceptance_protocol.py`:
   - Implement an automated end-to-end integration test orchestrating:
     - Step 1: Nominal baseline (mocked normal frames).
     - Step 2: Chaos injection (blur and sensor noise).
     - Step 3: Anomaly & incident trigger with correct `FailureSubsystem` attribution.
     - Step 4: Network link termination (simulate backend connection refused).
     - Step 5: Offline SQLite edge buffer accumulation.
     - Step 6: Edge process simulated SIGKILL and restart (restoring payloads from SQLite).
     - Step 7: Network restoration.
     - Step 8: Idempotent resynchronization & backlog drain.
     - Step 9: Forensic evidence dossier assembly verification (pre, trigger, post frames).
     - Step 10: Evidence access audit log verification.
2. Assert quantitative criteria:
   - 0.0% P0 incident data loss during the offline window.
   - 100% deduplication on replayed batches.
   - Monotonic nanosecond timestamp validity (no negative stage durations).
   - Correct root cause classification matching synthetic chaos.
```
