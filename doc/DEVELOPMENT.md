# Development guide

This integration runs inside Home Assistant; there is no separate build step.
Use local tests for Python logic and a real Home Assistant instance for entity,
config-flow, recorder, and lifecycle compatibility.

## Getting started

1. Clone the repository and read [AGENTS.md](../AGENTS.md) for the guidance map.
2. Prefer an isolated task worktree on a topic branch. Agents ask whether to
   create or reuse one before editing unless the user already requested it.
   Follow the shared
   [worktree skill](../.agents/skills/git-worktrees/SKILL.md).
3. Use the latest stable Python 3 to match the
   [Validate code workflow](../.github/workflows/validate-code.yml). When testing inside HA,
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

CI currently runs syntax checks and pytest on the latest available stable
Python 3 (`3.x` with `check-latest: true`) on PRs to `main` and manual dispatch,
publishing a JUnit report when permitted. Commits entering `main` are validated
by the beta publication workflow.

The workflow and its job are named **Validate code**. Every PR targeting `main`
runs this job without path filters. After the check has appeared on a PR,
select **Validate code** in the branch rules' required status checks to require
syntax checking and the complete integration/release-tooling test suite.

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

### Automatic betas

**Tag beta release** runs on pushes to `main` and manual dispatch.
It processes every commit newly reachable from `main` after `start_commit` in
[release-config.json](../.github/release-config.json), oldest dependencies first.
The bootstrap anchor excludes historical commits; leave it unchanged after
enabling publication. Multiple commits in one push each receive a beta, including
branch commits introduced by a merge. Squash merges avoid publishing unfinished
intermediate branch commits.

Each candidate is validated in a temporary local Git clone with its exact commit
checked out in detached-HEAD mode. This preserves Git metadata for tests that
discover the repository root. The workflow installs that commit's test/runtime
requirements, checks syntax, and runs its test suite before packaging tracked
integration files from a separate Git archive. A failed candidate
stops the batch without publishing it. Inspect the workflow log before retrying;
fixing only a later commit does not make the failed historical commit pass.

Versions are allocated from tags and published stable releases, not from the
repository manifest. With latest stable `v1.0.25`, the first cycle is
`v1.0.26-beta.1`, `v1.0.26-beta.2`, and so on. Every successful candidate gets a
GitHub prerelease with a flat `mijnted.zip` asset, containing the matching
manifest version without the tag's `v` prefix. The tracked manifest remains
`0.0.0-dev.0`; no versioning commits are pushed to `main`.

For a minor or major cycle, change `next_version` from `null` to a core version
such as `"1.1.0"` or `"2.0.0"` through a normal PR. A target cannot move an
active higher cycle backwards. Once that target is released, it is consumed
automatically and the next patch becomes the default; resetting it to `null`
is optional housekeeping.

### Promoting to stable

1. Open GitHub **Actions → Promote release → Run workflow**.
2. Select branch **main**.
3. Enter the beta tag, such as `v1.0.26-beta.3`, or leave it empty to use the
   published beta for the current `main` commit.
4. Choose **version_bump**: **patch** (default), **minor**, or **major**.
5. Run the workflow. If an empty input reports no beta for `main`, wait for
   **Tag beta release** to finish or rerun it, then retry promotion.

The selected bump is calculated from the latest published stable version,
not by incrementing the beta's version. For stable `v1.0.25` and beta
`v1.0.26-beta.3`:

| Selection | Stable release | Next default beta cycle |
|---|---|---|
| `patch` | `v1.0.26` | `v1.0.27-beta.1` |
| `minor` | `v1.1.0` | `v1.1.1-beta.1` |
| `major` | `v2.0.0` | `v2.0.1-beta.1` |

Minor and major bumps reset the lower version components to zero. A beta from
an already-released version cycle cannot be promoted again to a new release.
For an explicitly configured higher beta cycle, choose a bump that reaches at
least that beta's core version; promotion never lowers its version.

