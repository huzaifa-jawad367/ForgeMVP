# Demo observability: first delivery

Implemented on `feat/demo` from [the design plan](DEMO_OBSERVABILITY_PLAN.md).

The app now has a readable shared shell, an actual single-pipeline Overview,
Live inspection, Reliability Lab, and Privacy Lab. Missing observations remain
unknown or stale instead of becoming zero or healthy defaults.

## Run locally

Use the existing virtual environment and installed dashboard dependencies.
From the repository root, build the dashboard:

```powershell
Push-Location dashboard
npm.cmd run build
Pop-Location
```

In one terminal start the backend with a separate demo database:

```powershell
$env:DATABASE_URL = 'sqlite:///outputs/feat-demo/forge.db'
.venv\Scripts\python.exe main.py --host 127.0.0.1 --port 8000
```

In another terminal start the edge with a separate durable queue:

```powershell
.venv\Scripts\python.exe edge_service.py --input visa:pcb1 --fps 1 --backend http://localhost:8000 --db-path outputs/feat-demo/edge_buffer.db --demo-port 8001
```

This requires the VisA dataset and EfficientAD model described in the main
project setup. The verified machine already had both cached. `HF_HUB_OFFLINE=1`
can be set when using that cached model. Other inputs remain supported by the CLI.
The demo interface is optional: omit `--demo-port` for ordinary edge operation.

Open <http://localhost:8000/reliability> or <http://localhost:8000/privacy>.
The built frontend defaults to edge port 8001; set `VITE_EDGE_API_URL` before
building if a different port is needed. Allowed browser origins are loopback
ports 8000 and 5173. This interface is intended for a local demonstration.

## Demonstrate delivery and recovery

Select **Run guided demo**. It pauses edge sync for ten seconds while real
capture, inference, and SQLite admission continue. An independent browser-to-edge
channel observes queue depth and transport state, including when the backend is
stopped. Resume is driven by the edge, so closing or reloading the browser does
not leave sync paused. Manual pauses automatically resume after sixty seconds.

The run tracks the exact payload identities admitted during the pause. Payloads
before or after that window do not inflate its result. Delivery is verified only
after the cohort closes, every admitted identity receives an exact ACK, and a
separate backend database query finds every identity. Rejection, eviction, or
storage errors prevent a successful result. An empty cohort is inconclusive.
Reset clears presentation state and resumes sync; it does not delete records.

Buffer insertion/eviction and ACK removal now change memory only after the
corresponding SQLite transaction succeeds. Failed backend writes return an error
instead of an ACK. Backend identities are scoped by edge, with unique constraints
and idempotent retry handling. Existing frame tables receive additive columns and
indexes on startup; new records include edge, payload, boot, and sequence identity.

## Demonstrate privacy

Choose a JPEG/PNG or select **Use synthetic sample**, then process with blur or
solid mask. The synthetic drawing exercises actual redaction but is explicitly
not an accuracy benchmark. Original and output use the same display scale, with
optional detection boxes and measured request processing time.

Original bytes go directly to the loopback edge API, bypassing the backend.
The endpoint accepts at most 5 MiB and four million pixels, processes one request
at a time in memory, and returns a processed PNG with `Cache-Control: no-store`.
It does not enqueue, archive, or sync either preview image. The browser keeps an
original object URL until replaced or cleared.

Preview and production share OpenCV frontal-face detection and a YCrCb skin
heuristic. Detection can miss faces and alter non-person areas. The UI states
these limitations; this demonstration does not establish GDPR compliance.

## Verification and remaining scope

Run the suite against an explicit test database. Existing integration tests clear
frame metrics and must not run against a database whose history you need:

```powershell
$env:DATABASE_URL = 'sqlite:///outputs/feat-demo/tests-isolated.db'
.venv\Scripts\python.exe -m unittest discover -s tests
```

On 2026-10-23, 59 Python tests passed, including transaction failure, invalid/lost
ACK retention, original-boot replay, exact cohorts, eviction/rejection outcomes,
request limits, preview concurrency, shared privacy output, and raw EfficientAD
score propagation for normal frames. Dashboard lint
and production build passed. Vite reports a large bundle warning; the test run
also reports an unclosed SQLite connection ResourceWarning to investigate.

Chrome checks covered guided recovery with 10/10 payloads reconciled, reload
during an active outage, blur and mask processing, a real backend stop/restart
with continued edge observation, and narrow-screen layout without horizontal
overflow. Runtime logs, test output, screenshots, and the decision trail are in
`outputs/feat-demo/`. The normal `forge.db` and default queue were not used by
this demo runtime. Pre-existing source changes were preserved. During verification,
test reruns accidentally used the default `forge.db`; an existing test cleared its
frame metrics. Its earlier frame history could not be restored from the available
baseline, which contains source changes only. The final suite rerun uses an
explicit isolated test database.

ACK-loss injection, supervised edge restart, and bounded storage-pressure UI
scenarios remain disabled. Queue replay itself has automated coverage, but run
presentation state is memory-only and resets when the edge process restarts.
Full incident evidence assembly and per-stage lifecycle timing remain future
integration work. Retry timing remains the actual fixed sync interval; the UI
does not claim exponential backoff. PostgreSQL deployment was not verified.
