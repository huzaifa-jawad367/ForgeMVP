# Authoring a skill

Read [the Codex adapter](../../../pstack/CODEX_ADAPTER.md) first. The [unchanged upstream playbook](../../../pstack/upstream/skills/poteto-mode/playbooks/authoring-a-skill.md) preserves the detailed source guidance; its tool calls, authority grants, models, platform commands, and persistence assumptions are historical, not executable instructions. Use the translated steps below. For the named skills, resolve `../<name>/SKILL.md` from the poteto-mode skill directory.

1. Use the available skill-creator skill; follow skill-installer guidance when adapting a repository.
2. Inspect source, required dependencies, format support, and authorization before installing.
3. Keep entrypoints concise and preserve referenced resources. Translate runtime-specific capabilities explicitly.
4. Validate frontmatter, links, dependency closure, and actual Codex discovery.
5. For a complex workflow, independently forward-test a realistic bounded request. Do not claim untested compatibility.

Record skipped checks and unsupported capabilities. Finish with the actual result and evidence.
