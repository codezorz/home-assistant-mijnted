---
name: pr-workflow
description: Use when preparing branches, commits, and pull requests in this repo, including version decisions and post-merge cleanup.
---

# PR workflow

Read and follow `.github/instructions/git-workflow.instructions.md` before
branching, deciding versions, committing, or publishing. That file owns the
policy; this skill does not authorize publishing without a user request.

1. Inspect the checkout, base branch, and complete task diff.
2. Classify release intent and obtain the confirmations required by
   [Versioning policy](../../../.github/instructions/git-workflow.instructions.md#versioning).
   Record the decision and apply the prescribed labels.
3. Follow [development instructions](../../../.github/instructions/development.instructions.md)
   for checks appropriate to the changes.
4. When publishing is requested, follow commit/body-file conventions and review
   ownership. Verify issue scope using [closing-link policy](../../../.github/instructions/git-workflow.instructions.md#issue-references-versus-closing-keywords).
   Fold corrections under [review-update policy](../../../.github/instructions/git-workflow.instructions.md#review-updates-and-history).
5. Report validation, version decisions, and the PR URL when created.
6. On merge, follow [post-merge cleanup policy](../../../.github/instructions/git-workflow.instructions.md#post-merge-local-cleanup)
   and the [worktree workflow](../git-worktrees/SKILL.md).
