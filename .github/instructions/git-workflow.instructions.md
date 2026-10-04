---
applyTo: "**"
description: Branches, version decisions, requested commits/PRs, labels, review ownership, and releases.
---

# Git and GitHub workflow

This is the authoritative repository policy for branches, versions, commits,
pull requests, labels, and releases. Apply publishing steps only when requested.

## Branches and worktrees

- The default branch and PR target are `main`. Work on a descriptive topic
  branch (`fix/*`, `feature/*`, `enhancement/*`, `docs/*`, or `tooling/*`).
- For new editing tasks, prefer an isolated task worktree. Ask the user whether
  to create or reuse one before starting, unless they already explicitly asked
  for a worktree. If they prefer the current checkout, honor that choice while
  preserving existing work and using a topic branch.
- Continue an existing branch for the same task. Do not split an ongoing task
  into an unrelated branch.
- For a new task, start from the requested base or the default branch. Fetch
  when an up-to-date remote base is needed; do not assume local `main` is current.
- Follow `.agents/skills/git-worktrees/SKILL.md` for checkout placement/naming.
  Never overwrite another checkout's uncommitted work or force a branch into
  multiple worktrees.

## Versioning

- Keep the source manifest at `0.0.0-dev.0`; do not commit release-version bumps.
  Tags and published GitHub releases determine versions. Workflows stamp the
  exact tag version, without `v`, into the release ZIP's manifest.
- Every newly reachable commit on `main` after the configured bootstrap commit
  receives a numbered beta after its syntax check and tests pass. This includes
  documentation and tooling changes, plus intermediate commits in multi-commit
  pushes and merged branches. Prefer squash merges if intermediate commits
  are not independently releasable.
- By default, betas target the patch after the latest published stable release.
  Stable promotion exposes a `version_bump` choice: patch (default), minor,
  or major, calculated from the latest published stable version. To set a
  higher beta cycle before promotion, optionally set `next_version` in
  `.github/release-config.json` to a higher minor or major core version. An active
  beta cycle cannot move backwards; an override is consumed once released.
- Keep each PR focused on its task. Note an explicit target-version decision
  in the PR description when applicable.

## Commits and pull requests

- Prefer a single commit per PR, including follow-up adjustments during review.
  If separate commits would improve review or isolate independent concerns,
  ask the user before using multiple commits unless they already requested them.
  Combining already-pushed commits still requires explicit permission for any
  history rewrite and force-push; use `--force-with-lease` when authorized.
- Before committing, inspect status, diff, and `git log --oneline -10`.
  Stage only intended files; never stage credentials or unrelated work.
- Write the commit message to a temporary file and use `git commit --file <file>`.
  Remove the temporary file afterward. Use a quoted Bash heredoc when writing
  multiline messages so shell variables and backticks remain literal.
- Before creating a PR, inspect remote tracking, every included commit, and
  the diff against the base branch. Push the topic branch and target `main`.
- Write the PR body to a temporary file and use `gh pr create --body-file <file>`;
  remove the file afterward. Summarize behavior, validation, and version decisions.
- Use `gh` for GitHub operations. Request review from the applicable owners in
  `CODEOWNERS`, and return the PR URL.
- Do not amend, force-push, skip hooks, or change Git configuration unless
  explicitly requested. If a commit hook fails, fix the problem and retry
  with a new commit attempt.

## Labels and issue closure

- Query the repository's existing labels; do not invent labels. Apply suitable
  labels when creating/updating PRs and when triaging/closing issues.
- Keep labels on merged PRs. Remove labels when closing an unmerged PR or
  cleaning up previously closed, unmerged PRs.
- For a fixed issue, keep the type label (`bug`, `enhancement`, or `question`)
  and add a closing comment referencing the fixing PR/commit.
- For an issue closed without a fix, apply the appropriate existing closure
  label (`duplicate`, `invalid`, or `wontfix`) and explain the reason in a comment.

## Post-merge local cleanup

- When the agent observes or performs a PR merge, verify its merged state with
  `gh` and ask whether to remove the task worktree and local topic branch.
  Offer both explicitly; wait for confirmation before removing either.
- Follow `.agents/skills/git-worktrees/SKILL.md`: inspect registered worktrees,
  dirty/untracked files, and remaining unmerged work. Ask how to preserve any
  work found before proceeding. Keep the primary checkout and `main`.
- From another checkout, remove the confirmed task checkout with
  `git worktree remove <path>`, then delete the confirmed local branch with
  `git branch -d <branch>`. Do not force removal or branch deletion. If Git
  refuses deletion after a squash/rebase merge, investigate the remaining work
  and ask before using a force-delete operation.
- Verify and report the remaining worktree/branch state. Remote branch deletion
  requires a separate request; local cleanup does not imply it.

## Releases

Releases are tags on commits reachable from `main`, not release branches.
The **Tag beta release** workflow reconciles pending commits on pushes and manual
dispatch. It creates `vX.Y.Z-beta.N` tags, prereleases, and
`mijnted.zip` assets. Do not publish unmerged topic-branch commits.

For stable publication, run **Promote release** from `main`. Supply an
existing beta tag or leave it empty to select the published beta at the current
`main` tip. If that beta is not available yet, wait for or rerun the beta workflow.
Choose `version_bump`: patch (default), minor, or major. Promotion calculates
`vX.Y.Z` from the latest stable release, tags the selected beta's exact commit,
and changes only the manifest version in its package. It does not rebuild
application code. It cannot lower the beta's core version or release an older
beta cycle again. Completed promotions are no-ops on retry; unfinished ones
must retain their original target and bump selection.
Stable release notes are generated between the previous published stable tag
and the promoted commit, with a stable-to-stable changelog link. Keep beta
provenance and bump details in the Actions log rather than the public notes.
The next beta defaults to `vX.Y.(Z+1)-beta.1`, unless a higher cycle is active.

Both publishers share a concurrency lock, recover unfinished draft releases,
and use a short-lived GitHub App installation token with Contents and Workflows
write access, scoped to this repository. Both Git checkout/tag pushes and `gh`
release operations must use that token. `GITHUB_TOKEN` cannot obtain Workflows
write access needed for historical workflow-changing commits. Configure
`RELEASE_APP_ID` as a repository variable and `RELEASE_APP_PRIVATE_KEY` as a
repository secret. No branch bypass or manifest push is needed. See
`doc/DEVELOPMENT.md` for setup, operation, and recovery details.
