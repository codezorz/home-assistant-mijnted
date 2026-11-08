# Aikido dashboard reference

Use Aikido's free Developer-plan dashboard and `gh` for manual GitHub tracking.

Follow [security triage policy](../../../../.github/instructions/security-triage.instructions.md)
and [SECURITY.md](../../../../SECURITY.md). These own root-cause grouping,
disclosure, dispositions, and verification requirements.

## Developer plan and GitHub Apps

Check [current pricing](https://www.aikido.dev/pricing) before relying on an
allowance or enabling another integration. The repository uses this setup:

| Capability | Developer-plan setup |
|---|---|
| Repository scans | Up to 10 repositories; scheduled rescans every 3 days. Dependency/license scanning, SAST, secrets, IaC, and outdated software checks are included. `uv.lock` supplies exact development dependency versions. |
| AutoFix | Includes 10 AI AutoFixes per month. Can create remediation PRs independently of incoming-PR scanning. |
| IDE integration | Included; optional local feedback between scheduled scans. |
| Incoming-PR security review / gating | Paid Basic feature; leave disconnected. |
| GitHub issue creation / sync | Paid feature; use manual GitHub tracking. |
| Public REST API / webhooks | Upgrade required; do not request local API credentials. |
| Manual repository rescans | Unavailable on the free plan; wait for a scheduled scan. |
| Aikido Libraries replacements | Paid Basic feature; use ordinary dependency upgrades for the free-plan workflow. |

The GitHub Apps are separate connections:

| GitHub App | Purpose | Developer-plan action |
|---|---|---|
| **Aikido Security** | Reads source repositories for scheduled scans. | Keep installed with access to `codezorz/home-assistant-mijnted`. |
| **Aikido Autofix** | Creates remediation PRs from findings. | Keep if using the included AutoFix allowance. |
| **Aikido Issues** | Creates and synchronizes GitHub issues. | Keep disconnected; use manual tracking. |
| **Aikido PR Checks** | Scans incoming PRs and publishes gating results. | Leave uninstalled/disconnected while staying on Developer. |

The **GitHub** tile under **PR Quality Gating** in
[integration settings](https://app.aikido.dev/settings/integrations) configures
the PR Checks app. Reconnecting it reinstalls PR gating, not source scanning.
Keep source access through **Aikido Security** and check the repository's active
status, scanned branch, and last completed scan. A retained listing or installed
app alone is not proof of current scan coverage.

### AutoFix setup

In [AutoFix settings](https://app.aikido.dev/issues/fix/settings), verify write
access, selected repositories, automatic PR categories, and PR metadata. Review
generated PRs through normal CI and Git/PR policy; keep auto-merge disabled
unless the maintainer explicitly chooses otherwise.

A saved category is not proof of plan entitlement: some need additional assets,
credits, or a paid feature. In particular, **Aikido library for majors** relies
on the paid Libraries feature; choose ordinary dependency upgrades for a
free-only configuration. Do not use **Test Autocreation** for a read-only audit,
because it can create real PRs.

### Optional local feedback

[IDE plugins](https://help.aikido.dev/ai-and-dev-tools/ide-plugins-overview) provide
local SAST, IaC, secrets, and dependency feedback. The
[secrets pre-commit hook](https://help.aikido.dev/ai-and-dev-tools/aikido-secrets-pre-commit-hook)
can check staged files. Inspect existing hooks and ask before installing or
changing global Git/editor configuration.

[Aikido MCP](https://help.aikido.dev/ai-and-dev-tools/aikido-mcp) is a separate
optional coding-tool connection. Verify workspace availability and
[permissions](https://help.aikido.dev/ai-and-dev-tools/aikido-mcp/mcp-permissions)
before relying on local scans or finding access. The repository does not configure
an MCP connection.

## Inspecting findings

1. Select `codezorz/home-assistant-mijnted` in [Repositories](https://app.aikido.dev/repositories).
   Verify active status, scanned branch/commit, and completed scan coverage.
2. Capture the finding's exposed identifiers/URL and evidence under the
   [root-cause process](../../../../.github/instructions/security-triage.instructions.md#finding-to-root-cause-tracking-process).
3. Compare against current source/dependencies. Finding status must be interpreted
   against the scan's coverage; this plan uses scheduled rather than manual rescans.

If dashboard access or scan metadata is unavailable, record what could and
could not be verified. Do not request API credentials as a fallback.

## Finding identity and GitHub tracking

Use `gh` under the [tracking policy](../../../../.github/instructions/security-triage.instructions.md#finding-to-root-cause-tracking-process).
Preserve region/repository/finding markers and exact dashboard URLs. When both
numeric IDs are exposed, the marker format is:

```text
<!-- aikido:app.aikido.dev:repo:123:issue:456 -->
<!-- aikido:app.aikido.dev:repo:123:issue:457 -->
```

Use actual IDs only; do not substitute a display-group ID for an individual
finding ID. If the UI does not expose those identifiers, retain the exact
dashboard URL and technical context instead of inventing a marker.

Reuse the `aikido` source label under [label policy](../../../../.github/instructions/git-workflow.instructions.md#labels-and-issue-closure).

## Dashboard dispositions

Use individual-finding controls scoped to this repository. A display group may
contain findings from other projects; do not apply a group-wide ignore merely
to complete this repository's triage.

Apply [disposition policy](../../../../.github/instructions/security-triage.instructions.md#dispositions):
use **Ignore** for justified suppression and **Snooze** for dated deferral, with
the rationale and tracking reference. Actionable findings remain open for remediation.

Reopen the finding after an action and read back its state and rationale. Use
an available note/history entry to preserve the full explanation if the UI's
status label is generic. **Ignored** is different from **solved**. If an
individual disposition, note, or verification is unavailable, report the
remaining step instead of claiming both systems are synchronized.

Verify remediation under [post-merge policy](../../../../.github/instructions/security-triage.instructions.md#pr-closure-and-post-merge-follow-up)
using a covering scheduled scan or equivalent reassessment.

## References

- [Scheduled scan frequencies and free-plan restrictions](https://help.aikido.dev/code-scanning/miscellaneous/scanning-frequencies)
- [Source-code GitHub connection](https://help.aikido.dev/code-scanning/connect-your-source-code/connect-github-account-to-aikido)
- [GitHub Issues integration and plan availability](https://integrations.aikido.dev/integrations/github-issues)
- [AutoFix overview](https://help.aikido.dev/autofix-and-remediation/overview-aikido-autofix)
- [Aikido feed](https://app.aikido.dev/issues)
- [AutoFix settings](https://app.aikido.dev/issues/fix/settings)
- [Ignore findings](https://help.aikido.dev/getting-started/core-functionalities/ignore-issues-to-remove-issues-from-main-feed)
- [Snooze findings](https://help.aikido.dev/getting-started/core-functionalities/snooze-issues-for-later)
