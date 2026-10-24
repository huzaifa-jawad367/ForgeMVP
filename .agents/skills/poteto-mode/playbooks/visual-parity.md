# Visual parity

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/visual-parity.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. Capture the real reference and target at matching viewport, state, fonts, and data.
2. Use the available browser/computer skill. A DOM snapshot or successful build is not a visual parity check.
3. Preserve the reference baseline and comparison harness unchanged. Do not weaken the comparison to make a candidate pass. Record any intentionally excluded dynamic regions before comparison.
4. Compare meaningful regions, implement scoped differences, and capture again. Use a measured image diff against the fixed baseline for a pixel-exact claim. Exact parity requires a zero diff in the declared scope, not a screenshot judged by eye.
5. Report the comparison method, measured result, scope, and evidence. A nonzero diff or unavailable comparison is a gap. A visual inspection can be useful, but label pixel parity unverified rather than calling it equivalent.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
