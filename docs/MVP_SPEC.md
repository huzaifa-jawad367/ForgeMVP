# FORGE — MVP End-State Requirements & Reliability Specification

> **Guiding Product Principle:**  
> *Forge exists to explain failures in deployed computer-vision systems. When a production vision system, network link, camera, or edge host goes wrong, Forge must preserve enough trustworthy state to explain exactly what happened, when it happened, and why.*

---

## 1. Executive Summary & Core Pillars

The Forge MVP is **not** considered complete merely when the nominal happy-path workflow (`Edge → Backend → Frontend`) functions under clean laboratory conditions.

The final MVP must definitively satisfy two non-negotiable core pillars:

1. **Reliability & Failure-Resilience Standard:** The three-service architecture remains resilient, self-healing, and forensically sound under severe, realistic industrial failure conditions (network partitions, power cuts, hardware saturation, optical degradation, and data corruption).
2. **Privacy-by-Design & European Industrial Standards:** The platform complies natively with European industrial workplace regulations (GDPR Art. 5/25, EU AI Act, and German Works Council / *Betriebsrat* co-determination policies), enforcing edge-side worker anonymization, zero worker-surveillance telemetry, and strict data minimization.

```text
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                                   FORGE MVP END-STATE                                  │
 ├───────────────────────────────────────────┬────────────────────────────────────────────┤
 │    PILLAR 1: INDUSTRIAL RELIABILITY       │      PILLAR 2: EUROPEAN PRIVACY-BY-DESIGN  │
 │                                           │                                            │
 │  • Crash-proof durable edge buffering     │  • Pre-persistence worker PII redaction    │
 │  • Idempotent deduplicated sync           │  • Zero-surveillance telemetry guarantee   │
 │  • Out-of-order packet reconstruction     │  • Strict data minimization (ROIs only)    │
 │  • Prioritized P0-P4 storage eviction     │  • Automated TTL data retention & purging  │
 │  • Nanosecond monotonic time semantics    │  • Works Council / Betriebsrat compliance  │
 │  • Multi-subsystem failure attribution    │  • Audit-trailed forensic evidence access  │
 └───────────────────────────────────────────┴────────────────────────────────────────────┘
```

---

## 2. Pillar 1: Reliability & Failure-Resilience Standard

### 2.1 Failure Scenarios Under Pressure Testing

The Forge MVP must be tested against and survive the following matrix of realistic factory failure modes:

| Category | Failure Scenario | Expected System Behavior |
| :--- | :--- | :--- |
| **Network** | Temporary network drop (1–60s) | Edge silently buffers in memory; automatic drain on reconnect. |
| **Network** | Prolonged network partition (>10 min) | Edge persists to SQLite disk backup; zero memory leak; zero frame loss for incidents. |
| **Network** | Backend ACK loss after ingestion | Edge retries batch; Backend detects duplicate `idempotency_key` and returns ACK without duplicate rows. |
| **Network** | Out-of-order & delayed delivery | Backend reconstructs sequence using `(boot_id, sequence_number)` and monotonic offsets. |
| **Network** | Corrupted / malformed payloads | Backend rejects with HTTP 422/400; Edge drops poison pill to dead-letter queue without stalling buffer. |
| **Process** | Edge service sudden crash / SIGKILL | Unacknowledged payloads in SQLite survive restart; leased items re-queued on startup. |
| **Process** | Backend service restart during sync | Edge receives connection error, performs exponential backoff, and resynchronizes seamlessly. |
| **Process** | Inference engine crash / OOM | Edge watchdog catches subprocess failure, reports `SUBSYSTEM_INFERENCE_CRASH` event, and restarts model. |
| **Storage** | Edge buffer nearing capacity (80%) | Tiered eviction activated: P4/P3 dropped; P0 incidents and P1 anomalies strictly locked. |
| **Storage** | Edge host disk 95%+ full | Safety circuit breaker: halts local video caching, logs critical storage alarm, preserves pre-allocated incident DB. |
| **Storage** | Backend DB locked or write failure | Backend returns HTTP 503; Edge holds leasing lock and retries with jitter. |
| **Hardware** | Sustained 100% GPU / NVML saturation | Edge queues frames or dynamically skips diagnostics frames (P2); records hardware bottleneck telemetry. |
| **Hardware** | CPU / RAM thermal throttling | Edge captures thermal metrics (`gpu_temperature`, CPU throttling flag) to correlate with inference latency spikes. |
| **Optical** | Camera disconnect / grab timeout | Edge transitions to `CAMERA_DISCONNECTED` state; fires high-priority incident with last good frame. |
| **Optical** | Defocus blur / lens dirt | Optical monitor catches blur score collapse; attributes issue to physical sensor rather than model drift. |
| **Optical** | Gaussian sensor noise & thermal noise | Noise score exceeds threshold; attributed to physical sensor degradation. |
| **Optical** | Lighting dropout / conveyor darkness | Brightness monitor drops below threshold; incident flagged as environmental lighting failure. |

