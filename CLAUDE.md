# Claude Code repository context

@AGENTS.md
@README.md

## Shared guidance discovery

The SessionStart hook lists instruction `applyTo` scopes and shared skill
`name`/`description` headers. Read every applicable instruction and each
matching skill in full before doing that work. Paths in the index are relative
to the active checkout root.

Skill bodies live only in `.agents/skills/`; do not create `.claude/skills/`
copies. If the hook is unavailable, inspect headers in `.agents/skills/` and
`.github/instructions/` manually. See `doc/DEVELOPMENT.md` for setup/validation.
