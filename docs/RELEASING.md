# Release operations

[Git/GitHub instructions](../.github/instructions/git-workflow.instructions.md) own version decisions,
PR labels, and publishing permission. This reference covers the publishers'
operation, setup, and recovery. Run publishing only when requested.

## Automatic betas

**Tag beta release** runs on pushes to `main` and manual dispatch.
It processes every commit newly reachable from `main` after `start_commit` in
[release-config.json](../.github/release-config.json), oldest dependencies first.
The bootstrap anchor excludes historical commits; leave it unchanged after
enabling publication. Multiple commits in one push each receive a beta, including
branch commits introduced by a merge. Prepare retained commits under the
[logical-commit and review-update policy](../.github/instructions/git-workflow.instructions.md#commits-and-pull-requests).

The workflow uses three separate jobs: read-only planning, candidate validation,
and trusted publication. Planning freezes the checked-out workflow commit as the
main snapshot and lists its unpublished candidates. Validation checks out each
exact historical candidate in a temporary local Git clone, preserving Git
metadata for repository-discovery tests. It installs that commit's requirements
(exporting its `uv.lock` when present), checks syntax, and runs its test suite.
Candidate subprocesses receive a minimal environment without workflow tokens or
inherited Git authentication settings. The validation runner never receives the
release App private key/token.

Only after the entire planned batch passes does a fresh publication runner mint
the App token. It packages tracked integration files directly from the validated
Git commits, without executing their tests, dependency installers, or build code.
Publication rejects pending commits outside the validated plan, and a newer main
commit is left for a later run. A failed candidate prevents publication of the
whole batch in that run. Inspect the workflow log before retrying; fixing only a
later commit does not make a failed historical commit pass.

Versions are allocated from tags and published stable releases, not from the
repository manifest. With latest stable `v1.0.25`, the first cycle is
`v1.0.26-beta.1`, `v1.0.26-beta.2`, and so on. Every successful candidate gets a
GitHub prerelease with a flat `mijnted.zip` asset, containing the matching
manifest version without the tag's `v` prefix. The tracked manifest remains
`0.0.0-dev.0`; no versioning commits are pushed to `main`.

## Merge-time release intent

Follow the [version policy](../.github/instructions/git-workflow.instructions.md#versioning)
for label selection and confirmation requirements. Integration-changing PRs
record reviewed intent with exactly one release label; operational-only PRs
omit release labels. The publisher retains patch intent as the fallback for
unlabelled PRs and direct pushes. That fallback is not a substitute for the
integration-label policy, and omitting a label does not skip beta publication.

The beta publisher identifies the PR's merge commit into `main` and reconstructs
its labels from GitHub issue events up to that merge. Labels on open PRs have no
effect, and label changes after merge do not alter the release intent. Direct
pushes and intermediate branch commits default to patch; a PR's label applies
at its merge commit. A squash merge produces one beta candidate; preserving
multiple logical commits produces a candidate for each newly reachable commit,
including the merge commit when present. Choose the merge strategy under the
[logical-commit policy](../.github/instructions/git-workflow.instructions.md#commits-and-pull-requests)
and account for this per-commit publication behavior.

The highest bump accumulates **since the latest published stable**, not from the
current beta version. With latest stable `v1.0.23`:

| Merged PR | New beta |
|---|---|
| Patch intent (explicit label or operational-only fallback) | `v1.0.24-beta.1` |
| Minor | `v1.1.0-beta.1` |
| Another minor | `v1.1.0-beta.2` |
| Patch intent (explicit label or operational-only fallback) | `v1.1.0-beta.3` |
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

## Promoting to stable

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
the stable release. The source beta tag and commit are recorded in the Actions
log. Draft retries refresh the stable release notes as well. Existing beta
releases stay available. Selecting an older beta is supported even when `main`
has advanced. Existing stable tags cannot be moved, and stable versions cannot
go backwards.

After promotion, new commits default to the next patch's beta cycle shown above.
The counter starts at one unless tags already exist for that cycle, in which
case it continues after the highest reserved beta number. An already-active
higher cycle continues instead, and labels on newly merged PRs may raise the
target. Existing legacy betas retain their core version and promote to matching
stable versions; deleting the old override does not send numbering backwards.
Promotion does not create a new commit or immediately publish a beta for the
unchanged `main` tip.

## Permissions, retries, and validation

Release workflow actions are pinned to full commit SHAs with readable version
comments. The grouped GitHub Actions Dependabot configuration proposes pin
updates for review; check upstream changes and action inputs before accepting
them, especially for actions that receive the release App private key/token.

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
   | Repository variable | `RELEASE_APP_CLIENT_ID` | GitHub App Client ID from the App settings, not the numeric App ID |
   | Repository secret | `RELEASE_APP_PRIVATE_KEY` | Complete downloaded PEM private key, including its headers |

Both workflows use the token action's `client-id` input. When migrating from
the former `RELEASE_APP_ID` setting, add `RELEASE_APP_CLIENT_ID` before merging
the workflow update. Keep the old variable until older workflows no longer need
it. The private key and installation permissions do not change.

The privileged publication phase generates a short-lived token scoped to this
repository and explicitly requests Contents and Workflows write access. All
release checkouts use read-only access with `persist-credentials: false`, and
Python setup completes before the App token is minted. `GH_TOKEN` authenticates
release API operations; tag pushes receive the same App token through a
process-local Git extraheader environment, without saving it in checkout config
or a remote URL. The action revokes the token at job completion.

The beta workflow separately uses the built-in `GITHUB_TOKEN` with Contents,
Issues, and Pull requests read access for planning and PR/label metadata. The
publisher supplies it as `GH_READ_TOKEN` for metadata reads. Candidate validation
has only Contents read permission and receives neither token in its processes.
The release App needs no additional permissions for labels. No bypass permission
for `main` is needed. Tag rules must allow these release tags. Normal publication
requires dispatch from `main`.

To verify App setup without publishing, manually run **Tag beta release** with
`verify_only` enabled. This mode may run from a topic branch before its workflow
changes are merged; it requests the actual Contents/Workflows write permissions
and checks GitHub API, label metadata, and Git repository access in a dedicated
job that does not check out or execute repository code. It skips planning,
candidate validation, and publication. Normal beta publication and stable
promotion still run only from `main`.

If token creation fails, check the Client ID/private key pair, repository
installation, and App permissions. After changing App permissions, approve the
installation's updated permissions in GitHub before retrying. A GitHub CLI
login's `workflow` scope does not change the workflow's built-in token.

Both publishers use the same concurrency group without cancelling running
publication. GitHub may replace a pending run with a newer one; reconciliation
on the next push or manual beta dispatch recovers missing commits. Each run
plans and publishes against the same immutable workflow snapshot for betas.
Commits arriving during a run are handled by a subsequent beta run.

Packages are attached to draft releases before publication. Rerunning a failed
workflow repairs unfinished drafts, preserving the assigned tag/version.
Published betas are skipped, and repeating the same completed promotion is a
no-op even though the latest stable version has advanced. An unfinished
promotion keeps its original target; retry with a beta of the original core
version rather than creating a second release for the same commit. Historical
unfinished promotions created with a different stable target must be recovered
before switching to matching-core promotion. Tags are never force-updated.
If a workflow times out on a large batch, rerun **Tag beta release**;
already-published commits are not tested again.

Validate release tooling locally without publishing:

```sh
python -m pytest .github/scripts/release.test.py .github/scripts/workflows.test.py -q
git diff --check
```

Do not run `python .github/scripts/release.py beta` or `promote` locally just to
test: these commands publish real tags/releases using the authenticated `gh`
CLI. Follow [development setup](DEVELOPMENT.md) for the test
environment. Use workflow logs and the built-in Marketplace on Home Assistant
2026.11 or newer to verify the first published ZIP can be installed and reports its
stamped version. Check that stable releases are offered by default and betas are
available after enabling the repository's **Pre-release** entity and turning on
its switch. See the [installation and update steps](../README.md#installation)
and the [Marketplace release guide](https://contributors.home-assistant.io/marketplace/guides/releases/)
for the packaging contract. Older releases have no ZIP asset; their existing
tags/assets are not rewritten by these workflows.
