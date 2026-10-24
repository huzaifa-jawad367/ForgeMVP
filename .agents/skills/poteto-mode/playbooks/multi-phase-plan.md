# Multi-phase plan

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/multi-phase-plan.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. Ground the target and define a final verifiable result.
2. Order independently verifiable phases by dependencies and risk. Name owners, artifacts, gates, and stop conditions.
3. If the user requested a plan, deliver the plan and stop before implementation.
4. For an execution request, complete and verify each phase before dependent work. Record exact versions and current state in the trail.
5. A stack is optional and requires an actual PR delivery request. No automatic PR creation or merge.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
