# Agent instructions

This file is the first place to look for how to work in this repo.

## Basic instructions

- **Purpose**: You are helping develop the **Home Assistant MijnTed** custom integration (Python). It talks to the MijnTed cloud API and exposes energy usage and device data as sensors and buttons in Home Assistant.
- **Where the code lives**: Integration code is under `custom_components/mijnted/`. Entry point: `__init__.py`. No separate build step; it runs inside Home Assistant.
- **Quick validation**: Use `python -m compileall custom_components/mijnted` to run a fast syntax check. If sandboxed execution cannot write `__pycache__`, rerun it outside the sandbox.
- **Validation scope outside HA**: This repo is not always executed in a full Home Assistant runtime during local checks. Treat HA-environment/runtime-specific failures as non-blocking for local validation, but treat Python syntax/parse errors as blocking.
- **Git commands**: Always run `git` commands outside the sandbox — the sandbox lacks permissions for git operations.
- **File deletion policy**: Always run file-removal commands (for example `Remove-Item`, `del`, `git rm`) outside the sandbox with escalation.
- **Before making changes**: Read the relevant instructions in `.github/instructions/` (see below). Follow existing code style and conventions.

## Where to find instructions

- **Detailed instructions**: `.github/instructions/` - the real, specific guidance lives here. Files are task- and area-specific (repo overview, layout, conventions, coding guidelines, docstrings, orchestration, sensors, API/auth, documentation, testing, etc.). Each has YAML frontmatter and `applyTo`; read the ones that match the files you are editing. `AGENTS.md` stays short; the instructions there are extensive.
- **Documentation map (direct)**:
  - `README.md` - user-facing install, configuration, usage, troubleshooting
  - `doc/SENSORS.md` - sensor catalog, purpose, attributes, edge cases
  - `doc/MONTH_SWITCH.md` - month-transition timeline and expected behavior
  - `doc/ENDPOINTS.md` - API endpoint and auth reference
- **Documentation map (indirect)**:
  - `.github/instructions/documentation.instructions.md` - when and how to keep docs in sync
  - `.github/instructions/sensors.instructions.md` - sensor behavior expectations
  - `.github/instructions/api-auth.instructions.md` - API/auth documentation expectations
  - `.github/instructions/coding-guidelines.instructions.md` - code structure principles (SRP, naming, DRY, refactors)
  - `.github/instructions/docstrings.instructions.md` - comments and docstring conventions for production code

## Preparing a change

Work happens on a **topic branch** (feature, enhancement, fix, etc.). No dedicated "release branch"; releases are created by **tagging on main** after the PR is merged.

- **Branch**: If you are already on a topic branch that has a version bump commit, continue working on it — do not create a new branch. Otherwise, create a branch from the default branch (e.g. `fix/xyz`, `feature/abc`).
- **First commit**: Bump **version** in `custom_components/mijnted/manifest.json` (semantic versioning: patch for fixes, minor for new features, major for breaking changes). Commit with a clear message (e.g. `Bump version to 1.0.22`). Skip this step if the current branch already contains a version bump.
- **Next commits**: Implement the fix or feature in **logically split commits** (one concern per commit, descriptive messages).
- **Push** the branch and **open a PR** targeting the default branch (`main`). Summarize changes and the version bump in the PR description. Request review from `CODEOWNERS` if applicable.
- **Commit messages**: Always write the commit message to a temporary file and use `git commit --file <file>` (then delete the file). Never pass the message inline with `-m` — PowerShell does not support heredoc and mangles parentheses, backticks, and special characters.
- **PR body**: Always write the PR body to a temporary file and use `gh pr create --body-file <file>` (then delete the file). Never pass the body inline with `-m` or `--body` — PowerShell mangles backticks and special characters.

**Releases**: On GitHub, releases are **tags on main**. After the PR is merged to main, create a tag (e.g. `v1.0.22`) on the merged commit and mark it as a release (manually or by the agent). No release branch; tagging happens only after merge.

## Default branch and PR target

- **Default branch**: `main`. All PRs (features, fixes, enhancements) target this branch.

## CODEOWNERS

- See `CODEOWNERS` at the repo root for who to assign or notify for reviews.