---

### 2.2 Required Architectural Reliability Properties

#### A. Durable Buffering & Zero-Loss Lease-Ack
1. **In-Memory Fast Path + SQLite Durability:**
   - Inference frames enter a thread-safe FIFO buffer ([`app/edge/buffer.py`](../app/edge/buffer.py)).
   - Unsynchronized payloads are persisted to SQLite (`outputs/edge_buffer.db`).
   - On edge restart, the buffer reads unacknowledged rows from disk before ingesting new camera frames.
2. **Two-Phase Lease-Ack Pattern:**
   - `peek_batch(batch_size)`: Leases up to $N$ payloads. Items are marked as *leased* with a timeout timestamp.
   - `ack_batch(payload_ids)`: Permanently deletes payloads from both memory and SQLite **only** upon receiving HTTP 200 from the backend.
   - If the sync worker crashes or HTTP times out, expired leases automatically return to the head of the dispatch queue.

#### B. Idempotent Synchronization & Ordering Tolerance
1. **Stable Distributed Identifiers:**
   Every event, metric, and frame payload must carry:
   - `edge_id`: Unique persistent identifier for the edge physical node (e.g., `edge-node-pcb1-01`).
   - `boot_id`: UUID generated once at service process launch to disambiguate restarts.
   - `sequence_number`: Strictly monotonic integer counter incremented per captured frame.
   - `payload_id` / `event_id`: UUID v4 or deterministic v5 hash.
   - `schema_version`: String identifier (e.g., `"1.0.0"`) to guarantee backwards compatibility.
2. **Backend Deduplication Engine:**
   - The backend enforces unique compound constraints: `UNIQUE(edge_id, boot_id, sequence_number)`.
   - Re-transmitted batches due to lost network ACKs are processed idempotently (`INSERT ... ON CONFLICT DO NOTHING`).
   - Out-of-order packets are reassembled into logical event timelines using the monotonic sequence counter.

#### C. Bounded Storage & Prioritized Evidence Eviction
Forge must **never** permit unconstrained buffering to exhaust the edge host's filesystem. Storage must be managed through strict priority classes:

| Priority Tier | Data Classification | Eviction Policy | Storage Quota |
| :---: | :--- | :--- | :--- |
| **P0** | **Confirmed Incident Evidence** (Pre-, Trigger-, and Post-incident frames + forensic metrics) | **NEVER EVICT** automatically; requires operator sign-off or explicit TTL expiry (30 days). | 40% of buffer disk |
| **P1** | **Anomalous Frames** (Inference score $> 0.50$ without full incident confirmation) | Preserve until buffer reaches **High Watermark (80%)**; FIFO evicted thereafter. | 30% of buffer disk |
| **P2** | **Periodic Diagnostic Snapshots** (Keyframe thumbnails for UI live relay) | Aggressively rotated; retain only latest $N=100$ keyframes. | 15% of buffer disk |
| **P3** | **Normal Telemetry Records** (Numerical metrics: FPS, latency, confidence, blur) | Downsample / aggregate into 10-second averages when disk is constrained. | 10% of buffer disk |
| **P4** | **Nominal High-Res Video** (Clean inspection frames with score $< 0.10$) | **Never persist to disk**; stream through memory ring buffer only and discard immediately. | 5% (RAM only) |

