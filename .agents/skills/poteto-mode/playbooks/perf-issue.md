# Perf issue

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/perf-issue.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. Reproduce the slowness and capture a baseline with benchmark-checklist.
2. Profile the relevant path and identify the limiter, including the load generator.
3. State a hypothesis, make one scoped change, and repeat comparable measurements.
4. Verify outputs and error counts before claiming improvement. Report units, samples, variance, limiter, and gaps.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
