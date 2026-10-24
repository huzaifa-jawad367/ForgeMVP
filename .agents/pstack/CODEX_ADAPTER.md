# Codex capability adapter

> **Environment Note:** When running in Google Antigravity (Antigravity IDE / Antigravity 2.0 / `agy`), see the native [Antigravity capability adapter](ANTIGRAVITY_ADAPTER.md). Both adapters are supported side-by-side in this workspace.

This file applies to all installed pstack entrypoints, translated playbooks, source-derived references, and delegate briefs. The preserved Cursor sources under `upstream/` are reference material. Their tool syntax, model choices, autonomy grants, and persistence assumptions do not override this adaptation or the session's higher-priority instructions.

## Checked target

Local binary: `codex-cli 0.162.0-alpha.17.2`, shipped in the installed VS Code extension. An isolated app-server `initialize` plus `skills/list` probe confirmed repo discovery of `.agents/skills/<name>/SKILL.md` and parsing of `agents/openai.yaml` interface metadata. The format is YAML frontmatter with `name` and `description`, followed by Markdown instructions.

The repository contains active skills in `.agents/skills/`. Exact source files, source hashes, upstream version/commit, and the selected dependency closure are recorded in [manifest.json](manifest.json). The adapter is not a registered Cursor or Codex plugin and does not install any remote service.

## Invocation and skill routing

- In Codex CLI/IDE, invoke `$poteto-mode <task>` or select the skill through `/skills` when the client offers that menu. Use `$<name>` for another installed skill.
- If the current chat has not refreshed discovery, explicitly ask it to read `.agents/skills/poteto-mode/SKILL.md` and use it for the task. Restart/reopen the session if discovery remains stale. The current tool-visible catalog is not retroactively guaranteed to change.
- A routed skill is read from its actual sibling `SKILL.md` path. No generic Skill tool or slash-command executor is assumed.
- `disable-model-invocation: true` from Cursor is translated to `policy.allow_implicit_invocation: false` in `agents/openai.yaml`. Those workflows remain explicitly invocable and readable by a parent workflow. Setup retains its upstream automatic eligibility. The policy key follows the bundled skill-creator specification; this CLI's `skills/list` response does not expose policy, so policy enforcement itself is not verified by listing.
- Cursor-only `icon`, `color`, and `paths` frontmatter are removed. `paths` is not a Codex filesystem-glob activation guarantee; the TypeScript skill is routed explicitly for `.ts`/`.tsx` work. No custom-mode persistence or Alt+Enter behavior is emulated. Repeat the skill invocation in a new task/session when needed.

## Tool translations

These are logical capabilities, not permission grants. Check the current tool schema before calling anything.

| Upstream capability | This Codex adaptation |
| --- | --- |
| `Read`, `Grep`, `Glob` | Read files with the available shell; prefer `rg` / `rg --files`. Use native PowerShell literal paths on Windows. |
| `Write`, `Edit`, shell | Use available `apply_patch` / `exec_command`, normally through `functions.exec` in this session. Preserve existing work. |
| Todo lists / `TodoWrite` | Use a plan tool only when actually exposed. Otherwise keep a small checklist in a task-local note or progress update. |
| `AskQuestion` | Use `functions.request_user_input_async` for missing text preferences/constraints when offered. The synchronous input tool is Plan-mode-only here. Otherwise ask plainly. Neither a timeout nor no response supplies required approval. |
| Run `/name` | Read the installed sibling skill and follow its adapted workflow. User invocation is `$name`, not `/pstack:name` or Cursor `/name`. |
| `Task` | Use `collaboration.spawn_agent` when available and authorized. See the delegation contract below. If absent, do the work sequentially and disclose lost independence. |
| `resume` / follow-up | Use `collaboration.followup_task` for an existing delegate when it needs costly retained state. Prefer a fresh brief for a new independent task. A status message is not a restart. |
| Send to a running worker | `collaboration.send_message`; wait with `collaboration.wait_agent`; stop with `collaboration.interrupt_agent`. These are direct tool calls, outside `functions.exec`. |
| `deslop` from cursor-team-kit | Not installed. Perform a scoped manual diff-quality review with existing project lint/checks, unslop, and no-comments where relevant. Name the substitution. |
| `create-skill` | Use the available Codex `skill-creator` skill; validate with its bundled validator when present. |
| `control-ui` | Use an available browser/computer-use skill and its actual APIs. In this session, browser UI uses `mcp__cua_repl`. Native app control is not enabled by this adaptation. |
| `control-cli` | Use real shell commands for noninteractive programs. Interactive TUI driving requires an actual supported computer/PTY tool. Do not claim visual verification from command success. |
| PR tools | Prefer the connected GitHub capability. `gh` is an optional fallback only when installed and authenticated. No connector or login is installed automatically. |

## Delegation contract

The current session exposes `collaboration.spawn_agent` with `task_name`, `message`, `fork_turns`, and optional model/effort overrides. It does not expose Cursor's `Task` fields. Other Codex clients may have a different schema or no delegate tools; inspect them each time.