#### D. High-Precision Time Semantics
To prevent clock skew, NTP jumps, or daylight-savings anomalies from corrupting root-cause investigations, all timing must decouple **ordering/duration** from **human-readable time**:

1. **Monotonic Clocks (`time.monotonic_ns()`):** Used exclusively for duration calculations, latency monitoring, lease timeouts, and inter-frame delta measurements.
2. **Wall Clocks (`datetime.now(timezone.utc)`):** Formatted in ISO-8601 with microsecond resolution for operator display and cross-service correlation.
3. **Explicit Lifecycle Timestamps:** Every frame and incident event must record:
   - `captured_at_ns`: Monotonic timestamp when the sensor delivered the frame.
   - `inference_started_at_ns`: Timestamp when tensor was dispatched to the model.
   - `inference_completed_at_ns`: Timestamp when heatmaps and defect boxes were computed.
   - `queued_at_ns`: Timestamp when payload entered the local `EdgeBuffer`.
   - `transmitted_at_ns`: Timestamp when HTTP payload was sent across the wire.
   - `received_at_ns`: Timestamp when backend `/api/edge/sync` received the packet.
   - `persisted_at_ns`: Timestamp when the database transaction committed.

---

### 2.3 Failure Visibility & Root-Cause Attribution

When a failure occurs, Forge must pinpoint the exact subsystem at fault. The system must classify failures into one of seven distinct root causes:

```text
                                  ┌───────────────────────────────┐
                                  │      ANOMALOUS CONDITION      │
                                  └──────────────┬────────────────┘
                                                 │
          ┌──────────────┬───────────────────────┼───────────────────────┬──────────────┐
          ▼              ▼                       ▼                       ▼              ▼
    [ OPTICAL ]     [ INFERENCE ]          [ HARDWARE ]             [ NETWORK ]    [ BACKEND ]
    - Defocus blur  - Model stall          - GPU VRAM OOM           - Partition    - DB lock
    - Sensor noise  - Weight crash         - Thermal throttling     - Packet loss  - Disk full
    - Light loss    - Confidence collapse  - Host RAM exhaustion    - Clock drift  - Schema mismatch
    - Camera drop     on clean image
```

#### Diagnostic Decision Heuristics:
1. **Camera Disconnect:** `fps == 0` for $> 3.0\text{ s}$ while edge service is active $\implies$ `FAILURE_SUBSYSTEM_CAMERA`.
2. **Defocus Blur / Vibration:** High anomaly score *correlated* with Laplacian variance $< T_{blur}$ $\implies$ `FAILURE_OPTICAL_DEFOCUS`.
3. **Sensor Thermal Noise / Dirty Lens:** High anomaly score *correlated* with high-frequency noise variance $> T_{noise}$ $\implies$ `FAILURE_OPTICAL_SENSOR_NOISE`.
4. **Lighting Dropout:** Frame luminance mean $< T_{dark}$ $\implies$ `FAILURE_ENVIRONMENTAL_LIGHTING`.
5. **Model Stalling / Algorithmic Drift:** Inference latency $> 3\times$ baseline with nominal hardware metrics $\implies$ `FAILURE_MODEL_INFERENCE_STALL`.
6. **Hardware Saturation:** GPU utilization sustained at 100% or GPU temp $> 85^\circ\text{C}$ with latency degradation $\implies$ `FAILURE_HARDWARE_GPU_EXHAUSTION`.
7. **Network Transport Partition:** Edge buffer size monotonic increase while `last_sync_ack_age > 10.0\text{ s}` $\implies$ `FAILURE_NETWORK_PARTITION`.

