---
name: figure-it-out
description: Design and execute an auditable playbook for a broad task that needs measurable gates and phased verification.
---

> Read the [Codex adapter](../../pstack/CODEX_ADAPTER.md) before using this skill or its references. It defines the supported tool, model, delegation, permission, and Windows mappings.

# Figure it out

Design a task-specific playbook when no narrower playbook fits. Rigor means evidence and gates proportional to the actual task.

1. Frame a falsifiable done predicate, boundaries, rough work units, and the riskiest unknowns. Ground the surrounding system with [how](../how/SKILL.md).
2. Capture a meaningful pre-change baseline before implementation. Use [architect](../architect/SKILL.md) for unsettled architectural choices, not a repeated ceremony over settled mechanical work.
3. Sequence verifiable units. Declare blocking gates, independent workstreams, shared mutable state, and the smallest safe decomposition. Give any delegated writers separate outputs and integration ownership.
4. For each unit, state a hypothesis, change the smallest relevant part, inspect the real artifact, and keep or revert only your own changes according to evidence. VERIFIED, NOT VERIFIED, and INCONCLUSIVE are distinct outcomes.
5. Keep the decision trail through [show me your work](../show-me-your-work/SKILL.md). Document gates and unresolved assumptions while proceeding on independent authorized work.
6. Verify the whole against the original predicate. Report the designed playbook, tradeoffs, evidence, trail path, and remaining gaps. Do not infer permission for external writes or continued execution after the session ends.
