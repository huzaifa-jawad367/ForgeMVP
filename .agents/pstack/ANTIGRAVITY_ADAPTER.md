# Antigravity capability adapter for pstack

This document defines how pstack skills, playbooks, principles, and workflows adapt to the **Google Antigravity (AGY)** environment (including Antigravity IDE, Antigravity 2.0, and the `agy` CLI), while maintaining full dual-compatibility with OpenAI Codex ([`CODEX_ADAPTER.md`](CODEX_ADAPTER.md)).

---

## 1. Target Environment & Discovery

### Environment
- **Platform:** Google Antigravity (Antigravity IDE / Antigravity 2.0 / `agy` CLI)
- **Runtime:** Native Windows environment with PowerShell shell (`run_command`), structured workspace artifacts, and reactive background tasks.
- **Models:** High-reasoning Gemini models (e.g., Gemini 3.8 Flash, Gemini 3.8 Pro) with native thinking/planning capabilities.

### Skill Discovery & Loading
Antigravity automatically discovers skills within the workspace customizations root:
```text
.agents/
├── skills/
│   ├── <skill_name>/
│   │   ├── SKILL.md          # Primary instruction file with YAML frontmatter
│   │   ├── agents/           # Preserved for Codex compatibility (e.g. openai.yaml)
│   │   ├── playbooks/        # Workflows and procedural guides
│   │   └── references/       # Detailed reference templates and rubrics
└── pstack/
    ├── ANTIGRAVITY_ADAPTER.md # This adapter
    ├── CODEX_ADAPTER.md       # Codex capability adapter
    └── FORGE.md              # Project context
```

### Progressive Disclosure
- **Discovery:** Antigravity scans all `.agents/skills/<name>/SKILL.md` files at conversation startup and injects their names and descriptions into the agent's context.
- **Activation:** The agent loads the full instructions of a skill using `view_file` only when triggered by user prompt, task requirements, or playbook routing.
- **Dual Compatibility:** The YAML frontmatter (`name` and `description`) and Markdown structure are natively understood by both Antigravity and Codex.

---

## 2. Tool Translation Matrix

Upstream pstack operations map directly to Antigravity native tools:

| Logical Capability | Upstream / Codex | Antigravity Tool & Pattern |
| :--- | :--- | :--- |
| **Read File** | `read_file`, `functions.exec` | [`view_file`](file:///) with `StartLine`, `EndLine`, and `ContentOffset` for pagination. Text and binary files supported. |
| **Write New File** | `write_file`, `functions.exec` | [`write_to_file`](file:///) with `Overwrite=true` when replacing an existing file. |
| **Edit File (Single block)** | `apply_patch`, `patch` | [`replace_file_content`](file:///) for a single contiguous block with exact `TargetContent`. |
| **Edit File (Multi-chunk)** | `apply_patch` | [`multi_replace_file_content`](file:///) for multiple non-contiguous edits in a single file pass. |
| **Pattern Search** | `grep`, `rg` | [`grep_search`](file:///) using fast ripgrep (supports regex, case sensitivity, and file globs). |
| **List Directory** | `ls`, `glob` | [`list_dir`](file:///) to inspect file trees, sizes, and child counts. |
| **Execute Shell Command** | `exec_command`, `functions.exec` | [`run_command`](file:///) running in PowerShell on Windows. Specify `Cwd` within the workspace. Never use `cd`. |
| **Background / Long Tasks** | `run_in_background` | [`run_command`](file:///) with small `WaitMsBeforeAsync` sends long tasks to the background; manage via [`manage_task`](file:///) (`status`, `send_input`, `kill`, `list`). |
| **User Clarification** | `AskQuestion`, `request_user_input` | [`ask_question`](file:///) renders an interactive modal with selectable options and default write-in. For trivial questions, ask in plain text. |
| **Browser / UI Verification** | `control-ui`, `mcp__cua_repl` | [`browser_subagent`](file:///) controls browser sessions, interacts with DOM, captures screenshots, and records sessions to WebP video artifacts. |
| **Web Data / Documentation** | External fetch | [`read_url_content`](file:///) (HTTP GET to markdown) and [`search_web`](file:///) for live search. |
| **Image & UI Mockups** | External generator | [`generate_image`](file:///) for creating high-fidelity UI designs, icons, and visual assets without device frames. |
| **Timers & Crons** | Shell `sleep` | [`schedule`](file:///) for one-shot timers with early cancellation conditions or recurring cron expressions. Never use sleep commands. |
| **Task Planning & Status** | `TodoWrite`, todo lists | Markdown artifacts in `<appDataDir>\brain\<conversation-id>\` or slash command `/plan`. |
| **Decision Logs & History** | Private transcripts | Review conversation transcripts in `<appDataDir>\brain\<conversation-id>\.system_generated\logs\transcript.jsonl`. |

---

## 3. Delegation & Subagent Contract

Antigravity provides reactive wakeup and subagent execution:

1. **Subagents:**
   - Use `browser_subagent` for browser automation and end-to-end UI verification.
   - For bulk tasks or context-heavy sweeps, delegate isolated slices to subagents to protect the main context window (`principle-guard-the-context-window`).
2. **Reactive Wakeup (Zero Polling):**
   - The Antigravity system automatically wakes up the parent agent when a background task or subagent finishes.
   - **Do NOT poll in a loop** with `manage_task(Action='status')` or repeated sleeps. Launch asynchronous work and simply finish the turn or proceed with other tasks.
3. **Role Briefs:**
   - Role prompts (such as `poteto-agent`, `comment-sicko`, `investigator`, `synthesizer`) are prompt roles. Supply their reference instructions from `.agents/skills/poteto-mode/references/` into the subagent brief or execution context.

---

## 4. Evidence, Artifacts, and Decision Trails

Antigravity features a dedicated Artifact and Transcript architecture:

- **Artifacts:** Save structured reports, architecture comparisons, decision trails ([`show-me-your-work`](../skills/show-me-your-work/SKILL.md)), and experiment metrics as Markdown files in the artifact directory:
  `<appDataDir>\brain\<conversation-id>\`
  Supports GitHub alerts (`> [!NOTE]`, `> [!IMPORTANT]`), diff blocks, tables, and mermaid diagrams.
- **Clickable Links:** All file and symbol references in agent responses must be formatted as clickable Markdown links with the `file://` scheme using forward slashes:
  `[filename](file:///c:/path/to/project/file.ext#L10-L20)`
- **Scratch Files:** Temporary test scripts or exploratory data are stored in `<appDataDir>\brain\<conversation-id>\scratch\`.

---

## 5. Platform & Operational Boundaries

1. **Operating System:** Windows with PowerShell.
   - Path separators: Use forward slashes in Markdown links and standard Windows paths or PowerShell cmdlets in commands.
   - Shell commands: Always execute in `run_command` with an explicit `Cwd` parameter. Never emit `cd` commands.
2. **Reversible Actions:**
   - Apply [`principle-never-block-on-the-human`](../skills/principle-never-block-on-the-human/SKILL.md) for reversible, safe implementation work.
   - Use [`ask_question`](file:///) when irreversible architectural choices, ambiguous requirements, or design fork decisions require user selection.
3. **Dual Compatibility Guarantee:**
   - Both `CODEX_ADAPTER.md` and `ANTIGRAVITY_ADAPTER.md` are first-class adapters.
   - Files under `.agents/skills/*/agents/openai.yaml` are maintained for Codex clients.
   - Antigravity parses `SKILL.md` directly and ignores Codex-specific metadata safely.
