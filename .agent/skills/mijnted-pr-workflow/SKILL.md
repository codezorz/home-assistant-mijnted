---
name: mijnted-pr-workflow
description: Use when preparing branches, commits, and pull requests in this repo, including version bump decisions and repository git workflow rules.
---

# Mijnted PR Workflow

Use this skill for branch/commit/PR tasks in this repository.

## What this skill covers

- Branching and PR flow for `main`
- Version bump decision rules
- Commit and PR body file workflow
- Safe command behavior in this repo

## Workflow

1. Start from `main` and create a topic branch (`fix/*`, `feature/*`, `enhancement/*`, `docs/*`).
2. Decide whether a version bump is required in `custom_components/mijnted/manifest.json`:
   - Bump only for integration runtime or user-facing changes in `custom_components/mijnted/**`.
   - Do not bump for `.github/**`, docs, or tooling-only changes.
   - Compare `manifest.json` version with the latest GitHub release version.
   - If equal: add a version bump commit first (semantic versioning).
   - If already higher than latest release: do not bump again.
3. Keep commits logically split and descriptive.
4. Push branch and open PR targeting `main`.
5. Include a clear PR summary and note version bump behavior when relevant.
6. Apply/update labels on PR and linked issue(s) according to repo label policy.
7. When closing an issue, apply fixed-or-closure-reason labels and add a traceable closing comment.

## Required command conventions

- Run all `git` commands outside sandboxed mode.
- For commit messages:
  - Write message to a temporary file.
  - Use `git commit --file <file>`.
  - Delete the temp file.
- For PR bodies:
  - Write body to a temporary file.
  - Use `gh pr create --body-file <file>`.
  - Delete the temp file.

## Mandatory checklist

- PR has appropriate labels before/after creation.
- Linked issue(s) have appropriate labels.
- Closed issue(s) fixed by PR/commit keep type label (`bug`, `enhancement`, `question`); otherwise include closure-reason label (`duplicate`, `invalid`, `wontfix`).
- Closed issue comment references fixing PR/commit (or explicit non-fix reason).

## References

- `AGENTS.md`
- `.github/instructions/repo.instructions.md`
