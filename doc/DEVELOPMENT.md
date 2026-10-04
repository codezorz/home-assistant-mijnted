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

## Brand artwork

The root [`icon.svg`](../icon.svg) is a scalable trace of the original 128 x 128
favicon from <https://mijnted.nl/favicon@128.png>. It preserves the red
house/heart artwork and transparent background, with smoothed outer heart and
hand curves on the right edge to remove favicon clipping artifacts. Export the
SVG when updating the PNG images: root [`icon.png`](../icon.png) and
`custom_components/mijnted/brand/icon.png` at 256 x 256, and the integration's
`icon@2x.png` at 512 x 512. Home Assistant uses the integration's PNG exports,
not the SVG.

For example, with Inkscape installed, run from the checkout root:

```sh
inkscape icon.svg --export-width=256 --export-height=256 --export-filename=icon.png
inkscape icon.svg --export-width=256 --export-height=256 --export-filename=custom_components/mijnted/brand/icon.png
inkscape icon.svg --export-width=512 --export-height=512 --export-filename=custom_components/mijnted/brand/icon@2x.png
```

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

### PR labels and beta targets

Before merging, apply at most one release label:

| Label | Release intent |
|---|---|
| `release:patch` | Next patch after the latest stable; the default without a release label |
| `release:minor` | Next minor after the latest stable, with patch reset to zero |
| `release:major` | Next major after the latest stable, with minor and patch reset to zero |

These labels are independent of type labels such as `bug` or `enhancement`.
The boundary is **integration behavior**, not the size of the diff:

- Operational-only work (CI, release automation, agent tooling, documentation)
  and routine nonbreaking fixes use normal betas without a release label or question.
- For new integration features, agents ask for patch, minor, major, or normal
  betas with no label, unless the user already chose. Recommend minor for
  backward-compatible features.
- Breaking integration behavior requires a major-version discussion, even
  when introduced by a bug fix.

No label already supplies default patch intent; an explicit patch label is
unnecessary just to continue normal betas.

The beta publisher identifies the PR's merge commit into `main` and reconstructs
its labels from GitHub issue events up to that merge. Labels on open PRs have no
effect, and label changes after merge do not alter the release intent. Direct
pushes and intermediate branch commits default to patch; a PR's label applies
at its merge commit. Prefer squash merges so the labelled change gets one beta.

The highest bump accumulates **since the latest published stable**, not from the
current beta version. With latest stable `v1.0.23`:

| Merged PR | New beta |
|---|---|
| Patch / unlabelled | `v1.0.24-beta.1` |
| Minor | `v1.1.0-beta.1` |
| Another minor | `v1.1.0-beta.2` |
| Patch / unlabelled | `v1.1.0-beta.3` |
| Major | `v2.0.0-beta.1` |

Each assigned beta tag preserves the accumulated target for subsequent commits
and retries. Existing higher-version cycles, including legacy `v1.1.0` betas,
cannot move backwards. `release-config.json` contains only the bootstrap anchor;
there is no `next_version` override. After a stable release, its version becomes
the new baseline and requests included in it are consumed.

An urgent fix merged while a minor-labelled feature PR is still open stays in
the patch cycle. Once the feature merges, its minor target takes effect. A fix
merged after the feature includes that feature's code and remains in its cycle.

Conflicting release labels at merge stop publication rather than guessing a
target; verify labels before merging. Missing merge-event metadata also stops
publication and can be retried once GitHub exposes the event. Tag reservation
freezes assigned versions; draft retries never reassign a tag from current labels.

### Promoting to stable

1. Open GitHub **Actions → Promote release → Run workflow**.
2. Select branch **main**.
3. Enter the beta tag, such as `v1.0.26-beta.3`, or leave it empty to use the
   published beta for the current `main` commit.
4. Run the workflow. If an empty input reports no beta for `main`, wait for
   **Tag beta release** to finish or rerun it, then retry promotion.

Promotion has no bump choice. It removes the beta suffix and publishes the
**same core version**:

| Selected beta | Stable release | Next default beta cycle |
|---|---|---|
| `v1.0.26-beta.3` | `v1.0.26` | `v1.0.27-beta.1` |
| `v1.1.0-beta.2` | `v1.1.0` | `v1.1.1-beta.1` |
| `v2.0.0-beta.1` | `v2.0.0` | `v2.0.1-beta.1` |

The beta's core version must exceed the latest stable version, and its commit
must be newer than and descend from the latest stable commit. Repeating an
already-completed promotion is a no-op. A later beta from an already-released
core cannot overwrite that stable or be renumbered during promotion.

Promotion downloads the selected beta's existing integration ZIP and changes
only its manifest version to the calculated stable version. It tags the same
source commit, and publishes a full release marked latest with the stable tag
as its title. GitHub generates fresh release notes from the previous published
stable tag to the selected source commit, including a stable-to-stable full
changelog link (for example, `v1.0.25...v1.0.26`). Beta notes are not copied into
the stable release. The source beta tag and commit are recorded
in the Actions log. Draft retries refresh the stable release notes as well.
Existing beta releases stay available. Selecting an older beta is supported
even when `main` has advanced.
Existing stable tags cannot be moved, and stable versions cannot go backwards.

After promotion, new commits default to the next patch's beta cycle shown above.
The counter starts at one unless tags already exist for that cycle, in which
case it continues after the highest reserved beta number. An already-active
higher cycle continues instead, and labels on newly merged PRs may raise the target.
Existing legacy betas retain their core version and promote to matching stable
versions; deleting the old override does not send numbering backwards.
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
token action revokes it at job completion. The beta workflow separately uses
the built-in `GITHUB_TOKEN` with Contents, Issues, and Pull requests read access
to query PR associations and label history. It passes that token as `GH_READ_TOKEN`
only to metadata reads; publishing continues to use the App token. The release
App needs no additional permissions for labels. No bypass permission for `main`
is needed. Tag rules must allow these release tags. Normal publication requires
dispatch from `main`.

To verify App setup without publishing, manually run **Tag beta release** with
`verify_only` enabled. This mode may run from a topic branch before its workflow
changes are merged; it requests the actual Contents/Workflows write permissions
and checks GitHub API, label metadata, and Git repository access, but skips
publication. Normal beta publication and stable promotion still run only from `main`.

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
promotion keeps its original target; retry with a beta of the original core
version rather than creating a second release for the same commit. Historical
unfinished promotions created with a different stable target must be recovered
before switching to matching-core promotion. Tags are never
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
