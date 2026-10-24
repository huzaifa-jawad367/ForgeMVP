# Validation record

Checked on 2026-10-23 against the installed `codex-cli 0.162.0-alpha.17.2` binary. This record distinguishes structural support from runtime behavior.

## Completed structural checks

The bundled skill-creator `quick_validate.py` validated all 43 active `SKILL.md` files with no failures. The project validator then checked:

- 43 active skill manifests and matching UI/default-prompt metadata.
- Preservation of upstream invocation-policy intent in the supported metadata shape.
- All 24 substantive principle bodies, 23 translated playbooks, and their preserved originals.
- SHA-256 integrity of 120 archived source files from pstack 0.15.31 at commit `e7fb9647db242b96206978d56e8aff4a68718088`.
- All local Markdown links in active skills, reference templates, and package documentation. The completed final run's link count is in [validation-results.json](validation-results.json).

The archive's local `.gitattributes` rule disables line-ending conversion so its byte-level hashes remain meaningful after Git checkout. Archive Markdown links to omitted optional upstream capabilities are historical and are not claimed to form an installed full plugin.

## Binary discovery check

An isolated format probe first confirmed `.agents/skills/<name>/SKILL.md` and parsed `agents/openai.yaml` interface fields. After installation, this command initialized a temporary stdio app-server and invoked `skills/list` with `forceReload` for the repository root and `dashboard/`:

```powershell
.venv/Scripts/python.exe .agents/pstack/scripts/validate_install.py --discovery
```

Both working directories returned all 43 skills enabled with `scope: repo`, parsed interface metadata, and no discovery errors. No model turn was sent by this protocol check. The existing application and Codex daemon were not restarted or reconfigured. The response does not expose invocation policy, so automatic/explicit-only enforcement itself remains unverified.

## Independent behavioral probe

A fresh delegate without the parent's conversation was given the installed mode path and this task:

> Investigate what happens to pending edge payloads when the backend cannot be reached, how they are saved, and what triggers removal after reconnect. Explain with source evidence. This is a read-only question; do not implement anything.

It was forbidden to edit, mutate network state, operate apps, create commits/PRs, inspect unrelated history, or spawn more delegates. It inherited the parent model; no model-family routing was tested. The actual tool-selected model identifier was not returned as a separate receipt, so this is not described as a cross-model evaluation.

Observed result from the returned analysis:

- Selected the Investigation route and read the mode, adapter, Forge context, dependency index, how workflow/templates, and unslop.
- Explained peek-without-removal, optional SQLite durability, startup restore, and removal after HTTP 200 plus JSON decoding, citing `app/edge/service.py` and `app/edge/buffer.py`.
- Distinguished retry behavior from an unconditional no-loss guarantee. It identified storage-capacity eviction, logged persistence failures, missing application-level ACK validation, and caught backend write exceptions as qualifications.
- Reported source-only evidence and did not claim to have executed an outage test. It declined database-mutating tests under its read-only scope.
- Reported using file reads, `rg`, and before/after Git status. Parent inspection of the resulting working tree found no application changes added by this installation or probe.
- Disclosed direct investigation without internal corroborating delegates, as required by the test constraints.

The report supports correct routing and scoped source investigation in this one case. Exact leaf-reading sequences are delegate-reported; no transcript-level audit is claimed. Feature implementation, browser driving, PR delivery, cleanup, and all other playbooks were not forward-tested end to end.

## Independent adaptation review

A separate read-only reviewer inspected the dependency closure, source/active separation, tool and model translations, permissions, and validation claims. It found two issues: this record needed actual results, and the translated visual-parity route had weakened the upstream measured-diff requirement. Both were corrected before the final validation. Pixel-exact claims now require an unchanged baseline/harness and measured zero difference in the declared scope; screenshot-only review is explicitly insufficient.

## Scope

- Local skills and interface metadata, required source resources, link closure, and provenance.
- Repo-root and nested dashboard discovery using the installed binary's app-server protocol.
- A read-only Forge investigation using the installed mode and dependencies, without app mutations or external writes.

## Boundaries

No compatibility claim is made for Cursor model IDs, multi-model diversity, persistent cloud orchestration, automation wakeups, external bot configuration, private transcript access, or the preserved Bun/Bash helpers. No model override is tested or needed for default inheritance. Discovery does not prove enforcement of explicit-only invocation policy.

See [CODEX_ADAPTER.md](CODEX_ADAPTER.md) for the supported translations and remaining limitations.
