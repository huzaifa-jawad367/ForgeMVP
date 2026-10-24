# Forge context for pstack

Read the current repository before applying this context; paths and running state can change. Preserve user edits outside the requested scope.

- Product requirements: `docs/MVP_SPEC.md`. The checklist can lag implementation; verify code and runtime rather than assuming its boxes establish completion.
- Demo/front-end plan: `docs/DEMO_OBSERVABILITY_PLAN.md`. A plan is not an instruction to implement when the user asked only for investigation.
- Backend: FastAPI in `main.py`, API/state in `app/api/`, SQLAlchemy storage in `app/storage/`.
- Edge: `edge_service.py`, `app/edge/service.py`, durable queue in `app/edge/buffer.py`, privacy filter in `app/edge/privacy.py`.
- Frontend: React/Vite/Recharts in `dashboard/src/`. `dashboard/dist/` is the compiled bundle served by FastAPI. After a frontend change, rebuild before testing the backend-served bundle, or use the Vite dev server intentionally.
- Local Python: `.venv/Scripts/python.exe`. Frontend build: `npm run build` from `dashboard/`. There is a lint script but no assumption that every checked-in lint configuration/dependency works; report actual command results.
- Runtime: default backend `forge.db`; default edge queue `outputs/edge_buffer.db`; evidence under `outputs/incidents/`. Do not reset, purge, or reuse those for a disposable test. A maintenance worker can purge expired records when the backend starts.
- Use a unique `DATABASE_URL=sqlite:///outputs/<task>/forge.db` for isolated backend checks. Start an edge via `EdgeService(db_path='outputs/<task>/edge_buffer.db', ...)` when an isolated queue is required; the CLI does not currently expose a queue path flag. Prefer existing meaningful tests, inspect their state effects, and use isolated storage.
- Test suite includes `tests/test_three_services.py`, `tests/test_idempotent_ingest.py`, `tests/test_tiered_buffer.py`, `tests/test_pii_redaction.py`, `tests/test_failure_attribution.py`, and other focused modules. Run only relevant checks and do not claim the whole MVP is verified from a subset.
- Independent process health matters: capture, inference, edge sync, backend availability, and browser telemetry are different states. The current backend-local Start/Stop endpoints do not supervise the standalone edge process.
- The skin-colour redaction heuristic is not a validated guarantee that every face is anonymized. Demo visualizations must expose actual observations and missing data rather than inventing zero loss, live offline telemetry, or a compliance certificate.
- Review services may already be listening on localhost:8000 with review data under `outputs/demo-review/`. Inspect before starting or stopping anything; do not kill a process just because its port matches.

These notes supply project-specific boundaries, not ongoing authorization to alter services, run network experiments, publish, or implement the frontend plan.
