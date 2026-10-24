# Shipping

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/shipping.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. Confirm the user actually authorized merging the named change or stack.
2. Resolve the exact PR head and base. Obtain an independent per-head verdict when delegation is available; record a missing independent verdict as a gap, not a pass.
3. Inspect actual behavior, checks, and unresolved review findings. A changed head invalidates its prior verdict.
4. Land only the contiguous verified portion of an authorized stack, bottom-up, using the supported forge capability.
5. Preserve unrelated local edits and branch history. Do not force-push or bypass review requirements by default.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
