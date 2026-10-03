# Agent instructions

Start here when working in this repository. This is a Python custom integration
for Home Assistant that exposes MijnTed cloud energy usage as sensors and buttons.
Runtime code lives in `custom_components/mijnted/`; there is no separate build.

## Before editing

- Read the applicable files in `.github/instructions/`. Their YAML `applyTo`
  patterns identify scope; agents without automatic loading must read them explicitly.
- Inspect the current branch, working-tree changes, and registered worktrees.
  Preserve other work and use explicit tool working directories for task checkouts.
- Prefer an isolated task worktree for new editing tasks. Ask whether to create
  or reuse one before starting, unless the user already requested a worktree.
- Shared skills live in `.agents/skills/` (plural). Before creating a worktree,
  load `git-worktrees` or read `.agents/skills/git-worktrees/SKILL.md`.
- Follow the repository's `.editorconfig` and surrounding code style.

## Guidance map

| Task | Authoritative guidance |
|---|---|
| Branches, versions, commits, PRs, labels, releases | `.github/instructions/git-workflow.instructions.md` |
| Environment, validation commands, Home Assistant smoke testing | `doc/DEVELOPMENT.md` |
| Test design and Home Assistant mocks | `.github/instructions/testing.instructions.md` |
| Required documentation updates and ownership | `.github/instructions/documentation.instructions.md` |
| Shared skill metadata and Claude discovery | `.github/instructions/agent-tooling.instructions.md` |
| Code layout | `.github/instructions/layout.instructions.md` |
| Architecture and monthly cache | `.github/instructions/orchestration.instructions.md` |
| Python conventions and design | `.github/instructions/conventions.instructions.md`, `.github/instructions/coding-guidelines.instructions.md` |
| Comments and docstrings | `.github/instructions/docstrings.instructions.md` |
| API/auth changes | `.github/instructions/api-auth.instructions.md` |
| Sensor/button changes | `.github/instructions/sensors.instructions.md` |

User-facing documentation starts at `README.md`; detailed behavior is in
`doc/SENSORS.md`, `doc/MONTH_SWITCH.md`, and `doc/ENDPOINTS.md`.
Use `doc/ISSUE_REPORTING.md` for issue reports and `SECURITY.md` for vulnerabilities.

## Execution boundaries

- Use Bash for shell commands and examples, including on Windows (Git Bash or
  WSL). Use forward-slash paths and quote path variables. If the tool's host
  shell differs, invoke Bash explicitly and keep the tool's working directory
  set to the active checkout. Follow the Bash setup in `doc/DEVELOPMENT.md`.
- Run Git commands outside sandboxed execution where the tool supports it.
- Run file-removal commands outside the sandbox with escalation where supported.
- Do not commit, push, create PRs, merge, or release unless the user requests it.
- For integration changes, the quick syntax check is
  `python -m compileall custom_components/mijnted`; see `doc/DEVELOPMENT.md`
  for the preferred environment and checks appropriate to the change.
