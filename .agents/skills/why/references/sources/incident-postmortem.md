> Source-derived reference. Read [Codex capability translations](../../../../pstack/CODEX_ADAPTER.md) first. Those rules control tool calls, models, delegation, permissions, and platform commands in this template.

# Incident & Postmortem Context

- **Linear**: look for tickets labeled `incident`, `sev-*`, `postmortem-action-item`, `reliability`
- **Slack**: search `#sev-*` and `#incident-*` channels around the dates the target code was added
- **Git**: commits with messages like "fix for incident", "add defensive check", "revert" followed by "re-apply with..." are strong signals