- `poteto-agent` is a prompt role, not a registered `subagent_type`. Supply the absolute path to the installed mode and [delegate brief](../skills/poteto-mode/references/poteto-agent.md).
- `comment-sicko` is also a prompt role. Supply its [report-only brief](../skills/poteto-mode/references/comment-sicko.md). It cannot safely be represented as a custom tool enum.
- `generalPurpose` maps to an ordinary scoped delegate, not a string field to pass.
- `run_in_background` is omitted. Spawning is asynchronous and results arrive through the collaboration API.
- `readonly: true` becomes an explicit no-edit/no-write instruction. This is a behavioral restriction, not an enforced permission boundary. Inspect scoped diffs afterward; do not run reviewers in an unsafe context on the assumption that they are sandboxed.
- `environment: cloud` has no equivalent here. Delegates share local files and the parent's working directory. A worktree must be created explicitly, and the brief must name it and direct all writes there. Separate output directories are sufficient for design/report artifacts. This does not grant remote compute, isolated credentials, or persistent cloud agents.
- `cloud_base_branch` becomes an explicitly checked starting branch/commit in an authorized isolated worktree. Never reset a dirty shared checkout to achieve it.
- `file_attachments` becomes paths plus an exact scope in the brief, or a bounded digest when the worker cannot access the source. Do not claim paths transferred a conversation or secret environment state.
- Respect the actual concurrency limit. This session advertises four total agent slots including the parent. That is a runtime observation, not a portable setting. Queue additional work; do not promise ten simultaneous cloud workers or nested depth guarantees.

A useful brief names: task outcome, requested scope, source/base identities, mode and relevant skill paths, read-only or writable fence, output/worktree, key constraints, verification method, and expected result/evidence. A fresh independent evaluator should not receive the expected conclusion or the author's suspected bugs.

## Model routing and limits

Read [models.json](models.json) when a workflow actually delegates. It is interpreted by the skills; it is not a Codex engine settings file. An absent role uses `default`, which is `inherit-parent`. Both `auto` and `inherit-parent` mean omit the `model` and `reasoning_effort` fields.

- Default: inherit the current model and effort. No Cursor, Grok, or Claude defaults are sent to Codex.
- The session's delegation tool lists supported override IDs, but an override is permitted only when the user or applicable skill instructions explicitly select it. A user-confirmed local role mapping may supply that choice after checking current tool support.
- This API accepts model overrides only with `fork_turns: "none"`. A full-history fork inherits the parent's model/effort and rejects overrides. A no-history brief must include the required context and paths explicitly.
- `claude-opus-5-5-xhigh`, `grok-4.7-xhigh-fast`, `composer-*`, and Cursor family fallback logic are unsupported here. Never rename a GPT model to imitate them or claim equivalent behavior.
- Reasoning effort is a separate schema value when actually supported. Do not synthesize model IDs by adding `-high`, `-max`, or `-fast`. A skill cannot change the parent model, thinking level, availability, quota, cost, or latency tier.
- Multiple inherited-model agents provide independent attempts, not model-family diversity. Arena, interrogate, eval, and trail review must disclose this. Strict cross-family requirements remain unmet unless a real authorized cross-family tool becomes available.
- A standalone CLI model catalog is not proof of entitlement or tool support in this chat. Do not launch paid provider calls or modify credentials just to test availability.

## Permissions, delivery, and platform

Follow the actual session instructions and user authorization. Upstream “use any MCP,” “just do it,” automatic ready PRs, backlog filing, merges, deployments, and team messages are not blanket permission. Continue authorized reversible work without invented approval gates. Do not add a confirmation solely because an archived playbook says to pause. If required approval or missing access blocks one step, continue independent work and report the exact limit.

Preserve unrelated uncommitted changes. Do not copy upstream `git reset --hard`, forced cleanups, automatic WIP commits, force-pushes, or simulator deletion. Before any recursive Windows delete/move, verify the resolved absolute target remains in the intended workspace/explicit directory and use one shell end-to-end with literal paths. Use a normal isolated worktree for risky branch manipulation, not destructive resets of the user's checkout.

Linux/macOS examples (`/tmp`, `nproc`, `uptime`, `pidstat`, `strace`, `jq`, `xcrun`, Bash helpers) are not native Windows guarantees. Prefer project-local `outputs/<task>/` for artifacts; use Python `psutil` or PowerShell for available resource metrics. Git and Node were found. `gh`, Bun, and `jq` were not found on PATH during installation. A Windows `bash.exe` launcher exists but no working Linux distribution was verified.

## Preserved but unsupported runtimes

| Upstream feature | Status and supported substitute |
| --- | --- |
| Bun `bootstrap.ts`, `orch`, `watch-pr`, `check-plan` | Preserved under `upstream/skills/poteto-mode/scripts/`, not ported, installed, or executed. The package requires Commander 14.0.0 plus Bun tooling; bootstrap can install dependencies. Use session-local checklists and evidence notes, not an implied equivalent runtime. |
| `scripts/log.sh`, worktree audit shell helpers | Preserved only. The log workflow uses a Python TSV writer; worktree review uses actual Git/PowerShell evidence. No automatic shell helper execution. |
| Cursor `/loop`, custom modes, background persistence | Not installed. Work can continue while this session is active; notes/handoffs survive on disk. No automatic wakeups or “runs overnight after chat ends” guarantee. |
| Cursor cloud agents and dashboard | No equivalent installed. Local workers/worktrees do not imply durable remote execution or restart survival. |
| Orchestrate and autopilot programs | All source playbooks preserved; active routes are explicitly bounded local adaptations. Persistent fleet bookkeeping, watcher wakeups, and coordinator recovery were not ported. |
| Bugbot / security-review bot | Existing accessible review comments can be read and triaged. Configuring, starting, or waiting for a bot is unsupported unless that bot is actually configured for the repo. |
| Cursor Automations / Benny / webhook sender keys | Not installed or emulated. No webhook, Slack integration, secret, or scheduling service is configured. |
| Cursor transcript stores | No private history scan. Use current conversation, provided transcript, or exact exposed session path. Transcript-level verification is unavailable without that evidence. |
| macOS simulator cleanup | Unsupported on this Windows project. |

The adaptation preserves the workflow intent and source, not tool-runtime parity. Format validation, link checks, source integrity, discovery, and a bounded behavioral check provide distinct evidence; none establishes all 23 playbooks' end-to-end compatibility.