---

## 3. Pillar 2: Privacy-by-Design & European Industrial Standards

In European manufacturing environments (Germany, France, Sweden, Italy, etc.), industrial computer vision systems are strictly regulated under:
- **GDPR (General Data Protection Regulation — Regulation EU 2016/679):** Articles 5 (Data Minimization), 25 (Data Protection by Design), and 32 (Security of Processing).
- **EU AI Act:** Requirements for high-risk industrial safety and manufacturing surveillance governance.
- **Works Council (*Betriebsrat*) Co-Determination:** Strict prohibition against technology capable of covertly monitoring employee performance, work pace, or personal conduct.

Forge guarantees full compliance through the following architectural mechanisms:

### 3.1 Edge-Side Worker PII Redaction (Pre-Persistence Anonymization)
1. **In-Memory Redaction Pipeline:**
   - Any camera stream covering an industrial workstation or conveyor belt may inadvertently capture workers' hands, arms, faces, or personal identification badges.
   - PII detection and redaction (Gaussian blurring or black-box pixel masking) is executed **in memory immediately upon frame ingestion**, *before* the frame is processed for anomalies, buffered to disk, or transmitted to the backend.
2. **Irreversible Masking:**
   - Neither the local SQLite buffer nor the central backend ever receives unredacted operator biometric data.
   - Keyframes and incident snapshots stored in `outputs/incidents/` contain strictly redacted imagery.

### 3.2 Strict Data Minimization & ROI-Only Archiving
1. **Zero Continuous Video Archiving:**
   - Forge explicitly forbids 24/7 video recording. Normal conveyor operation frames are processed in ephemeral RAM rings and destroyed within seconds.
2. **Region-of-Interest (ROI) Cropping:**
   - When an incident is triggered on a printed circuit board (PCB), Forge stores the cropped defect bounding box and the heatmap overlay, discarding peripheral image areas that do not pertain to the optical inspection target.

### 3.3 Anti-Surveillance & Works Council Guarantees
1. **Cryptographic Telemetry Separation:**
   - Telemetry schemas are restricted to machine and optical metrics: `[fps, latency_ms, blur_score, noise_score, anomaly_confidence, gpu_temp]`.
   - The platform strictly rejects any telemetry schema fields associated with human operator tracking (e.g., worker ID, operator cycle time, break duration).
2. **Immutable System Telemetry Signatures:**
   - Sync packets carry signed metadata certifying that the stream source is an automated inspection camera, protecting employers and employees from regulatory audit non-compliance.

### 3.4 Automated TTL Retention & Cryptographic Deletion
1. **Configurable Time-to-Live (TTL):**
   - **Diagnostic Telemetry:** Purged automatically after **72 hours**.
   - **Incident Evidence Dossiers (P0):** Retained for **30 days** for engineering root-cause analysis, after which files are permanently unlinked and database records scrubbed.
2. **Automated Vacuuming:**
   - Edge and backend SQLite instances execute periodic `VACUUM` and secure unlinking to ensure deleted image blocks cannot be recovered from disk.

### 3.5 Tamper-Evident Access & Audit Logging
- Every view, download, or export of incident evidence through the frontend dashboard is logged with a timestamp, client IP, and incident ID.
- Operators cannot silently download inspection frames without creating an immutable audit entry.

---

## 4. Technical Protocol & Schema Contracts

### 4.1 Edge Sync Request Schema (`POST /api/edge/sync`)

