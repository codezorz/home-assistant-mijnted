# Development guide

This integration runs inside Home Assistant; there is no separate build step.
Use local tests for Python logic and a real Home Assistant instance for entity,
config-flow, recorder, and lifecycle compatibility.

## Getting started

1. Clone the repository and read [AGENTS.md](../AGENTS.md) for the guidance map.
2. Use a topic branch. For isolated checkouts, follow the shared
   [worktree skill](../.agents/skills/git-worktrees/SKILL.md).
3. Use Python 3.12 to match the current
   [test workflow](../.github/workflows/python-tests.yml). When testing inside HA,
   use the Python version required by that HA installation.

### Local environment

Agents use Bash, including Git Bash or WSL on Windows. The alternative shell
examples below are for human contributors.

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
python -m pip install -r requirements_test.txt
```

`requirements_test.txt` owns local test dependencies; `manifest.json` owns
Home Assistant runtime requirements. CI installs both. For exact runtime
dependency versions outside HA, install the manifest requirements as well:

```sh
python -c "import json, subprocess, sys; r=json.load(open('custom_components/mijnted/manifest.json', encoding='utf-8'))['requirements']; subprocess.check_call([sys.executable, '-m', 'pip', 'install', *r])"
```

Tests mock Home Assistant and do not need a full HA installation. A shared venv
can serve worktrees with compatible requirements; use a separate environment
when a task needs conflicting dependency versions. Do not copy environments
or credentials between checkouts automatically.

## Checks appropriate to the change

| Change | Checks |
|---|---|
| Documentation / agent guidance | `git diff --check`; verify local links, imports, skill metadata, and referenced code behavior |
| Integration Python | `python -m compileall custom_components/mijnted`; relevant existing tests |
| Cache, date, or statistics behavior | Target affected tests, including rollover, API lag, zero/missing values, and late corrections |
| Broad integration changes | `python -m pytest -q`, plus an HA smoke test for runtime-sensitive behavior |

Example targeted run: `python -m pytest tests/test_config_flow.py -q`.
The [testing instructions](../.github/instructions/testing.instructions.md)
explain mock boundaries and test design. Add tests for meaningful behavioral
changes; documentation-only edits do not need application tests.

Syntax errors and failed behavioral assertions are blocking. If syntax checking
cannot write `__pycache__` in a sandbox, rerun in an allowed execution context.
Missing dependencies should be resolved in the environment above. A limitation
that specifically requires real HA is a remaining runtime-verification gap,
not a passing test or a reason to ignore an assertion failure.

CI currently runs Python 3.12 syntax checks and pytest on PRs to `main`, pushes
to `main`, and manual dispatch, publishing a JUnit report when permitted.

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

## Agent tooling

- Shared instructions: [AGENTS.md](../AGENTS.md) and `.github/instructions/`.
- Shared, on-demand skill bodies: `.agents/skills/<name>/SKILL.md`.
- OpenCode discovers `.agents/skills/`; restart OpenCode after configuration
  or skill changes so a fresh session discovers the updated definitions.
- Claude Code imports shared instructions and README through [CLAUDE.md](../CLAUDE.md).
  Its `SessionStart` hook indexes `applyTo`, `name`, and `description` headers
  from the current checkout. It advertises relevant files without copying skill
  bodies into `.claude/skills/` or eagerly loading every document.
- Start Claude with Bash, Git, and awk available (Git Bash on Windows). Use
  `/context` to verify memory imports and inspect the hook's instruction/skill
  index. Skills are selected from that index and read as files; this does not
  register native `/skill-name` commands. Restart after hook configuration changes.
- For a new instruction or skill, use valid YAML frontmatter with `applyTo`
  or `name`/`description`. The hook picks it up next session without a second
  registration. Its supported metadata format is documented in
  [agent-tooling instructions](../.github/instructions/agent-tooling.instructions.md).
- The hook can also be checked directly from the checkout root with
  `bash .claude/hooks/list-guidance.sh`. Hook changes have focused tests in
  `tests/test_agent_guidance_hook.py`.
- Keep personal Claude preferences in ignored `CLAUDE.local.md` or
  `.claude/settings.local.json`.

## Publishing

Follow the [Git/GitHub policy](../.github/instructions/git-workflow.instructions.md)
for version decisions, commits, PRs, labels, owners, and releases.
