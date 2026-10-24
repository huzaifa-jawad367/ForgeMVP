# Antigravity Workspace Rule: pstack Adaptation

When working in this repository using Google Antigravity (Antigravity IDE, Antigravity 2.0, or `agy`), observe the following guidelines:

## 1. Skill Discovery & Execution
- All 43 skills in `.agents/skills/` are available for execution.
- When any skill or playbook is active (e.g. `poteto-mode`, `architect`, `tdd`, `arena`, or the 24 engineering principles), follow the Antigravity capability translations in [`.agents/pstack/ANTIGRAVITY_ADAPTER.md`](../pstack/ANTIGRAVITY_ADAPTER.md).

## 2. Tool Mappings
- **File inspection:** Use `view_file` (with line slicing and pagination) and `grep_search` / `list_dir`.
- **Modifications:** Use `replace_file_content` for single contiguous chunks, `multi_replace_file_content` for non-contiguous changes, and `write_to_file` for new files.
- **Shell commands:** Use `run_command` with PowerShell syntax and explicit `Cwd` within the workspace. Never emit `cd` commands.
- **Asynchronous / Long jobs:** Set `WaitMsBeforeAsync` on `run_command` to dispatch long jobs to background tasks; interact with them using `manage_task` (`status`, `send_input`, `kill`).
- **Reactive Wakeup:** Do not poll in a loop with status checks or sleep commands. The system notifies you reactively when background tasks or subagents finish.
- **UI / Browser testing:** Use `browser_subagent` to drive and verify web applications (automatically recorded to WebP videos).
- **Design Decisions:** Use `ask_question` when underspecified architectural decisions or irreversible forks require user selection.

## 3. Evidence & Decision Logging
- Record reports, design proposals, and decision trails in the conversation's Artifact Directory (`<appDataDir>\brain\<conversation-id>\`).
- Create clickable file links using GitHub-style Markdown syntax with forward slashes: `[filename](file:///path/to/file#L1-L10)`.

## 4. Dual Compatibility
- Preserve existing Codex compatibility metadata (`agents/openai.yaml`, `CODEX_ADAPTER.md`) without modification.
