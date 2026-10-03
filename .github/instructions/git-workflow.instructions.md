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
- Continue an existing branch for the same task, especially when it already
  contains an unreleased version bump. Do not create a second bump or split
  an ongoing task into an unrelated branch.
- For a new task, start from the requested base or the default branch. Fetch
  when an up-to-date remote base is needed; do not assume local `main` is current.
- Follow `.agents/skills/git-worktrees/SKILL.md` for checkout placement/naming.
  Never overwrite another checkout's uncommitted work or force a branch into
  multiple worktrees.

## Version bumps

- Only runtime or user-facing integration changes in `custom_components/mijnted/**`
  require considering a bump to `manifest.json`. Docs, agent configuration,
  workflows, and tooling-only changes do not.
- Compare the manifest version with the latest published GitHub release using
  `gh release view`. If the manifest equals that version, make a bump commit
  first: patch for fixes, minor for features, major for breaking changes.
- If the manifest is already higher, keep that unreleased version. If it is
  lower or the release cannot be determined, investigate before choosing a version.
- Keep implementation commits logically split by concern. Note the version
  decision in the PR description.

## Commits and pull requests

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

## Releases

Releases are tags on `main` after the PR is merged, not release branches.
When release publication is requested, tag the merged commit (for example
`v<manifest-version>`) and publish its GitHub release. Do not release an
unmerged topic-branch commit.
