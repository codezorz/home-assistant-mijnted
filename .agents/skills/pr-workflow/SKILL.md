---
name: pr-workflow
description: Use when preparing branches, commits, and pull requests in this repo, including version decisions and post-merge cleanup.
---

# PR workflow

Read and follow `.github/instructions/git-workflow.instructions.md` before
branching, deciding versions, committing, or publishing. That file owns the
policy; this skill does not authorize publishing without a user request.

1. Inspect the checkout, base branch, and complete task diff.
2. Decide release impact from integration behavior:
   - Operational-only work (CI, release automation, agent tooling, docs) and
     routine nonbreaking bug fixes: normal betas, no release label or question.
   - New integration features: ask for **patch**, **minor**, **major**, or
     **normal betas / no label**, unless the user already chose. Recommend
     minor for backward-compatible features.
   - Breaking integration behavior, even a bug fix: ask about major.
   Apply at most one user-selected `release:*` label and record the decision
   in the PR body. No label is already the normal default; do not suggest a
   patch label just to continue betas. Labels take effect on merge and bump
   requests accumulate since stable rather than stacking.
3. Follow `doc/DEVELOPMENT.md` for checks appropriate to the changes.
4. When publishing is requested, follow the policy's commit-message/PR-body
   file conventions, review ownership, and labeling rules. Prefer one commit
   per PR; ask before splitting into multiple commits unless already requested.
   Follow the policy's permission requirements when rewriting pushed history.
5. Report validation, version decisions, and the PR URL when created.
6. After confirming through GitHub that the PR has merged, ask whether to remove
   its task worktree and local topic branch. Follow the policy's post-merge
   cleanup rules and `.agents/skills/git-worktrees/SKILL.md` after confirmation.
