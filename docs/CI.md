# Continuous integration

This guide explains workflow operation and troubleshooting.
[CI instructions](../.github/instructions/ci.instructions.md) own development
constraints for workflow changes.

## Validate code

CI runs syntax checks and pytest on the latest available stable Python 3
(`3.x` with `check-latest: true`) on PRs to `main` and manual dispatch,
publishing a JUnit report when permitted. Commits entering `main` are validated
by the beta publication workflow. The selected Python version can advance to a
new minor version without a workflow edit.

The workflow and its job are named **Validate code**. Every PR targeting `main`
runs this job without path filters. After the check has appeared on a PR,
select **Validate code** in the branch rules' required status checks to require
syntax checking and the complete integration/release-tooling test suite.

The test job has read-only repository access and disables checkout credential
persistence. It uploads JUnit results even when tests fail. A separate fresh
runner publishes **Pytest Results** with `checks: write` using only the uploaded
report and a pinned reporter action; it does not check out or execute PR code.
This reporting job is skipped for fork PRs, whose tokens remain read-only;
their **Validate code** result and downloadable test artifact remain available.

Follow [the development guide](DEVELOPMENT.md) to reproduce checks locally and
[testing instructions](../.github/instructions/testing.instructions.md) for test design.

## CodeQL scanning and fork approvals

The [advanced CodeQL workflow](../.github/workflows/codeql.yml) analyzes Python
and GitHub Actions using the default query suites. It runs on PRs targeting
`main` (including fork PRs), pushes to `main`, a weekly schedule, and manual
dispatch. It scans the normal PR merge checkout using `pull_request`, with the
built-in token and no repository secrets. GitHub supports uploading CodeQL
results from this event for public fork PRs despite the read-only fork token.
The existing first-time-contributor workflow approval policy still applies.
Approval permits a workflow run; it is not permanent contributor approval.
Updating or rebasing an external contributor's PR can require approval for the
new run while they remain a first-time contributor.

GitHub's [default CodeQL setup](https://docs.github.com/en/code-security/concepts/code-scanning/setup-types#about-default-setup)
excludes fork PRs. Requiring its **CodeQL** check therefore leaves those PRs
waiting even after **Validate code** passes. Advanced setup supplies the missing
scan; rerunning the test workflow does not start a CodeQL analysis.

Default setup must remain disabled while the repository workflow performs
advanced uploads. The workflow runs directly on its configured events, without
an activation variable. The temporary `CODEQL_ADVANCED_ENABLED` migration
variable is obsolete and can be removed from repository Actions settings.
Its guard evaluated false on fork PR #70 even when the base repository's value
was `true`, skipping analysis after workflow approval. Do not reintroduce a
repository-variable gate for these scans.

For a baseline or manual verification, run **Actions → CodeQL → Run workflow**
on `main`, or use:

```sh
gh workflow run codeql.yml --repo codezorz/home-assistant-mijnted --ref main
```

Keep the required **CodeQL** code-scanning check and **Validate code** check in
the `main` ruleset. The workflow is named **CodeQL**, with matrix jobs named
**Analyze (actions)** and **Analyze (python)**. Both analyses upload using the
`/language:actions` and `/language:python` categories, then GitHub reports the
separate **CodeQL** code-scanning check. A skipped analysis job does not supply
that result, so the required check can remain **Expected**. A job skipped by a
job-level condition before matrix expansion can also display the literal name
`Analyze (${{ matrix.language }})`; that is not a completed language scan.

After a workflow fix lands, trigger a fresh PR event for an existing blocked PR
by updating its branch or closing and reopening it. Approve the fork workflow
run if prompted and verify both language jobs and the **CodeQL** result pass.
Re-enable auto-merge if closing/reopening cleared it. Rerunning an older run
uses its original workflow revision, so it may repeat the obsolete condition.
