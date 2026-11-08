---
applyTo: ".github/workflows/**,.github/dependabot.yml,.github/scripts/**,.github/instructions/ci.instructions.md,docs/CI.md"
description: Required CI checks, CodeQL event and permission constraints, and fork approval rules.
---

# CI rules

- Follow [the CI guide](../../docs/CI.md) for workflow operation, branch-rule
  setup, fork approvals, and troubleshooting.
- Keep **Validate code** running for every PR to `main`, without path filters,
  and keep it required alongside the **CodeQL** code-scanning check.
- Run **HA-native reporting** on every PR with its supported Python profile and
  locked dependencies. Its runner has read-only access and synthetic API data.
  JUnit publication stays on the separate artifact-only reporting runner.
- Do not require **Aikido Security: check code** on the free Developer plan;
  paid PR gating is outside the [Aikido setup](aikido-triage.instructions.md).
- Use the latest stable Python 3 (`3.x` with `check-latest: true`) for the fast
  suite. The native HA job uses the Python range declared by `tests_native/`.
- Keep advanced CodeQL scanning on normal `pull_request` merge checkouts with
  the built-in token and no repository secrets. Default CodeQL setup must remain
  disabled while the advanced workflow uploads results.
- Run CodeQL directly on its configured events without a repository-variable gate.
- Preserve first-time-contributor workflow approvals. Approval permits one
  workflow run; it does not grant permanent contributor approval.
- Lint changed workflows with `actionlint` and run change-appropriate checks from
  [development guidance](../../docs/DEVELOPMENT.md#checks-appropriate-to-the-change).
