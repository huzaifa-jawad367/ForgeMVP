# Hillclimb

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/hillclimb.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. Define the metric, target, constraints, stop conditions, and a trustworthy fixed harness.
2. Validate the baseline using benchmark-checklist and keep a decision trail.
3. Loop one hypothesis and scoped change at a time. Compare on the same workload and count correctness failures.
4. Keep proven wins; revert only your own losing edits. Record inconclusive experiments.
5. Stop at the requested target or resource boundary. Do not create a budgeted goal unless explicitly requested.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
