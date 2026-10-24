---
name: interrogate
description: Adversarially review a scoped artifact with independent attempts and honest model-diversity limits.
---

> Read the [Codex adapter](../../pstack/CODEX_ADAPTER.md) before using this skill or its references. It defines the supported tool, model, delegation, permission, and Windows mappings.

# Interrogate

Adversarially review a scoped artifact without auto-applying changes. Multiple inherited-model reviewers provide independent attempts, not the upstream multi-model guarantee.

1. Identify the requested files/diff and relevant base. Include the current task's uncommitted edits only when in scope; do not review or rewrite unrelated changes.
2. State intent from the user's request and source evidence. Resolve factual uncertainty by inspection. Ask only when missing intent materially affects review.
3. Read [reviewer prompt](references/reviewer-prompt.md), [rubric](references/rubric.md), [code-quality lens](references/code-quality-review.md), and [lead judgment](references/lead-judgment.md).
4. Give fresh read-only reviewers the same intent and scope. Choose available model routing through the adapter. Inspect concrete failing cases yourself. If no delegation is available, perform a sequential review and label the loss of independence.
5. Deduplicate findings and put each in Act on, Consider, Noted, or Dismissed, with evidence and a short reason. State which independent attempts found it and any disagreements. Do not overstate agreement between same-family reviewers.
6. Return intent, actual review setup, findings, agreement, and gaps. A review is not authorization to apply fixes, create a PR, or message another person.