```json
{
  "$schema": "https://json-schema.forge-cv.org/v1/edge-sync-batch.json",
  "schema_version": "1.0.0",
  "edge_id": "edge-node-pcb1-01",
  "boot_id": "b78d22e0-2470-4f51-8742-fa33a887019f",
  "batch_id": "batch-10492",
  "sequence_range": {
    "start": 12040,
    "end": 12055
  },
  "transmitted_at_ms": 1728042000125.4,
  "edge_buffer_stats": {
    "queue_size": 16,
    "capacity": 5000,
    "total_synced": 12040,
    "total_dropped": 0,
    "storage_used_bytes": 4194304,
    "storage_max_bytes": 1073741824
  },
  "frames": [
    {
      "payload_id": "8d3e91aa-9f05-4c07-b24f-ef1459a93011",
      "sequence_number": 12040,
      "timestamps": {
        "captured_at_ns": 4912093847291,
        "inference_started_at_ns": 4912093910000,
        "inference_completed_at_ns": 4912111910000,
        "queued_at_ns": 4912112100000
      },
      "inference": {
        "anomaly_score": 0.842,
        "is_anomalous": true,
        "threshold": 0.50,
        "inference_time_ms": 18.0,
        "fps": 12.5,
        "defect_classes": ["scratch", "bridging"],
        "num_detections": 2
      },
      "optical_quality": {
        "blur_score": 142.5,
        "noise_score": 0.041,
        "brightness": 128.2
      },
      "privacy": {
        "pii_redacted": true,
        "redaction_method": "in_memory_gaussian_roi"
      },
      "hardware": {
        "cpu_percent": 24.2,
        "memory_percent": 41.0,
        "gpu_utilization": 58.0,
        "gpu_temperature": 62.0
      }
    }
  ],
  "latest_frame_jpeg": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
}
```

### 4.2 Backend Sync Response Schema (`HTTP 200 OK`)

```json
{
  "status": "ack",
  "edge_id": "edge-node-pcb1-01",
  "batch_id": "batch-10492",
  "received_at_ms": 1728042000142.1,
  "frames_ingested": 16,
  "frames_deduplicated": 0,
  "controls": {
    "blur": 0.0,
    "noise": 0.0,
    "brightness": 0.0,
    "latency": 0.0
  },
  "command": {
    "action": "NONE",
    "buffer_watermark_ack": "OK"
  }
}
```

---

## 5. End-State Acceptance Test Protocol (10-Step Verification)

To declare the Forge MVP complete, the system must pass this end-to-end multi-service acceptance test without manual intervention:

```text
[Step 1: Nominal Baseline] ──> [Step 2: Physical Degradation] ──> [Step 3: Incident Trigger]
                                                                          │
[Step 6: Edge Crash & Recover] ◄── [Step 5: Safe Accumulation] ◄── [Step 4: Cut Network]
       │
       ▼
[Step 7: Network Restored] ──> [Step 8: Idempotent Re-Sync] ──> [Step 9: Dossier Rebuilt]
                                                                          │
                                                                          ▼
                                                                [Step 10: UI Forensics]
```

### Step-by-Step Test Procedure:

1. **Step 1 — Nominal Operation Baseline:**  
   The edge service ingests VisA `pcb1` conveyor frames. EfficientAD produces normal scores ($< 0.50$). The dashboard displays green health badges, sub-second telemetry, and stable 12–15 FPS throughput.
2. **Step 2 — Physical Sensor Degradation Injected:**  
   Using the chaos engineering panel, defocus blur and Gaussian sensor noise are injected pre-inference.
3. **Step 3 — Anomaly & Incident Detection:**  
   Inference anomaly score breaches the $0.50$ threshold. The Incident Engine recognizes consecutive anomalies, assigns attribution (`OPTICAL_DEGRADATION`), and opens an incident record.
4. **Step 4 — Network Severed (Simulated Outage):**  
   The backend network link is abruptly terminated (HTTP requests fail with connection refused).
