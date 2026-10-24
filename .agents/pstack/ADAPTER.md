# pstack Multi-Environment Capability Adapter

This directory provides capability and tool adapters for multiple AI agent platforms:

1. **[Google Antigravity Adapter](ANTIGRAVITY_ADAPTER.md)**
   Use this adapter when running in **Google Antigravity** (Antigravity IDE, Antigravity 2.0, or the `agy` CLI).
   Maps skills to Antigravity native tools: `view_file`, `replace_file_content`, `multi_replace_file_content`, `write_to_file`, `run_command`, `browser_subagent`, `ask_question`, `manage_task`, transcripts, and artifacts.

2. **[OpenAI Codex Adapter](CODEX_ADAPTER.md)**
   Use this adapter when running in **OpenAI Codex** (Codex CLI or VS Code extension).
   Maps skills to Codex tools: `functions.exec`, `collaboration.spawn_agent`, `apply_patch`, `request_user_input_async`, and `agents/openai.yaml` policies.

Both adapters operate over the shared 43 skills in [../skills/](../skills/) without duplication or modification of core contracts.
