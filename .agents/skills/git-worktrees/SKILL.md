---
name: git-worktrees
description: Use when creating, locating, or cleaning up Git worktrees. Defines repository-relative placement and descriptive task-based names for isolated checkouts.
---

# Git worktrees

## Placement and naming

- Resolve the primary checkout with `git worktree list --porcelain`; do not
  derive the container from a task worktree's directory name. Ask if the
  primary checkout cannot be identified confidently.
- Relative to the **primary repository root**, use
  `../<repo-name>-worktrees/<type>-<task>`.
- `<repo-name>` is the primary checkout directory's name. `<type>` follows
  the repository's branch conventions (for example `fix`, `feature`,
  `docs`, `tooling`, or `review`). `<task>` describes the actual work.
- Use lowercase hyphen-separated names. Map branch `fix/month-switch` to
  checkout `fix-month-switch`, or `review/pr-54` to `review-pr-54`.
- Avoid generic names such as `<repo-name>-worktree`, `worktree`, `temp`,
  or `agent-1`. Each checkout should identify its task without opening it.
- Keep checkouts outside the repository; this layout needs no ignore rule.
  Keep shared skills tracked under `.agents/skills/` (plural).

```text
../
  <repo-name>/
  <repo-name>-worktrees/
    fix-month-switch/
    tooling-agent-skills-layout/
```

## Workflow

1. Read repository instructions. Inspect `git status --short --branch`,
   `git worktree list --porcelain`, and branch refs before creating anything.
2. Prefer an isolated task checkout for new editing work. Ask whether to create
   or reuse a worktree before starting, unless the user already requested one.
   Honor a preference for the current checkout; follow the Git policy.
3. Choose the requested base or the repository's default branch. Fetch if
   a current remote base is required; report a failed fetch before using
   a stale ref. Validate new branches with `git check-ref-format --branch`.
4. Verify the container's parent exists, create the container if needed,
    and verify the destination is unused. Respect external-directory access
    and use Bash with quoted, forward-slash paths. Reject path separators and
    `..` in task slugs.
5. From the primary repo root, create a new task branch:
   `git worktree add -b <type>/<task> "../<repo-name>-worktrees/<type>-<task>" <base-ref>`.
   For an existing branch, omit `-b`. If already checked out, use its
   registered worktree instead of forcing another checkout.
6. Verify status in the new checkout and report its path, branch, and base.
   Run subsequent tools explicitly in that checkout and read its instructions.
   Creating a worktree does not relocate the running agent session.

Uncommitted changes remain in their original checkout. Do not automatically
stash, reset, copy secrets or environments, commit, push, or open a PR.

For requested cleanup, inspect dirty/untracked files and unmerged work first;
ask how to preserve any work found. Use `git worktree remove` from another
checkout, without `--force`. Delete branches only when requested separately.
Use `git worktree move` to rename registered checkouts; inspect
`git worktree prune --dry-run` before pruning stale metadata.
