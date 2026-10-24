# Bug fix

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/bug-fix.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. Reproduce the reported defect on the same surface and capture failing evidence.
2. Trace the first incorrect state with how. Use tdd only for a cheap meaningful regression check.
3. Name the intended domain shape and use architect for an unsettled boundary change.
4. Implement the smallest in-scope root-cause fix with scoped delegation when available.
5. Re-run the original reproduction and nearby meaningful checks. A blocked reproduction is an explicit gap.
6. Use Opening a PR only when the task requests it.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
