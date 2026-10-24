# Autonomous run

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/autonomous-run.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. Define the done predicate and requested resource/authority boundaries.
2. Run the matching narrower playbook and maintain a decision trail.
3. Continue authorized independent work while recording genuine blockers. Autonomy does not grant external messaging, deletion, or merge authority.
4. Checkpoint on disk before context rollover and continue after compaction. Execution ends when this session ends; no scheduler is installed.
5. Verify the real result and name unfinished work honestly.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
