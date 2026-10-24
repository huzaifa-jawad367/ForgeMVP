---
name: no-comments
description: Review comments and suppressions in scope while preserving real contracts and correctness constraints.
---

> Read the [Codex adapter](../../pstack/CODEX_ADAPTER.md) before using this skill or its references. It defines the supported tool, model, delegation, permission, and Windows mappings.

# No comments

Review comments and suppressions in the requested scope. Preserve necessary legal notices, public API contracts, proven external constraints, and useful issue links. Prefer self-explanatory code over narration.

1. Read [comment reviewer instructions](../poteto-mode/references/comment-sicko.md). Give a fresh read-only delegate the scope and that path if delegation is available; otherwise review directly and report the independence limitation.
2. Inspect the nearby code before accepting any finding. A review result must name the exact comment/symbol and why it is redundant, misleading, or a workaround. Treat correctness-related suppressions as signals to investigate, not permission to delete guards.
3. Apply accepted changes only when the caller authorized editing. Reject code edits by a report-only reviewer. Use [how](../how/SKILL.md) or [why](../why/SKILL.md) when a claimed constraint is unclear, and [architect](../architect/SKILL.md) before a meaningful shape change.
4. Prefer the smallest in-scope root-cause fix. Do not remove an uncertain correctness constraint merely to satisfy a style preference. Preserve it and report the uncertainty until evidence resolves it.
5. Where a type, check, or existing lint rule can enforce a real constraint, implement it within the task's authorization or propose it for later. No extra approval gate is implied for already-authorized reversible work.
6. Report accepted deletions/fixes, protected comments, unresolved constraints, and actual verification. External deslop and registered Comment Sicko agent types are not installed by this package.