Promotion downloads the selected beta's existing integration ZIP and changes
only its manifest version to the calculated stable version. It tags the same
source commit, publishes a full release marked latest, and carries over beta
release notes with the source tag, commit, and selected bump recorded. Existing
beta releases stay available. Selecting an older beta is supported even when
`main` has advanced.
Existing stable tags cannot be moved, and stable versions cannot go backwards.

After promotion, new commits normally start the next patch's beta cycle shown
above. An already-active higher minor/major cycle continues instead.
Promotion does not create a new commit or immediately publish a beta for the
unchanged `main` tip.

### Permissions, retries, and validation

Both publishers use a GitHub App installation token to create tags and manage
releases. Historical commits can differ from current `main` in workflow files;
GitHub then requires Workflows write permission for tag/release operations.
The built-in `GITHUB_TOKEN` cannot receive that permission, even with
`contents: write`. See GitHub's
[release API permission requirements](https://docs.github.com/en/rest/releases/releases#create-a-release).

Configure a release App, such as **MijnTed Release Orchestrator**:

1. Register a GitHub App with repository **Contents: Read and write** and
   **Workflows: Read and write**. Metadata read access is automatic. Webhooks
   and user OAuth authorization are unnecessary for installation-token use.
2. Install the App on this account and grant access to this repository.
3. Generate a private key in the App settings.
4. In repository **Settings → Secrets and variables → Actions**, add:

   | Kind | Name | Value |
   |---|---|---|
   | Repository variable | `RELEASE_APP_ID` | Numeric App ID |
   | Repository secret | `RELEASE_APP_PRIVATE_KEY` | Complete downloaded PEM private key, including its headers |

The workflows check these settings before validation, generate a short-lived
token scoped to the current repository, and request Contents and Workflows write
access explicitly. Checkout credentials and `GH_TOKEN` both use this App token,
so Git tag pushes and GitHub release operations have the same permissions. The
token action revokes it at job completion; the built-in workflow token only has
Contents read access. No bypass permission for `main` is needed. Tag rules must
allow these release tags. Normal publication requires dispatch from `main`.

To verify App setup without publishing, manually run **Tag beta release** with
`verify_only` enabled. This mode may run from a topic branch before its workflow
changes are merged; it requests the actual Contents/Workflows write permissions
and checks GitHub API and Git repository access, but skips publication. Normal
beta publication and stable promotion still run only from `main`.

If token creation fails, check the App ID/private key pair, repository
installation, and App permissions. After changing App permissions, approve
the installation's updated permissions in GitHub before retrying. A GitHub CLI
login's `workflow` scope does not change the workflow's built-in token.

Test and release workflows select the latest available stable Python 3 using
`python-version: "3.x"` and `check-latest: true`. The interpreter can therefore
advance to a new minor version without a workflow edit.

Both publishers use the same concurrency group without cancelling running
publication. GitHub may replace a pending run with a newer one; reconciliation
on the next push or manual beta dispatch recovers missing commits.
Each run works with a fetched main snapshot. A commit arriving during promotion
is handled by the next beta run.

Packages are attached to draft releases before publication. Rerunning a failed
workflow repairs unfinished drafts, preserving the assigned tag/version.
Published betas are skipped, and repeating the same completed promotion is a
no-op even though the latest stable version has advanced. An unfinished
promotion keeps its original target; retry with the original bump selection
rather than creating a second release for the same beta. Tags are never
force-updated. If a workflow times out on a large batch,
rerun **Tag beta release**; already-published commits are not tested again.

Validate release tooling locally without publishing:

```sh
python -m pytest .github/scripts/release.test.py -q
git diff --check
```

Do not run `python .github/scripts/release.py beta` or `promote` locally just to test:
these commands publish real tags/releases using the authenticated `gh` CLI.
Use workflow logs and a real HACS installation to verify the first published
ZIP can be installed and reports its stamped version. Older releases have no
ZIP asset; their existing tags/assets are not rewritten by these workflows.
