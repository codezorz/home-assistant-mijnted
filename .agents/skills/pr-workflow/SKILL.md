---
name: pr-workflow
description: Use when preparing branches, commits, and pull requests in this repo, including version decisions and post-merge cleanup.
---

# PR workflow

Read and follow `.github/instructions/git-workflow.instructions.md` before
branching, deciding versions, committing, or publishing. That file owns the
policy; this skill does not authorize publishing without a user request.

1. Inspect the checkout, base branch, and complete task diff.
2. Classify integration impact using the policy's **Versioning** rules. Apply
   exactly one explicit release label for integration changes, including
   `release:patch` for routine nonbreaking fixes; leave operational-only PRs
   unlabelled for release intent. Confirm feature/breaking targets as the policy
   requires and record the decision in the PR body. Recheck labels before merge
   and when scope changes. Labels take effect on merge and bump requests
   accumulate since stable rather than stacking; they do not select beta versus
   stable publication.
3. Follow [development instructions](../../../.github/instructions/development.instructions.md)
   for checks appropriate to the changes.
4. When publishing is requested, follow the policy's commit-message/PR-body
   file conventions, review ownership, and labeling rules. Apply its
   [review-update and history rules](../../../.github/instructions/git-workflow.instructions.md#review-updates-and-history)
   when incorporating corrections into an existing PR.
   Follow [issue policy](../../../.github/instructions/issues.instructions.md)
   for completion and beta feedback, and the Git policy's **Issue references
   versus closing keywords** section for PR links and the pre-merge closure check.
5. Report validation, version decisions, and the PR URL when created.
6. After confirming through GitHub that the PR has merged, ask whether to remove
   its task worktree and local topic branch. Follow the policy's post-merge
   cleanup rules and `.agents/skills/git-worktrees/SKILL.md` after confirmation.
