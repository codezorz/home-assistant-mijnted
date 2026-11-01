# Development guide

The [development instructions](../.github/instructions/development.instructions.md)
own contributor and agent rules. This guide explains environment setup,
dependency maintenance, and local verification.

This integration runs inside Home Assistant; there is no separate build step.
Use local tests for Python logic and a real Home Assistant instance for entity,
config-flow, recorder, and lifecycle compatibility.

## Getting started

1. Read [CONTRIBUTING.md](../CONTRIBUTING.md) for the contributor guidance map.
   [AGENTS.md](../AGENTS.md) is the agent entry point; the
   [worktree skill](../.agents/skills/git-worktrees/SKILL.md) covers isolated checkouts.
2. Use the latest stable Python 3 to match [Validate code](../.github/workflows/validate-code.yml).
   When testing inside HA, use the Python version required by that installation.
3. Agents use Bash, including Git Bash or WSL on Windows. Alternative shell
   examples below are for human contributors.

## Local environment

Prefer an existing `~/.venv-home-assistant`. To create it if needed:

```sh
python -m venv ~/.venv-home-assistant
```

In PowerShell, use `python -m venv "$HOME\.venv-home-assistant"` instead.
Activate it before installing dependencies or running Python checks:

| Shell | Activation |
|---|---|
| Bash/zsh | `source ~/.venv-home-assistant/bin/activate` |
| Git Bash with Windows Python | `source ~/.venv-home-assistant/Scripts/activate` |
| PowerShell | `& "$HOME\.venv-home-assistant\Scripts\Activate.ps1"` |
| Windows cmd | `%USERPROFILE%\.venv-home-assistant\Scripts\activate.bat` |

Use the environment created by the Python interpreter in that shell: Linux/WSL
environments use `bin/activate`, while Windows Python uses `Scripts/activate`.
Do not share one virtual environment between Windows Python and WSL Python.

From the active checkout's root:

```sh
python -m pip install uv
python -m uv export --locked --no-hashes --no-emit-project --format requirements-txt --output-file requirements_test.txt
python -m pip install -r requirements_test.txt
```

`pyproject.toml` declares runtime dependency inputs and the `dev` test group;
`uv.lock` pins their full transitive graph across supported platforms. The
project is virtual (`package = false`), so installing these dependencies does
not build or install the integration as a Python package. The development
project targets Python 3.11 and newer; use the latest stable Python for CI parity.

`requirements_test.txt` is an ignored, generated pip export, recreated by the
commands above and by CI/release validation. It is not a dependency source to
edit or commit. Exporting with `--locked` rejects stale project metadata rather
than silently changing the lock. Regenerate the export after every lock update.

Home Assistant continues to install runtime requirements from
`custom_components/mijnted/manifest.json`. Keep those inputs mirrored in
`pyproject.toml`; a test checks their names and constraints match. The lock
describes the development/validation environment, while HA owns its installed
runtime environment.

Tests mock Home Assistant and do not need a full HA installation. A shared venv
can serve worktrees with compatible requirements; use a separate environment
when a task needs conflicting dependency versions. Do not copy environments
or credentials between checkouts automatically.

## Dependency maintenance

Commit `pyproject.toml` and `uv.lock` together. To resolve intentional input
changes, run `python -m uv lock`; to refresh all pinned versions, run
`python -m uv lock --upgrade`. Then recreate the pip export using the command
above, install it, and run the relevant tests. Check metadata/lock consistency
without updates using `python -m uv lock --check`.

[Aikido supports `uv.lock`](https://help.aikido.dev/code-scanning/scanning-practices/python-projects-security-scanning-best-practices)
for Python dependency scanning, including exact transitive dependency versions.
The [Dependabot configuration](../.github/dependabot.yml) uses the `uv` ecosystem to
update the project metadata and lock weekly, grouping Python updates and
retaining the existing major-version ignore policy. GitHub Actions updates
remain in their separate weekly group. Generated pip exports are created at
installation time so lock-only updates cannot leave a committed export stale.
Review runtime constraint changes against the HA manifest as well.

## Checks appropriate to the change

| Change | Checks |
|---|---|
| Documentation / development guidance | `git diff --check`; verify local links, imports, skill metadata, and referenced code behavior |
| GitHub Actions workflows | `actionlint <changed-workflow>`; `git diff --check`; relevant tooling tests if script behavior changes |
| Dependency inputs / lock | `python -m uv lock --check`; regenerate/install the pip export; `python -m pytest -q` |
| Integration Python | `python -m compileall custom_components/mijnted`; relevant existing tests |
| Cache, date, or statistics behavior | Target affected tests, including rollover, API lag, zero/missing values, and late corrections |
| Broad integration changes | `python -m pytest -q`, plus an HA smoke test for runtime-sensitive behavior |

Example targeted run: `python -m pytest tests/test_config_flow.py -q`.
[Testing instructions](../.github/instructions/testing.instructions.md) own mock boundaries and test
design. Add tests for meaningful behavioral changes; documentation-only edits
do not need application tests.

Syntax errors and failed behavioral assertions are blocking. If syntax checking
cannot write `__pycache__` in a sandbox, rerun in an allowed execution context.
Missing dependencies should be resolved in the environment above. A limitation
that specifically requires real HA is a remaining runtime-verification gap,
not a passing test or a reason to ignore an assertion failure.

## Home Assistant smoke test

1. Copy this checkout's `custom_components/mijnted` to a test HA installation's
   `custom_components` directory and restart HA to load changed Python code.
2. Add or reload MijnTed and verify the affected sensors/buttons, availability,
   and config/options flow. Reloading an entry alone is not a reliable way to
   load edited Python modules.
3. For recorder changes, verify imported statistics with recorder enabled.
   Follow [MONTH_SWITCH.md](MONTH_SWITCH.md) for boundary scenarios and
   [SENSORS.md](SENSORS.md) for expected attributes/fallbacks.
4. Enable logging as described in [README.md](../README.md#troubleshooting)
   and inspect relevant errors. Report the HA version and what was exercised.

## Related guidance

- [CI and fork approvals](CI.md)
- [Agent setup and discovery](../.github/instructions/agent-tooling.instructions.md#local-agent-setup)
- [Brand artwork](../.github/instructions/layout.instructions.md#brand-artwork)
- [Git/GitHub policy](../.github/instructions/git-workflow.instructions.md) and [release operations](RELEASING.md)
- [Tool-agnostic security triage](../.github/instructions/security-triage.instructions.md)
