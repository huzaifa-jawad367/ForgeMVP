---
name: arena
description: Compare isolated candidate designs or implementations, choose a base, and verify a coherent synthesis.
---

> Read the [Codex adapter](../../pstack/CODEX_ADAPTER.md) before using this skill or its references. It defines the supported tool, model, delegation, permission, and Windows mappings.

# Arena

Produce competing candidates, choose a base, graft useful ideas, and verify the synthesis.

1. Frame the artifact and three to six observable scoring criteria. Candidates receive the same task and required constraints; keep the judging rubric separate when conducting a blinded comparison.
2. Choose two or more candidates only when comparison earns its cost. Use inherited model routing unless the user configured an available model. Give each candidate a distinct output directory or explicit worktree. No shared candidate writes.
3. Delegate within the actual available slots, or run sequential attempts when delegation is unavailable. Record dropouts and independence limits. Do not claim cross-family comparison from multiple instances of the same model.
4. Once candidates stop writing, request a fresh read-only judge when available. It scores candidate artifacts against the rubric. A different family is optional only when genuinely available and authorized; otherwise record the missing diversity.
5. The parent reads every candidate and makes the final choice. Prefer coherent boundaries and a smaller API when tied. Graft only the useful parts, then verify the synthesized artifact on the real surface.
6. Report the chosen base, rejected alternatives, judge agreement/disagreement, graft sources, dropouts, and verification evidence. Independent candidate agreement is evidence with the stated limitations.
