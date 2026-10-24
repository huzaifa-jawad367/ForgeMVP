# Pause safely

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/pause-safely.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. Pause only on an explicit user stop/pause instruction. Compaction alone is not a pause request.
2. Reach a safe boundary, stop launching work, and reconcile active delegates and processes owned by this task.
3. Leave edits on disk and write a project-local handoff with intent, verification, paths, running services, and next action.
4. Do not create WIP commits, pushes, or PRs unless already authorized.
5. If an explicit budgeted goal exists, use its pause mechanism only under the user instruction.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
