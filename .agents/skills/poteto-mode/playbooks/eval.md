# Eval

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/eval.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. Define the behavioral question and a rubric before sampling.
2. Use isolated candidate workspaces and the same realistic task. Avoid cues that reveal the intended answer.
3. Use fresh independent delegates when available. Record actual models, repeated-model limitations, and dropped candidates.
4. Judge artifacts by observable behavior. Inspect accessible tool receipts; missing transcripts leave chain-following unverified.
5. Report the evidence and uncertainty. Do not call a same-model comparison a cross-family eval.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
