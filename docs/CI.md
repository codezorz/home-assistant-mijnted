# Continuous integration

[CI instructions](../.github/instructions/ci.instructions.md) own workflow-change
policy. This guide covers current jobs, branch settings, and troubleshooting.

## Validate code

**Validate code** runs on every PR to `main` and manual dispatch, without path
filters. It checks syntax and the full pytest suite on the latest stable Python 3
(`3.x`, `check-latest: true`), then runs native HA localization checks in a separate
locked Linux environment. [Development setup](DEVELOPMENT.md) owns local commands.

The test runner has read-only access and disables checkout credential persistence.
JUnit results are uploaded even after test failures. A fresh runner publishes
**Pytest Results** from the artifact without checking out PR code. Fork PRs retain
their test result/artifact; the write-permission reporting job does not run there.

## CodeQL scanning and fork approvals

The [CodeQL workflow](../.github/workflows/codeql.yml) analyzes Python and Actions
on PRs to `main`, pushes to `main`, a weekly schedule, and manual dispatch. It uses
the normal PR merge checkout, the built-in token, and no repository secrets.

Keep advanced setup enabled through this workflow and GitHub default setup disabled.
In the `main` ruleset, require **Validate code** and the **CodeQL** code-scanning
check. The matrix jobs **Analyze (actions)** and **Analyze (python)** upload their
language categories; both analyses and the separate CodeQL result must complete.

First-time-contributor runs can require approval. Approve the relevant run and
verify its commit; approval applies to that run, not permanently to the contributor.

For manual verification on `main`:

```sh
gh workflow run codeql.yml --repo codezorz/home-assistant-mijnted --ref main
```

## Troubleshooting

| Symptom | Check |
|---|---|
| CodeQL remains **Expected** | Inspect both language jobs and the code-scanning result; a skipped analysis does not supply the required check. |
| Fork workflow awaits approval | Approve the run for the current PR commit. |
| A workflow correction needs verification | Start a run/event using the corrected revision; a rerun uses the workflow revision attached to that run. |
| Tests fail | Reproduce with the [change-appropriate checks](DEVELOPMENT.md#checks-appropriate-to-the-change); native checks need their separate environment. |

Beta publication validates commits entering `main` through the isolated process
described in [release operations](RELEASING.md).
