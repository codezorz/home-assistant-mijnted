# Development instructions

This directory holds development instructions and authoritative repository
policies for contributors and coding agents. Start with
[AGENTS.md](../../AGENTS.md) for the guidance map.

- Use `*.instructions.md` files with `applyTo` and `description` frontmatter.
- Keep Git/GitHub policy, including PR issue references and closure, in
  [git-workflow.instructions.md](git-workflow.instructions.md).
- Put on-demand workflows and tool-specific references in
  [`.agents/skills/`](../../.agents/skills/README.md). Keep integration reference
  and detailed contributor/maintainer guides in [`docs/`](../../docs/README.md).
- Keep these scoped rules concise and link detailed guides rather than copying
  their commands and operational explanations into automatically loaded files.

## Start here

- [Development setup and checks](development.instructions.md)
- [Testing](testing.instructions.md) and [CI](ci.instructions.md)
- [Git/GitHub policy](git-workflow.instructions.md) and [release operations](../../docs/RELEASING.md)
- [Security triage, independent of scanner](security-triage.instructions.md)
- [Agent tooling](agent-tooling.instructions.md)

Follow [documentation ownership](documentation.instructions.md) and
[agent-tooling guidance](agent-tooling.instructions.md) when adding guidance.
See [CONTRIBUTING.md](../../CONTRIBUTING.md) for the contributor entry point.

## Placement conventions

GitHub supports [contributor guides](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors)
in several locations and [scoped instructions](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions)
in `.github/instructions/`. The [Agent Skills specification](https://agentskills.io/specification)
supports on-demand `references/` material. Both integration and contributor
documentation can live in `docs/`; development rules stay here. Keep entry
points short, guidance scoped, and each policy authoritative in one place.