5. **Step 5 — Durable Edge Buffering:**  
   The edge node logs a warning, switches to resilient offline mode, and safely writes all incoming frames and incident evidence to `outputs/edge_buffer.db`. Buffer count badge increases.
6. **Step 6 — Edge Process Kill & Restart:**  
   The edge service process is forcefully killed (`SIGKILL`) while holding buffered items. Upon relaunch, `EdgeBuffer` restores 100% of unsynced items from SQLite without corruption or drop.
7. **Step 7 — Network Restored:**  
   The backend is brought back online. The edge sync worker detects the active endpoint.
8. **Step 8 — Idempotent Resynchronization & Drain:**  
   The edge buffer transmits the queued backlog. The backend processes the batch, deduplicating any previously acknowledged frames, and writes metrics to the central SQLite database. Buffer queue drains to 0.
9. **Step 9 — Forensic Evidence Dossier Assembly:**  
   The backend confirms that the incident dossier contains:
   - 3 pre-incident nominal frames.
   - Trigger incident frame with bounding boxes and defect heatmap.
   - 3 post-incident frames.
   - Synchronized system hardware and optical quality metrics.
10. **Step 10 — Frontend Forensic Presentation:**  
    The operator views the incident in the web dashboard. The modal presents:
    - Exact root cause attribution (`PHYSICAL_SENSOR_DEGRADATION: DEFOCUS_BLUR`).
    - Side-by-side pre/trigger/post forensic image evidence with worker PII redacted.
    - Timestamp breakdown detailing capture, inference, buffer latency, and sync delivery.

---

## 6. Quantitative Acceptance Criteria

| Metric | Target Requirement | Verification Method |
| :--- | :--- | :--- |
| **P0 Incident Data Loss** | **$0.0\%$ (Strict Zero Loss)** | Verify all incident frames and evidence survive 10-minute network outage and edge restart. |
| **Deduplication Rate** | **$100\%$ on repeated batches** | Inject identical batch 3 times; verify database contains exactly 1 unique record per frame. |
| **Edge Memory Footprint** | **$\le 500\text{ MB}$ RSS** | Monitor edge process memory during sustained 1,000-frame offline accumulation. |
| **Buffer Drain Throughput** | **$\ge 100\text{ frames/sec}$** | Measure time required to flush a 500-item backlog across a restored link. |
| **Monotonic Clock Integrity** | **$\ge 99.999\%$ consistency** | Verify zero negative duration values across all edge-to-backend stage transitions. |
| **PII Redaction Latency** | **$\le 15\text{ ms}$ overhead** | Ensure in-memory face/hand blurring does not drop inference FPS below 10 FPS. |
| **Root-Cause Accuracy** | **$\ge 95\%$ on synthetic chaos** | Verify that injected blur, noise, and lighting faults are correctly attributed in incidents. |

---

## 7. Status & Implementation Traceability

- [x] **Core 3-Service Architecture:** Edge node, central backend, and React dashboard operational.
- [x] **VisA & EfficientAD Integration:** Pre-trained PCB1 anomaly detection runner validated.
- [x] **Durable `EdgeBuffer`:** In-memory queue + SQLite disk persistence with lease-ack implemented in [`app/edge/buffer.py`](../app/edge/buffer.py).
- [x] **Basic Resilience Test Suite:** FIFO order, persistence across restart, offline retention, and remote control loops validated in [`tests/test_three_services.py`](../tests/test_three_services.py).
- [ ] **Pillar 1 Enhancements:** Explicit monotonic lifecycle timestamp arrays (`captured_at_ns` $\to$ `persisted_at_ns`), compound unique dedup constraints on backend database, and P0–P4 priority storage eviction.
- [ ] **Pillar 2 Implementation:** Edge-side PII redaction filter, ROI-only incident cropping, and automated 72h/30d TTL data vacuuming worker.
- [ ] **Full 10-Step Acceptance Harness:** Automated CI/CD script executing the complete failure-injection and forensic verification sequence.
