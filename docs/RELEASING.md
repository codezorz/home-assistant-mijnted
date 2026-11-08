# Release operations

[Git/PR policy](../.github/instructions/git-workflow.instructions.md) owns version
decisions, labels, logical commits, and publishing permission. This guide covers
the current publishers. Run publication only when requested.

## Automatic betas

**Tag beta release** runs on pushes to `main` and manual dispatch. Candidates are
unpublished commits reachable after `start_commit` in
[release-config.json](../.github/release-config.json), processed in dependency order.
Keep that anchor stable. Each retained commit is a candidate, including branch
and merge commits; prepare history under the
[logical-commit policy](../.github/instructions/git-workflow.instructions.md#commits-and-pull-requests).

The workflow separates three trust boundaries:

| Job | Responsibility |
|---|---|
| Read-only planning | Freeze the workflow/main snapshot and candidate list. |
| Candidate validation | Check out each exact candidate in a temporary Git clone, install its dependencies, and run syntax/tests. Subprocesses receive no workflow tokens or inherited Git authentication. |
| Trusted publication | After the whole batch passes, mint the release App token and package tracked integration files without executing candidate code. Reject candidates outside the validated plan. |

New commits wait for a subsequent run. A failing candidate blocks that run's
batch; every retained commit must pass independently.

Tags have the form `vX.Y.Z-beta.N`. Each published beta has a flat `mijnted.zip`
containing integration files at its root and a matching manifest version without
the `v` prefix. The source manifest stays `0.0.0-dev.0`.

## Merge-time release intent

Choose labels under [version policy](../.github/instructions/git-workflow.instructions.md#versioning).
The publisher reads PR merge events and their labels at merge time. A squash is
one candidate; other merge strategies retain their newly reachable commit candidates.
Direct/intermediate commits use the patch fallback.

The highest requested bump since the latest stable defines the target cycle.
Repeated requests at that level advance its beta counter. Reserved versions do
not move backwards or change on retry. Open PRs do not reserve targets.
Conflicting labels or unavailable merge metadata stop publication; resolve the
problem and retry rather than guessing a version.

## Promoting to stable

1. Open **Actions → Promote release → Run workflow** on `main`.
2. Supply a published beta tag, or leave it empty for the beta at the current
   `main` commit. If that beta is not published, finish/retry the beta workflow first.
3. Run promotion for the beta that has been tested.

Promotion removes `-beta.N` and publishes the **same core version**, with no bump
selection. The beta commit must descend from and be newer than the latest stable,
and its core version must exceed that stable. A selected beta need not be the
current `main` tip. Tags cannot be moved or overwrite a stable release.

The publisher downloads the beta ZIP, changes only its manifest version, and tags
the same source commit. GitHub generates fresh stable-to-stable release notes and
a changelog link. Beta provenance is recorded in the Actions log; beta releases
remain available.

Completed promotions are no-ops. An unfinished promotion keeps its reserved target.
After stable publication, new commits default to the next patch cycle unless an
already-reserved higher cycle or merged release intent requires a higher target.
Promotion creates no source commit or immediate beta for an unchanged `main` tip.

## Permissions, retries, and validation

### GitHub App setup

Both publishers create tags/releases using a repository-scoped GitHub App
installation token. Grant **Contents: Read and write** and **Workflows: Read and
write**; the built-in `GITHUB_TOKEN` does not provide Workflows write access.
Install the App on this repository and generate its private key.

Configure repository Actions settings:

| Kind | Name | Value |
|---|---|---|
| Variable | `RELEASE_APP_CLIENT_ID` | GitHub App Client ID |
| Secret | `RELEASE_APP_PRIVATE_KEY` | Complete PEM private key |

The publication phase requests those write permissions only for this repository.
Checkouts use read-only access with `persist-credentials: false`; Python setup
finishes before token creation. `GH_TOKEN` authenticates release APIs, and Git tag
pushes use the same token through a process-local extraheader. No token is stored
in checkout configuration or remote URLs; the action revokes it at completion.

Beta metadata reads use the built-in token via `GH_READ_TOKEN`, with Contents,
Issues, and Pull requests read access. Candidate validation has Contents read
access and receives neither token in its subprocesses. No `main` bypass is needed;
tag rules must permit release tags. Publishing dispatches run from `main`.

### Verify and recover

- Run **Tag beta release** with `verify_only` to check App/API/label/Git access
  without planning, candidate execution, or publishing. This verification job can
  run from a topic branch and does not check out repository code.
- For token failure, check Client ID/key pairing, installation access, and approved
  App permissions. CLI login scopes do not change workflow-token permissions.
- Both publishers share a non-cancelling concurrency group. A subsequent push or
  manual beta run reconciles pending commits if GitHub replaces a queued run.
- Assets are attached to drafts before publication. Retry unfinished drafts using
  their reserved versions; published candidates are skipped. Recover an unfinished
  promotion at its reserved core version. Never force-update tags.
- After a batch timeout, rerun the workflow; published candidates are not revalidated.
- Actions are SHA-pinned; review Dependabot updates, especially token-action inputs.

Validate tooling without publishing:

```sh
python -m pytest .github/scripts/release.test.py .github/scripts/workflows.test.py -q
git diff --check
```

`release.py beta` and `promote` publish real tags/releases through authenticated
`gh`; they are not local test commands. Use [development setup](DEVELOPMENT.md).
Verify installation/stamped version through Marketplace using the
[installation guide](../README.md#installation) and
[Marketplace packaging contract](https://contributors.home-assistant.io/marketplace/guides/releases/).
