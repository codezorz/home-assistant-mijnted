---
applyTo: "**"
description: Issue creation, triage, implementation completion, and beta-testing follow-up.
---

# Issues

This file owns issue policy. [Git/PR instructions](git-workflow.instructions.md)
own PR closing keywords and GitHub link mechanics; [release operations](../../docs/RELEASING.md)
explain beta publication and promotion.

## Creating and triaging issues

- Follow [issue reporting](../../docs/ISSUE_REPORTING.md) for report contents,
  pre-submission checks, and issue forms. Security findings follow the
  [security triage policy](security-triage.instructions.md), including disclosure,
  root-cause grouping, source dispositions, and reopening existing tracking.
- Define the expected code or documentation outcome and relevant pre-merge
  checks for implementation issues. Do not add deployment, live-HA access,
  reporter confirmation, or stable promotion as completion criteria for an
  otherwise complete implementation.
- Follow the [label policy](git-workflow.instructions.md#labels-and-issue-closure).
  Use `bug` for confirmed faulty behavior and the appropriate existing type for
  other work. For a fixed issue, retain its type label and add a closing comment
  linking the fixing PR/commit. For closure without a fix, explain the disposition
  and use the appropriate existing `duplicate`, `invalid`, or `wontfix` label.

## Completion and beta feedback

- A complete fix with required pre-merge checks closes its issue when the PR
  merges into `main`. Use the [PR issue-link rules](git-workflow.instructions.md#issue-references-versus-closing-keywords)
  to distinguish full fixes from partial implementations.
- Report checks performed and runtime verification not performed honestly.
  Failed syntax checks, behavioral assertions, and required CI remain blocking;
  lack of a deployed HA environment alone does not keep a completed issue open
  or make a full fix partial work.
- The existing release automation validates and publishes beta candidates from
  `main` for testing. Issue closure does not wait for beta deployment or feedback.
- Beta findings become new, linked follow-up issues with the tested beta,
  environment, and reproduction details. Apply the triage rules above and link
  the original issue and fixing PR.
  Security findings use their [source-verification and follow-up rules](security-triage.instructions.md#pr-closure-and-post-merge-follow-up).
- Once beta testing is satisfactory, promote the tested beta when the maintainer
  requests it under [release operations](../../docs/RELEASING.md#promoting-to-stable).
  Implementation completion, beta feedback, and stable promotion are distinct.
