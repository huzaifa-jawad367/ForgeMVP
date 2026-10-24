---
name: poteto-mode
description: 'Use poteto-mode for rigorous project engineering: grounded design, small changes, deliberate delegation, and
  verified outcomes.'
---

> Read the [Codex adapter](../../pstack/CODEX_ADAPTER.md) before using this skill or its references. It defines the supported tool, model, delegation, permission, and Windows mappings.

# Poteto mode for Forge / Codex

Use rigorous, small, verifiable changes. The parent owns the playbook, integration, and final evidence. This is a project-local adaptation, not the Cursor plugin runtime.

## Start

1. Read [the Codex adapter](../../pstack/CODEX_ADAPTER.md) once per session. Its capability and authorization translations apply to every bundled skill, source template, playbook, and delegate. Read [Forge context](../../pstack/FORGE.md) for project work and [dependencies](references/dependencies.md) when resolving a route.
2. State the requested outcome, scope, and a checkable done predicate. Inspect existing work before editing. Match one playbook from the table below and read its active file. Preserve the task's existing authorization and any explicit planning checkpoint.
3. Use the session's plan tool if it has one; otherwise maintain a short task checklist in a local task note or progress update. No fabricated TodoWrite call. Keep skipped steps with a reason.
4. Read the relevant principle leaf in full before applying it. The [principles index](references/principles.md) maps all 24 names to installed files. Mention a principle only when its concrete effect helps the user assess a choice.

## Routing

| Request | Active playbook |
| --- | --- |
| Explain / investigate / assess a premise | [Investigation](playbooks/investigation.md) |
| Reproduce and fix a defect | [Bug fix](playbooks/bug-fix.md) |
| Measured slowness | [Perf issue](playbooks/perf-issue.md) |
| Repeated measured improvement | [Hillclimb](playbooks/hillclimb.md) |
| Live runtime symptom | [Runtime forensics](playbooks/runtime-forensics.md) |
| Captured profile / trace | [Trace forensics](playbooks/trace-forensics.md) |
| New behavior | [Feature](playbooks/feature.md) |
| Behavior-preserving change | [Refactoring](playbooks/refactoring.md) |
| Cheap decision experiment | [Prototype](playbooks/prototype.md) |
| Match an existing visual reference | [Visual parity](playbooks/visual-parity.md) |
| Create / adapt a skill | [Authoring a skill](playbooks/authoring-a-skill.md) |
| Compare prompts or skills | [Eval](playbooks/eval.md) |
| PR readiness and existing reviews | [Babysit](playbooks/babysit.md) |
| Explicitly authorized merge | [Shipping](playbooks/shipping.md) |
| Sustained execution within this session | [Autonomous run](playbooks/autonomous-run.md) |
| Multi-phase delivery | [Multi-phase plan](playbooks/multi-phase-plan.md) |
| Resume prior work | [Session pickup](playbooks/session-pickup.md) |
| Explicit user pause | [Pause safely](playbooks/pause-safely.md) |
| Requested worktree cleanup | [Worktree cleanup](playbooks/worktree-cleanup.md) |
| Authorized PR preparation | [Opening a PR](playbooks/opening-a-pr.md) |
| Project-scale orchestration | [Orchestrate](playbooks/orchestrate.md) (bounded local adaptation) |
| Independent PR queue | [Autopilot-full](playbooks/autopilot-full.md) (bounded local adaptation) |
| Linear PR stack | [Autopilot-stack](playbooks/autopilot-stack.md) (bounded local adaptation) |

## Triggers inside the selected workflow

- Ground nontrivial changes with [how](../how/SKILL.md). Use [why](../why/SKILL.md) for historical intent; keep evidence separate from inference.
- Name the domain shape before writing logic. Read [model the domain](../principle-model-the-domain/SKILL.md). For a meaningful cross-function design, use [architect](../architect/SKILL.md); do not redesign settled mechanical edits.
- Use [arena](../arena/SKILL.md) for competing designs and [swarm](../swarm/SKILL.md) for independent slices. This skill authorizes scoped delegation when the governing session permits it. Missing delegation tools mean sequential execution with an explicit independence gap.
- Use [interrogate](../interrogate/SKILL.md) for contested design or adversarial review. Same-model attempts are independent perspectives, not cross-model evidence.
- Use [tdd](../tdd/SKILL.md) when a cheap local regression check exists. Verify UI using the available computer/browser skill, backend behavior with the real service or meaningful existing integration checks.
- Write the throughput checkpoint for multi-step changes. List blocking gates, independent slices, shared mutable state, and the smallest safe decomposition. Mark inapplicable dimensions with a reason.
- Read [benchmark checklist](../benchmark-checklist/SKILL.md) before reporting a measured performance claim. Read [show me your work](../show-me-your-work/SKILL.md) for long runs.
- Use [unslop](../unslop/SKILL.md) for prose, [technical writing](../technical-writing/SKILL.md) for maintained docs, and [no comments](../no-comments/SKILL.md) for scoped comment review. A manual diff-quality pass substitutes for unavailable external deslop; report that substitution.
- A broad task with no suitable playbook uses [figure it out](../figure-it-out/SKILL.md). Invoke [reflect](../reflect/SKILL.md) only when requested. [Setup](../setup-pstack/SKILL.md) is optional; inherited model routing already works without it.

## Delegates

Use the adapter's supported delegation API and brief template. For a code/helper delegate, include the absolute path to this file and [delegate instructions](references/poteto-agent.md). For comment review use [comment reviewer instructions](references/comment-sicko.md). The parent runs the playbook; do not delegate the entire orchestration recursively. Give candidate writers separate output directories or worktrees. Local delegates share this filesystem.

Default to inherited model and effort. Read the project routing file only through the adapter. Never invent model aliases, append effort suffixes to model IDs, or promise a different model family. Review every delegate artifact yourself.

## Finish

Verify the real outcome, inspect the scoped diff, and state remaining gaps. Report what changed for users, why the design was chosen, checks and their actual results, and relevant limitations. A local task does not implicitly require a commit, push, PR, merge, deployment, or message to another person. Do those only within the actual user request. Preserve unrelated work.
