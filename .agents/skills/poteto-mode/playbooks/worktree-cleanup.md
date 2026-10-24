# Worktree cleanup

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/worktree-cleanup.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. Inspect git worktree list and branch/merge state read-only first.
2. Identify only disposable or explicitly requested targets. Preserve dirty worktrees, unknown state, and unrelated caches.
3. Before removal on Windows, verify each resolved absolute path stays in the intended target directory. Use one shell and native literal-path operations.
4. Prefer normal git worktree removal; do not force-remove or recursively delete as a fallback without the required authorization.
5. macOS simulator cleanup is unsupported in this Windows adaptation. Report reclaimed space only if measured.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
