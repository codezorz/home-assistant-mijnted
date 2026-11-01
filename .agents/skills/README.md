# Shared skills

This directory holds on-demand development workflows shared by coding agents.
Each skill lives in `<name>/SKILL.md` with matching `name` and `description`
frontmatter.

- Skills describe how to carry out a task and link to authoritative policy.
- Keep development instructions and repository policy in
  [`.github/instructions/`](../../.github/instructions/README.md), and integration
  reference documentation and detailed contributor guides in
  [`docs/`](../../docs/README.md).
- Put detailed tool-specific commands and credential/API setup in that skill's
  `references/` directory and link them directly from `SKILL.md` for on-demand use.
- Keep shared skill bodies here; agent-specific configuration should discover
  or reference them rather than maintain copies.

See [agent-tooling guidance](../../.github/instructions/agent-tooling.instructions.md)
for metadata and discovery requirements.
