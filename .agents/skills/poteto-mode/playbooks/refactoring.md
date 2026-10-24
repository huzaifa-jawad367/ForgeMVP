# Refactoring

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/refactoring.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. State the behavior and contracts that must remain unchanged. Ground the call graph with how.
2. Prefer deletion and a smaller domain shape. Use architect for ownership changes.
3. Declare shared state and scoped ownership before delegation.
4. Migrate callers and remove old internal APIs together where in scope.
5. Verify behavior rather than snapshots of internal structure. Inspect the scoped diff for unintended changes.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
