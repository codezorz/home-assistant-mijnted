---
applyTo: "AGENTS.md,CLAUDE.md,.agents/**,.claude/**,.github/instructions/**,tests/test_agent_guidance_hook.py"
description: Shared guidance metadata and Claude's metadata-only session-start hook; keep skill bodies tool-neutral.
---

# Agent tooling

- Keep shared skill bodies in `.agents/skills/<name>/SKILL.md`, never `.agent/`
  or a duplicated `.claude/skills/` tree. Use required `name` and `description`
  frontmatter; the lowercase hyphen-separated name must match its directory.
- Use capability-based names for repo-local skills (`doc-sync`, `pr-workflow`,
  `validation`). Reserve repository prefixes for globally distributed skills
  or when needed to avoid a naming collision; describe repository scope in
  the skill's description.
- Instruction frontmatter requires `applyTo` and `description`. Scope all
  applicable files, including entry/platform files and relevant tooling.
- For metadata consumed by the hook, keep values on one line. Use comma-separated
  globs for `applyTo`; plain or single/double-quoted scalar values are supported.
  Do not use YAML block scalars, lists, anchors, or multiline values. Quote
  descriptions containing YAML-significant characters such as `: ` or ` #`.
- `.claude/hooks/list-guidance.sh` reads headers only and prints a deterministic
  index of relative paths, skill triggers, and instruction scopes. It never
  executes metadata, copies bodies, or registers native slash commands.
- `.claude/settings.json` runs that script through Bash on `SessionStart`
  (`startup`, `resume`, `clear`, `compact`). Git discovers the active worktree
  root; `CLAUDE_PROJECT_DIR` is preferred when provided.
- `CLAUDE.md` imports `AGENTS.md` and README. The index tells Claude to read
  matching skills and all applicable instructions in full before that work.
  `applyTo` is a relevance selector, not a mechanism for silently overriding
  conflicting rules; resolve contradictions instead of maintaining two policies.
- Keep the hook dependency-free beyond Bash, Git, and awk (available in Git Bash
  on Windows). Follow `AGENTS.md` for the Bash-only agent shell convention and
  verify hook configuration after editing.
- Run `python -m pytest tests/test_agent_guidance_hook.py -q` for hook changes;
  see `doc/DEVELOPMENT.md` for the test environment and Claude setup.
