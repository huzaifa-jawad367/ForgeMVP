---
name: reflect
description: When explicitly requested, review the active conversation for durable lessons and propose scoped skill changes.
---

> Read the [Codex adapter](../../pstack/CODEX_ADAPTER.md) before using this skill or its references. It defines the supported tool, model, delegation, permission, and Windows mappings.

# Reflect

Use only when the user explicitly requests reflection. Extract durable lessons from the current conversation or an explicitly provided transcript. Do not search other workspaces' chats.

1. Collect actual decisions, corrections, and tool evidence. If no transcript is accessible, use a bounded session digest and state its limits.
2. Read the judgment, tooling, divergent, and synthesizer templates under `references/` for their substantive review criteria. Use fresh read-only reviewers within session capacity, defaulting to inherited models. The adapter overrides templates' legacy tools, model routing, and authority.
3. Synthesize Accepted, Rejected, and Backlog findings. Prefer structural enforcement over another instruction when a type, test, or existing check can enforce the lesson.
4. Present concrete skill edits for review. Reflection alone does not authorize skill mutation or backlog tickets. If the user already asked to implement the changes, do that scoped work without another generic approval request; otherwise leave a local proposal.
5. Use the installed skill-creator workflow for substantive skill edits and validate the actual files. No automatic external issue filing.
