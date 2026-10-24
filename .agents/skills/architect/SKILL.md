---
name: architect
description: Design caller usage, domain shapes, signatures, and module ownership before a nontrivial implementation.
---

> Read the [Codex adapter](../../pstack/CODEX_ADAPTER.md) before using this skill or its references. It defines the supported tool, model, delegation, permission, and Windows mappings.

# Architect

Settle caller usage, domain types, signatures, and ownership before a nontrivial implementation locks in the wrong shape.

1. Ground the relevant system with [how](../how/SKILL.md). Use [why](../why/SKILL.md) when changing ownership or layering. Skip grounding only for genuinely greenfield code.
2. Use [arena](../arena/SKILL.md) to produce two structurally distinct design candidates. Supply [runner guidance](references/runner-prompt.md), [rationale template](references/rationale-template.md), and [design red flags](references/design-red-flags.md). Candidates write only to isolated outputs. Default model inheritance means this is not a diverse-model panel.
3. Write real caller examples first, then derive types, module boundaries, invariant ownership, and data flow. Prefer a small public surface hiding real complexity. Screen both candidates against the red flags before synthesis.
4. Choose a coherent design and explain rejected alternatives and any grafted ideas. Continue implementation if authorized; stop at the design when the user requested a checkpoint or plan only.
5. Implement against that sketch. Repeated deviations, escape hatches, or shared-state workarounds are evidence to re-ground and redesign, not excuses to accumulate patches. Re-run only the unsettled design, not the whole exercise for a mechanical edit.
