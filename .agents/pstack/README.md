# pstack for this project's Codex environment

Project-local adaptation of [cursor/plugins pstack](https://github.com/cursor/plugins/tree/e7fb9647db242b96206978d56e8aff4a68718088/pstack), version 0.15.31, MIT licensed by Lauren Tan. Start with the mode; it reads other installed skills as needed.

## Invoke it

In a Codex session opened in this repository, send:

```text
$poteto-mode implement the Reliability Lab from docs/DEMO_OBSERVABILITY_PLAN.md. Start with the offline/recovery flow and verify it in the browser.
```

For a plan without implementation:

```text
$poteto-mode review the proposed Privacy Lab. Investigate the real edge redaction path and return a plan only.
```

Or ask to read `.agents/skills/poteto-mode/SKILL.md` and follow it. Skills should be available on your next turn. If this client does not refresh its list, start a new session in the repository or reopen Codex. CLI/IDE clients can use `/skills` or `$` selection where offered. This is not the Cursor `/add-plugin` command or a persistent custom mode.

Optional model setup is `$setup-pstack`. It changes only [models.json](models.json) after checking the current session's actual routing support. No setup is needed to inherit the current model.

## What is installed

- 43 skills in `../skills/`: poteto-mode, 14 core workflow dependencies, the two transitive helpers, all 24 principles, plus optional reflect and setup-pstack.
- 23 active translated playbooks, each linked to its unchanged upstream original.
- Source-derived prompt templates, review rubrics, design guidance, and the original MIT notice.
- Exact selected upstream source files in `upstream/`, with provenance and SHA-256 hashes in [manifest.json](manifest.json). The archive is reference-only; its Cursor scripts and agent manifests are not registered or executed.

Other pstack tools such as poteto-help, automate-me, recall, correct, teach, statechart, and verification-skill generators are outside this dependency closure. The full source README is preserved in [upstream/README.md](upstream/README.md) and describes capabilities beyond this installation.

Read [CODEX_ADAPTER.md](CODEX_ADAPTER.md) for tool translations, role briefs, unsupported features, authorization differences, model limits, and Windows behavior. Read [FORGE.md](FORGE.md) for project context. No global settings, AGENTS.md, credentials, MCP connections, hooks, app code, or application dependencies are changed by this installation.

## Verify it

Run from the repository root:

```powershell
.venv/Scripts/python.exe .agents/pstack/scripts/validate_install.py
.venv/Scripts/python.exe .agents/pstack/scripts/validate_install.py --discovery
```

The second command starts an isolated local Codex app-server process only to initialize and list skills. It sends no model turn and makes no inference request. It checks both repository-root and dashboard-subfolder discovery. It does not change the running Codex daemon's configuration.

The validator checks active manifests and metadata, local links, declared closure, all 23 playbooks and 24 principles, and preserved source integrity. A bounded independent behavioral probe is reported separately in [VALIDATION.md](VALIDATION.md). Discovery and successful parsing are not full runtime compatibility or proof of enforcement of invocation policy.

Validation uses Python 3.9+ and PyYAML, which are already present in this project's `.venv`. No extra package was installed. The preserved upstream helpers have separate dependencies and are not covered by this validator.

To remove the adaptation, remove only the 43 directories named in `manifest.json` and `.agents/pstack/`, preserving any edits you wish to keep. No uninstall command or recursive deletion is run automatically.
