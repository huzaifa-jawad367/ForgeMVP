# Forge demo observability and frontend plan

Status: initial delivery implemented on `feat/demo`; see [implementation and run instructions](DEMO_IMPLEMENTATION.md) for verified scope and remaining work. Original plan follows, based on a local runtime review on 2026-10-23.
Reference: [MVP specification](MVP_SPEC.md).

## Desired experience

A visitor should understand three things without reading the specification:

1. What the inspection system is doing now.
2. What survives when a component or connection fails, with visible evidence of recovery.
3. What happens to an image before it can be buffered, transmitted, or archived.

Keep live operations readable and give reliability experiments their own page. Every experiment should explain the action, expected behavior, observed behavior, and result. Show actual measurements; show unavailable data explicitly.

## What was inspected and verified

- Started FastAPI at `http://localhost:8000` and opened the existing compiled React dashboard in Chrome.
- Started the standalone edge service with the cached EfficientAD PCB1 model and the real VisA dataset: 1,004 normal and 100 anomalous images. This machine used CPU inference, around 250–300 ms per inspected frame, at a configured 1 FPS.
- Used separate review databases, `outputs/demo-review/forge.db` and `outputs/demo-review/edge_buffer.db`, to preserve the existing databases and their pending payloads.
- Stopped the review backend while leaving edge inference running. At the offline sample, the backend had 30 rows and the edge had 17 pending payloads, frame indexes 30–46. After restarting the backend, all 17 appeared in the backend database. There were zero duplicate `(boot_id, sequence_number)` groups in that review database. The queue returned to a small live working backlog rather than remaining at the outage backlog.
- During the outage, the browser continued to display its previous active status and queue values. It did not clearly explain that its telemetry was stale.
- Ran 15 existing tests covering redaction, buffer priorities, schema contracts, idempotent ingestion, and failure attribution; all passed using a separate verification database. These checks do not establish every acceptance target in the specification.
- Preserved the seven files with pre-existing uncommitted changes. No product implementation was changed during this review.

### Current data locations

| Data | Current location and behavior |
| --- | --- |
| Source images | `../data/VisA_20220922/pcb1/Data/Images/{Normal,Anomaly}`; read by the edge dataset loader |
| Pending edge payloads | `outputs/edge_buffer.db`, SQLite `edge_queue`; JSON includes metrics and periodic redacted JPEG keyframes; restored at edge startup |
| Backend records | `forge.db` by default; SQLAlchemy tables `sources`, `frame_metrics`, `system_metrics`, `incidents`, `audit_logs`; `DATABASE_URL` can override storage |
| Incident files | `outputs/incidents/<incident_id>/`; image and JSON evidence managed separately from database records |
| Live preview | In-memory latest JPEG, relayed through `/api/stream/live` and `/api/stream/frame` |
| Dashboard | Source in `dashboard/src`; compiled bundle in `dashboard/dist`, served by FastAPI |
| Review runtime | Logs and disposable databases in `outputs/demo-review/`; normal edge CLI still defaults to the existing queue database |

The default local application uses SQLite. The Docker Compose configuration proposes PostgreSQL; this review did not verify that deployment.

## Findings that affect the design

1. **The fleet overview uses mock data.** Five cards and their summary counters come from `mockPipelines.js`. Diagnostics also use mock metadata, while API history and the WebSocket are effectively shared. Replace this with the actual active pipeline, or label fixture cards explicitly and keep their data separate.
2. **Reliability telemetry travels on the connection being demonstrated.** `/api/edge/status` only knows the last successful sync. A live offline queue graph requires an independent local observation channel; otherwise it must say “last reported,” with an age.
3. **Health concepts are conflated.** Browser WebSocket connection, backend availability, edge heartbeat, capture activity, inference, and sync need independent states. The existing Stop button calls the backend-local pipeline endpoint, which does not stop the standalone edge process.
4. **The layout hides the story.** Small uppercase labels, low-contrast text, glowing borders, a large stream, stacked metrics, and bottom controls compete for attention. The buffer appears far down the diagnostics page.
5. **The buffer latency label is misleading.** It displays inference time, not queue residence or sync round-trip time. Several missing metrics also become zero in frontend hooks.
6. **Privacy is implemented as a heuristic.** `redact_worker_pii` uses YCrCb skin-colour regions and Gaussian blur. It is not a validated face detector. A true `pii_redacted` flag means regions were changed; it does not establish that every person was anonymized.
7. **Some requested demonstrations need integration work.** The backend currently supplies a placeholder 1×1 frame to its incident engine rather than rebuilding evidence from edge keyframes. Full lifecycle timestamps and privacy metadata are not exposed by the metrics API. Do not present complete evidence or stage timing until those paths are connected.

