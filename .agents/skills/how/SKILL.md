---
name: how
description: Trace subsystem architecture, data flow, storage, and ownership from code and runtime evidence.
---

> Read the [Codex adapter](../../pstack/CODEX_ADAPTER.md) before using this skill or its references. It defines the supported tool, model, delegation, permission, and Windows mappings.

# How

Explain the affected subsystem from actual source and runtime evidence before changing it. Use [explorer prompt](references/explorer-prompt.md) and [explainer prompt](references/explainer-prompt.md) for their evidence/output structure; the Codex adapter controls delegation, models, and permissions.

1. State the question and relevant boundary. A single module or narrow question needs one exploration pass; do not fan out for its own sake.
2. For a cross-cutting question, split into two to four independent angles. Use available delegated readers with no-edit briefs and the paths to these templates. Schedule within the session's actual capacity. With no delegation tool, inspect those angles sequentially and label that limitation.
3. Trace input, transformation, storage, output, and failure paths. Cite the files/symbols actually read. Record missing or contradictory evidence.
4. Synthesize Overview, Key Concepts, How It Works, Where Things Live, and Gotchas, omitting empty sections. The parent checks the explanation against the source. Use [why](../why/SKILL.md) for motivation, not speculation disguised as fact.

Investigation stays read-only. An explanation is not permission to rewrite the subsystem.
