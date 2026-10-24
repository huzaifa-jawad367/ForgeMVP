# Babysit

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/babysit.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. State whether this is a one-time status check or an explicitly requested monitoring loop.
2. Use available GitHub connectors, or authenticated gh if present, to inspect the current PR head, checks, conflicts, and reviews.
3. Triage existing Bugbot/security comments skeptically using references/bugbot-triage.md. Do not configure or wait for unavailable bots.
4. Fix only authorized scope; inspect the new head and rerun relevant checks after changes.
5. Use bounded waits and progress updates. Report merge-readiness and blockers; green checks alone do not prove behavior.
6. No automatic merge follows from a request to check status.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
