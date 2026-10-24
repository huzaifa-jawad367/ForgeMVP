# Opening a PR

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/opening-a-pr.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. Apply this route only when a PR is requested or already within the authorized deliverable. Otherwise finish locally.
2. Inspect the intended base, scoped changes, and existing work. Use an isolated worktree when needed; never reset away unrelated edits.
3. Use technical-writing and unslop for the explanation, a manual diff-quality pass for unavailable deslop, and scoped no-comments review.
4. Run meaningful verification and inspect the final diff. Preserve small ordered commits when commits are authorized.
5. Prefer the connected GitHub capability. Use gh only if installed and authenticated. Write multiline CLI bodies to a file with literal newlines.
6. Open a reviewable PR with actual evidence. Do not invent a URL or automatically start a monitoring/merge loop.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
