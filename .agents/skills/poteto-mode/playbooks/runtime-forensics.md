# Runtime forensics

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/runtime-forensics.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. Treat the deliverable as diagnosis unless a fix was also requested.
2. Capture the live symptom and instrument the smallest relevant path.
3. Trace observed resource use, lifecycle, and state transitions to source. Avoid premature patching.
4. Report the demonstrated mechanism, competing explanations, evidence, and what remains unknown.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
