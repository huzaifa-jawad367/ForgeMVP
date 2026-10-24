# Trace forensics

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/trace-forensics.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. Read the supplied trace/profile format and its collection conditions.
2. Identify hot paths or retained resources; distinguish sampled cost from elapsed duration.
3. Map frames to source and compare alternative explanations.
4. Report a diagnosis and evidence. A captured trace does not authorize unrelated runtime changes.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