## Proposed navigation and visual direction

Use one consistent shell with four destinations:

| Page | Purpose | Main content |
| --- | --- | --- |
| Overview | Understand current operation | Actual pipeline, independent service health, four headline metrics, latest incident, links into experiments |
| Live inspection | Operate and investigate the conveyor | Moderate-size stream, anomaly/optical trends, recent incidents; optional advanced sensor controls |
| Reliability Lab | Demonstrate failure and recovery | Guided experiment, pipeline flow, live queue chart, durable-storage details, event log, measured outcome |
| Privacy Lab | Inspect the real redaction path | Upload, original/redacted comparison, region overlay, processing time, persistence boundary, detector limitations |

Use a restrained dark industrial theme with a neutral background, clear borders, and one accent colour. Reserve amber/red for degraded/error states. Use 16 px body text, readable chart labels, 24–32 px page titles, and 24 px card padding. Use monospace for identifiers and numbers, not entire descriptions. Remove scanlines and decorative flashing. Support normal page scrolling, visible keyboard focus, reduced motion, and narrow-screen stacking. Avoid a fixed controls panel obscuring content.

## Reliability Lab: primary demo

First experiment: **Disconnect sync → accumulate safely → reconnect → verify delivery.**

Low-fidelity page arrangement:

```text
Reliability Lab                         [Run guided demo]
See how Forge keeps working when delivery stops.

[Camera / inference] → [Durable edge queue] → [Sync link] → [Backend database]
 Running               17 pending           Disconnected   Reachable

[Disconnect sync] [Reconnect]   Experiment elapsed: 00:18
“Capture continues. Payloads stay on the edge until acknowledged.”

[Captured in run] [Pending locally] [Committed remotely] [Dropped by tier]

Queue depth over time                  Delivery and storage
Outage / recovery markers              Last ACK / next retry
Pending and recovered counts           SQLite rows / bytes / oldest age
                                       P0 / P1 / P2 / P3 breakdown

Experiment events                      Outcome
14:02:10 Sync disconnected              Reconciled 64 of 64 run payloads
14:02:11 Payload persisted locally      Duplicate attempts / inserts
14:02:28 Sync restored                  Protected incident payloads lost
14:02:29 Backlog acknowledged           Remaining backlog / measured drain rate
```

### Behavior and measurement

- Disconnect **only the edge sync transport**. Keep inference, the web app, and the demo observation channel available. Label this accurately as an injected sync outage.
- Add an optional, loopback-only demo interface on the edge process for status, pausing/resuming sync, and transient privacy processing. Start it only in demo mode. The backend can relay status and sync controls; raw privacy images must go directly to the local edge interface.
- Explain that this channel exists to observe the experiment. A whole-edge disconnection makes its values unknown; switch to last-known data rather than continuing an animated estimate.
- Return observed state after a control action. Do not mark “offline” merely because the browser sent a request. Handle reconnect requests even while sync is disabled.
- Record a run ID, starting counters, boot IDs, and exact payload identities. Track captured/admitted, committed, pending, rejected, and evicted payloads so the result can be reconciled without double-counting a batch in flight.
- Track capture, SQLite persistence, transmission attempts, backend commit, and ACK as distinct events. “Synced” means commit confirmed and acknowledgement received.
- For a deterministic end state, finish a bounded capture window, then drain that run's payloads. Ongoing capture does not require the global queue to stay at zero.
- Graph actual edge queue samples with outage and reconnect markers. Annotate rejected or evicted records instead of hiding them in a single zero-loss badge.
- Show stage durations only within a single clock domain. Monotonic values from different hosts/boots cannot be subtracted to infer network latency. Use edge-measured HTTP round trips and separately measured backend processing durations.
- Run reset clears experiment controls and local presentation state; it does not delete incident history or evidence.

### Additional experiments, in order

| Experiment | What visitors do | What proves it worked |
| --- | --- | --- |
| Lost acknowledgement / duplicate retry | Enable one injected ACK loss after a committed batch | Retry attempt visible; backend unique rows unchanged; deduplicated count increases |
| Edge restart | Restart the demo edge with pending payloads, through a local supervisor | New boot ID; old pending identities restored and committed once |
| Lens blur / sensor noise / lighting | Choose a named preset, optionally adjust intensity | Input change, measured optical metric, attributed incident, evidence, and recovery shown together |
| Storage pressure | Run an isolated, small-capacity queue workload | Tier occupancy and actual evictions; P0 accounting shown explicitly |
| Malformed payload | Inject a controlled invalid fixture | Rejection reason and quarantine visible; healthy following payloads still delivered |
| Retention and evidence access | Open evidence; inspect retention status | Access record, applicable expiry policy, last maintenance outcome; deletion demos use disposable fixtures |

