---
name: show-me-your-work
description: Keep an evidence-linked decision trail for long tasks without inventing transcript or reviewer verification.
---

> Read the [Codex adapter](../../pstack/CODEX_ADAPTER.md) before using this skill or its references. It defines the supported tool, model, delegation, permission, and Windows mappings.

# Show me your work

Keep one append-only TSV decision trail for a long or unattended task. Use [the template](references/decision-log-template.tsv). Columns are `ts`, `phase`, `decision`, `why`, `evidence`, and `result`.

- Keep task-local working evidence under `outputs/<task>/` for this project. Commit a trail only when requested or appropriate to an authorized deliverable.
- Record choices, checkpoints, pivots, failures, and measured results, not every tool call. Evidence is a real path, URL, commit identity, or command receipt. Mark guesses and missing proof.
- Use Python's `csv` writer with tab delimiter, or another available local tool. Keep cells single-line and prefix spreadsheet formula-leading characters `=`, `+`, `-`, and `@` with an apostrophe. The upstream Bash logger is preserved as source only.
- Start a new run with a `start` row when appending to another run's trail. Correct bad entries with superseding rows; do not rewrite history.
- Audit against the conversation and accessible tool receipts. Use a transcript only when this session exposes its exact path or the user supplies it. No search through unrelated private session directories. Missing transcripts mean transcript-level audit is unverified.
- Request an independent read-only review when tools and scope allow. Record the actual model; same-model review does not satisfy upstream's cross-family requirement. Without a delegate, label self-review explicitly.
- Report the trail path and attention items. Never claim that an inaccessible transcript, unrun check, or unavailable reviewer verified the work.
