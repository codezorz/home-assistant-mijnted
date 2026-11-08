---
applyTo: "**"
description: Branch, version, commit, PR, label, issue-link, and publishing policy.
---

# Git and GitHub workflow

This file owns Git/release policy. The [PR skill](../../.agents/skills/pr-workflow/SKILL.md)
provides the task workflow; [release operations](../../docs/RELEASING.md) owns
publisher setup, execution, and recovery. Publishing requires a user request.

## Branches and worktrees

- Target `main` from a descriptive topic branch: `fix/*`, `feature/*`,
  `enhancement/*`, `docs/*`, or `tooling/*`. Continue the same task's branch.
- Follow the [worktree workflow](../../.agents/skills/git-worktrees/SKILL.md).
  Ask about checkout choice before new editing work; preserve existing changes
  and use explicit working directories. Never force a branch into two worktrees.
- Fetch when a current remote base is needed. Do not assume local `main` is current
  or silently use a stale ref after a failed fetch.

## Versioning

- Keep the source manifest at `0.0.0-dev.0`. Release tags determine versions;
  publishers stamp the ZIP manifest. Do not commit version bumps.
- Each validated commit entering `main` receives a numbered beta, including
  documentation/tooling commits. Retained commits must be independently releasable.
- Integration-changing PRs carry exactly one explicit release label. Operational-only
  PRs have no release label and use their appropriate type label.

  | Impact | Release intent |
  |---|---|
  | Nonbreaking integration fix | `release:patch` |
  | Backward-compatible feature | Recommend `release:minor`; confirm with the user |
  | Breaking change | Discuss and confirm `release:major` with the user |

- Routine nonbreaking fixes need no version question. Confirm feature/breaking
  targets before creating/updating the PR, and record the decision in its body.
  Mixed changes follow their highest integration impact; file paths do not determine intent.
- Labels determine the version target, not beta versus stable publication. The
  publisher reconstructs intent at merge; open-PR labels and post-merge edits do
  not affect published intent. Check labels again when scope changes and before merge.
- Bump requests accumulate from the latest published stable, keeping the highest
  requested target. Repeated minor requests share a cycle; reserved targets never
  move backwards. Unlabelled/direct commits default to patch, but that fallback
  does not replace the explicit-label requirement for integration PRs.
- Promotion publishes a tested beta's exact core version when requested. Do not
  introduce version overrides in `.github/release-config.json`.

## Commits and pull requests

- One feature or independent root-cause fix is one logical commit, including its
  tests and documentation. Do not split by file/layer or retain review-only fixups.
  A PR can contain related independent fixes, one releasable commit each; explain
  their issue mapping and intended commit count before merge.
- Before committing, inspect status, the full diff, and `git log --oneline -10`.
  Stage only intended files and never credentials. Run change-appropriate checks.
- Write commit messages to a temporary file and use `git commit --file <file>`.
  Use a quoted Bash heredoc if a shell writes multiline text. Remove the file afterward.
- Before a PR, inspect remote tracking, every included commit, and the complete
  base-branch diff. Push the topic branch and target `main`.
- Use `gh`; write the PR body to a temporary file and use
  `gh pr create --body-file <file>`, then remove it. Include behavior, validation,
  release intent, and issue scope. Request applicable `CODEOWNERS` review and return the URL.
- Do not skip hooks or change Git configuration without permission. Fix a rejected
  commit's problem and retry the appropriate operation under the rules below.

### Review updates and history

- Fold corrections into the feature/fix's owning commit. Amend or consolidate its
  slice, preserving unrelated commits; add a commit only for an independent change.
- A maintainer request to fix/update an agent-managed open PR authorizes this
  consolidation and `--force-with-lease` on that task branch. Record the expected
  remote tip first and use an explicit lease. Investigate a failed lease instead
  of overwriting remote changes; never use an unguarded force push.
- Rewriting unrelated/shared branches requires explicit authorization. Never rewrite
  `main` as PR maintenance. Do not defer logical-history cleanup to merge-time squash.

## Labels and issue closure

- Query existing labels; do not invent them. Provision the defined release labels
  if setting up this scheme and they are missing. Keep labels on merged PRs;
  remove them when closing an unmerged PR.
- [Issue policy](issues.instructions.md) owns type labels, dispositions, completion,
  and beta feedback. Security severity follows [security triage](security-triage.instructions.md).

### Issue references versus closing keywords

- Use `Refs #123`, `Related to #123`, or `Part of #123` for partial work or context.
  State completed and remaining scope; do not narrow an issue silently to justify closure.
- Use `Fixes`, `Closes`, or `Resolves` only when merge fulfills the
  [whole issue's completion criteria](issues.instructions.md#completion-and-beta-feedback).
  Read the issue/discussion first; ask if scope is unclear.
- Closing keywords in PR bodies or commits, and manual Development links, can close
  the whole issue on merge to `main`. There is no partial-close syntax. A partial
  PR can close a fully completed sub-issue while referencing its parent.
- Before publishing/updating and before merge, inspect the PR body, included commit
  messages, final merge/squash message, and Development links. Check parsed links
  with `gh pr view <number> --json body,closingIssuesReferences`; inspect commit
  messages separately. Remove unintended closing links.
- For accidental closure, correct the link, reopen, and comment with the fixing PR,
  completed subset, and remaining work. Preserve the type label; a body edit alone
  does not reopen an issue.

## Post-merge local cleanup

- Verify merge with `gh`, then ask explicitly whether to remove the task worktree
  and local branch. Remote branch deletion needs separate permission.
- Follow the [worktree cleanup procedure](../../.agents/skills/git-worktrees/SKILL.md).
  Inspect dirty/untracked and unmerged work, preserve user changes, and keep the
  primary checkout/`main`. Use non-forced removal/deletion. If deletion is refused
  after a squash/rebase merge, investigate and ask before forcing it.

## Releases

Release only commits reachable from `main` using the existing workflows. Follow
[release operations](../../docs/RELEASING.md) for automatic betas, tested-beta
promotion, GitHub App permissions, validation isolation, and retry recovery.
