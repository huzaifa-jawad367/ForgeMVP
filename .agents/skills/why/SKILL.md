---
name: why
description: Investigate historical design rationale with cited evidence and explicit inference and access gaps.
---

> Read the [Codex adapter](../../pstack/CODEX_ADAPTER.md) before using this skill or its references. It defines the supported tool, model, delegation, permission, and Windows mappings.

# Why

Reconstruct motivation without turning plausible stories into facts. Ground the target with [how](../how/SKILL.md). Read [epistemics](references/epistemics.md), [source playbook](references/source-playbook.md), and the relevant investigator/synthesizer templates in `references/`.

1. Name the symbol/behavior and the question. Inspect code, tests, git history, and actual PR/issue context available to this project.
2. Discover available read-only connector capabilities. Consider source control, issue tracker, long-form documents, team chat, infrastructure observability, exception tracking, and analytics. Search only accessible, relevant sources. A category with no connector is a recorded evidence gap, not a prompt to fabricate access or install an integration automatically.
3. For multiple available categories, use scoped read-only investigators within capacity or sequential searches. Each returns supporting evidence, contrary evidence, and gaps. Defensive code should use the incident/postmortem guidance in `references/sources/incident-postmortem.md`.
4. Synthesize the question, code anchor, findings, reasonable inferences, competing hypotheses, unknowns, consulted sources, and confidence. Preserve evidence/confidence distinctions from the templates.
5. Before a change, summarize Preserve / Change / Avoid / Risk constraints. Do not post to chats or trackers as part of this read-only inquiry.
