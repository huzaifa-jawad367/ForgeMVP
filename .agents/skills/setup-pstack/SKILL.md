---
name: setup-pstack
description: Configure project-local pstack role preferences using models actually supported by the current Codex session.
---

> Read the [Codex adapter](../../pstack/CODEX_ADAPTER.md) before using this skill or its references. It defines the supported tool, model, delegation, permission, and Windows mappings.

# Setup pstack for this Codex project

Configure only `.agents/pstack/models.json`. Do not write Cursor rules, global Codex settings, or provider credentials. Setup is optional; this package defaults all roles to `inherit-parent`.

1. Read [the adapter](../../pstack/CODEX_ADAPTER.md) and inspect the current session's actual delegation schema. A CLI model catalog alone does not prove that a chat's delegate API can run that model.
2. Read the existing local routing file. Keep unrelated role choices. `auto` and `inherit-parent` mean omit model and reasoning overrides.
3. If the user requests specific model/effort choices, check their exact identifiers against the currently available tool and any applicable session restrictions. With this collaboration API, an override requires `fork_turns: "none"` and a self-contained brief; full-history forks inherit and reject overrides. Do not infer a speed mode from a model suffix.
4. Present any actual availability limits. Do not map Grok or Claude to GPT and call it equivalent. Unsupported routing stays inherited with an explicit note, or remains an unmet request if the named model is required.
5. Write only confirmed requested changes to the local JSON. Use one role per key. Validate JSON and invoke a bounded check only when it is authorized and needed; never silently launch a paid cross-provider call to test a slug.
6. Report the file and actual choices. This is a skill-interpreted routing file, not a Codex engine configuration. A skill cannot change the parent chat's model, effort, billing, or context policy.
