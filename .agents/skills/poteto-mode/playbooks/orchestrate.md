# Orchestrate (bounded local adaptation)

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/orchestrate.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. The upstream durable cloud-fleet runtime is not ported. Do not run its Bun bootstrap, orch CLI, or watchers.
2. For a project that fits this session, use autonomous-run with bounded local workers, one writer per worktree/output, and parent-owned integration.
3. Persist work units, ownership, exact commits, verification verdicts, gates, and next actions in project-local notes.
4. Respect actual available agent slots. Queue remaining work; do not promise nested cloud capacity, wakeups, or restart survival.
5. Treat changed heads as unverified and reconcile every worker at a checkpoint.
6. For a multi-day durable coordinator requirement, report that infrastructure as unsupported rather than silently simulating it.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