Disable experiments with an explanation until their instrumentation and behavior are verified. Do not fill the host disk, introduce real GPU exhaustion, or stop the production process to illustrate these cases.

## Privacy Lab: image upload and comparison

1. The user selects a JPEG or PNG. Show the original using a browser-local object URL.
2. Send bounded image bytes directly to the demo edge endpoint. Decode and process in memory using the same redaction function called by the conveyor pipeline. Avoid file-spooling upload helpers, request-body logging, or storing originals.
3. Return the redacted image plus actual detector method/version, image dimensions, redaction region count, and measured processing time. Extend the shared function to optionally return region metadata while preserving its existing production behavior.
4. Present a large side-by-side comparison with an optional draggable divider and a redaction-region overlay. Keep both images at the same scale. Offer an explicitly labelled solid-mask mode if implemented in the shared pipeline.
5. Explain the boundary visually: **browser original → edge RAM / redaction → redacted output → eligible for buffering and sync**. This preview does not archive either image by default. A later save action must persist only the processed image.
6. Show “No regions detected; review the output” when appropriate. Do not show a success badge just because processing returned HTTP 200. Allow clearly labelled manual regions as a fallback, distinct from automatic detection.
7. Clear images and revoke browser object URLs when replaced or cleared. Verify that no original bytes are written to the edge queue, backend database, or evidence directory.

For dependable face demonstrations, add and validate a dedicated face detector in the shared pipeline. Evaluate varied skin tones, lighting, face sizes, profiles, multiple people, and non-person imagery. Show the method actually used. Title this page “Privacy / redaction preview”; avoid a blanket “GDPR compliant” certificate based on blur alone.

## Implementation sequence

### 1. Establish truthful signals

Work in `app/edge/service.py`, `app/edge/buffer.py`, `app/api/routes.py`, `app/api/state.py`, and telemetry contracts.

- Add optional demo edge status/control endpoints and actual sync pause/resume.
- Expose queue capacity, per-tier counts/drops, persisted-row count, storage bytes, oldest pending age, capture/inference activity, ACK age, retries, and last error.
- Add backend commit/dedup counters and run-specific reconciliation. Return failure when persistence fails; do not acknowledge an uncommitted frame.
- Preserve payload boot identity across replay and scope backend identity by edge. Verify the database's actual uniqueness enforcement before advertising replay guarantees.
- Add explicit timestamps and freshness to every status response; distinguish missing values from measured zero.

### 2. Build the shared shell and Reliability Lab

Work in `dashboard/src/App.jsx`, pages, hooks, and shared styles.

- Add persistent navigation and readable spacing/type.
- Replace the mock fleet's default live claims with real state.
- Add typed/validated status mapping, visible API errors, reconnecting/stale states, and separate control state from observed state.
- Implement the first guided outage experiment and measured result panel. Reuse Recharts for a legible time-series chart.

### 3. Add Privacy Lab

Extend `app/edge/privacy.py` and the optional edge demo API. Add the upload/comparison UI. Keep the production redaction call and the preview on the same implementation. Validate the existing heuristic before selecting a detector improvement.

### 4. Improve investigation and broaden demos

- Give incidents a full detail page with pre/trigger/post panels, root-cause explanation, relevant metrics, and an access-history panel.
- Connect edge evidence to the backend evidence manager; clearly label missing phases.
- Surface full lifecycle metadata without cross-host clock subtraction.
- Route evidence access through audited endpoints; the current static `/evidence` mount does not audit individual direct image downloads and exposes more of `outputs` than incident imagery.
- Add ACK-loss, restart, and isolated storage-pressure scenarios after their correctness checks pass.

## Definition of done

- A visitor can run a complete offline/recovery demonstration without a terminal and explain where pending data lives.
- The outage graph shows edge-observed queue growth while the backend remains accessible, and honest last-known states when the observation channel disappears.
- Run-specific counts reconcile after recovery; duplicates are reported as retries, not extra stored rows. Error and drop conditions prevent an unconditional success result.
- Reloading during an experiment reconnects to its actual state. Abandoned experiments have a visible recovery path.
- Privacy preview output matches the shared edge redaction function; originals remain out of persistent stores; no-detection and partial-detection cases are explicit.
- Integration tests cover pause/resume, persistence and acknowledgement failures, committed-batch retry, restart replay, and image persistence boundaries. Existing tests remain green.
- Browser verification covers the guided flow, stale telemetry, errors, keyboard operation, reduced motion, and desktop/narrow layouts. Build and existing applicable checks pass.

Recommended first delivery: the shared readable shell and a working offline/recovery Reliability Lab, followed by the Privacy Lab. These two additions demonstrate the core product story before adding more charts or scenarios.
