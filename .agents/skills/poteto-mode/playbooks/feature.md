# Feature

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/feature.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. Ground with how; use architect for meaningful design choices.
2. Name the data shape and its organizing structure before logic.
3. Write the throughput checkpoint: blocking gates, independent streams, shared mutable state, smallest safe decomposition.
4. Delegate implementation with explicit ownership where tools permit. Use arena for truly competing shapes. Otherwise implement directly and record the review-separation limit.
5. Verify the actual behavior and inspect the diff. Use interrogate for a contested design.
6. Sequence small verifiable units. Commit or open a PR only within the actual delivery request.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
