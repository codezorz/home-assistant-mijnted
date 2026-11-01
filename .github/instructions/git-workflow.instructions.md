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
- PR release labels determine beta targets: `release:patch`, `release:minor`,
  or `release:major`. They select version intent, not beta versus stable
  publication. Unlabelled PRs and direct pushes still default to patch in the
  publisher; this fallback does not replace explicit labeling of integration
  changes. The publisher reconstructs labels at the main merge event, ignoring
  later label edits. Open PRs do not influence versions.
- Accumulate the highest requested bump since the latest published stable,
  rather than incrementing the current beta core for each PR. Repeated minor
  requests continue the same minor cycle. An already-reserved higher beta cycle
  cannot move backwards, including legacy cycles. Promotion publishes that
  beta's exact core version; it has no bump selection. Do not add version
  overrides to `.github/release-config.json`.
- Apply exactly one explicit release label to PRs that change integration
  behavior. Leave release labels off operational-only PRs. Classify by behavior
  and compatibility, not file paths or diff size; mixed PRs follow their highest
  integration impact.

  | PR impact | Release-label guidance |
  |---|---|
  | Documentation, instructions, CI, release automation, or developer tooling only | No release label; use an appropriate existing type label |
  | Nonbreaking integration fix | `release:patch` |
  | Backward-compatible integration feature | Recommend `release:minor`; confirm the feature's release target with the user |
  | Breaking integration change, even a bug fix | Discuss and confirm `release:major` with the user |

- Routine nonbreaking integration fixes receive `release:patch` without a bump
  question. For new features or breaking behavior, confirm the release target
  before creating/updating the PR unless the user already chose. Use an explicit
  label for the agreed target; leaving it unlabelled is not an integration-change
  release decision.
- Record the release decision in the PR body, including why an operational-only
  PR has no release label. Generic type labels such as `documentation`,
  `enhancement`, and `bug` do not determine release versions. Documentation and
  tooling commits still receive normal betas; omitting a label does not skip
  publication. An explicit patch label records reviewed integration intent but
  does not lower or restart an active minor/major beta cycle.
- Keep each PR focused on a feature or coherent set of related fixes. Note an
  explicit target-version decision in the PR description when applicable.

## Commits and pull requests

- Organize commits as logical, independently reviewable slices: one feature is
  one commit; each independent issue/root-cause fix is one commit, including its
  necessary tests and documentation. Do not split one feature into commits by
  file, implementation layer, or tests versus code.
- A PR may contain multiple related fixes, with one commit per independent
  issue/root cause. Multiple commits following this rule do not require a
  separate approval. Explain the commit-to-issue mapping in the PR body and
  identify which issues are fully fixed versus only referenced.
- Each retained commit must pass its appropriate checks and be independently
  releasable: the beta publisher validates every commit reaching `main`.
  Preserve logical slices when merging a multi-fix PR; use squash merges to
  consolidate unfinished review history for a single feature/fix. Review
  adjustments belong with their logical slice, subject to the history-editing
  permissions below.
- Combining already-pushed commits still requires explicit permission for any
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
- The release-label scheme above is part of repository automation. If its
  labels are missing, create those defined labels when setting up that scheme.
  Before merging, verify exactly one release label for integration-changing PRs
  and none for operational-only PRs. Recheck the classification and label when
  the PR's scope changes; conflicting release labels stop publication.
- Keep labels on merged PRs. Remove labels when closing an unmerged PR or
  cleaning up previously closed, unmerged PRs.
- For a fixed issue, keep the type label (`bug`, `enhancement`, or `question`)
  and add a closing comment referencing the fixing PR/commit.
- For an issue closed without a fix, apply the appropriate existing closure
  label (`duplicate`, `invalid`, or `wontfix`) and explain the reason in a comment.

### Issue references versus closing keywords

- Use `Refs #123`, `Related to #123`, or `Part of #123` for context,
  investigations, interim work, and partial implementations. State what the PR
  completes and what remains; leave the broader issue open.
- Use `Fixes #123`, `Closes #123`, or `Resolves #123` only when merging the PR
  completes the issue's entire agreed scope. Read the issue and its relevant
  discussion first. If completion is unclear, use a reference and ask about
  closure; do not infer completion from a related feature or a passing test suite.
- For security remediation, a PR that completes the remediation scope and required
  pre-merge checks should close the issue on merge. Post-merge scanner verification
  is follow-up triage; reopen the existing issue if a fresh check confirms an
  unresolved finding with the same root cause. Follow the
  [security follow-up policy](security-triage.instructions.md#pr-closure-and-post-merge-follow-up).
- GitHub closes the whole issue when a closing PR merges into the default branch
  (`main`). There is no partial-close syntax: `Closes #123 (partially)` still
  closes #123. A later sentence saying that work remains does not prevent closure.
- Closing keywords also work in commit messages when the commit reaches `main`.
  Manually linking an issue through the **Development** sidebar can also close it
  on merge. Use plain references for partial work rather than these closing links.
- A partial PR may close a separate, fully completed sub-issue while referencing
  its parent. Do not silently narrow the parent issue or move its remaining scope
  to follow-ups just to justify closing it.
- Before creating/updating a PR and before merging any PR (including contributor
  PRs), review its body, included commit messages, final merge/squash message, and
  Development links for unintended closures. Inspect GitHub's parsed PR-body and
  manual closing links with
  `gh pr view <number> --json body,closingIssuesReferences`; inspect commit messages
  separately because commit-based closures need not appear in that list. Confirm
  each intended closure against the issue's scope and replace partial-work
  closing keywords/links with references before merging.
- If a partial PR already closed an issue accidentally, correct the PR body/link,
  reopen the issue, and comment with the merged PR, completed subset, and remaining
  scope. Editing a merged PR body alone does not reopen the issue. Preserve its
  type label; accidental closure is not a `duplicate`, `invalid`, or `wontfix`.

See [GitHub's linking documentation](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue)
for supported keywords and auto-closing behavior.

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
Promotion removes the beta suffix to produce `vX.Y.Z`, tags the selected beta's
exact commit, and changes only the manifest version in its package. It does not
rebuild application code. The source commit must be newer than and descend from the
latest stable commit, and its core version must exceed the latest stable.
Completed promotions are no-ops on retry; unfinished ones
must retain their original beta core version.
Stable release notes are generated between the previous published stable tag
and the promoted commit, with a stable-to-stable changelog link. Keep beta
provenance in the Actions log rather than the public notes.
The next beta defaults to `vX.Y.(Z+1)-beta.1`, continuing the counter if tags
already exist for that cycle. New merged PR labels may raise that target;
an already-active higher cycle remains active.

Both publishers share a concurrency lock, recover unfinished draft releases,
and use a short-lived GitHub App installation token with Contents and Workflows
write access, scoped to this repository. Both Git checkout/tag pushes and `gh`
release operations must use that token. `GITHUB_TOKEN` cannot obtain Workflows
write access needed for historical workflow-changing commits. Configure
`RELEASE_APP_CLIENT_ID` as a repository variable and `RELEASE_APP_PRIVATE_KEY` as a
repository secret. The beta workflow uses a separate read-only `GITHUB_TOKEN`
with Issues and Pull requests read permissions for merge-time label history.
No additional release App permissions, branch bypass, or manifest push is needed.
See [release operations](../../docs/RELEASING.md) for setup, operation, and recovery
details, and [development instructions](development.instructions.md) for checks.
