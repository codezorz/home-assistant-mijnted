# Aikido dashboard reference

This repository uses Aikido's free Developer plan. The local REST API helper
has been removed; use the dashboard for Aikido and `gh` for GitHub tracking.

Follow [security triage policy](../../../../.github/instructions/security-triage.instructions.md)
and [SECURITY.md](../../../../SECURITY.md). These own root-cause grouping,
disclosure, dispositions, and verification requirements.

## Developer plan and GitHub Apps

The following published entitlements were checked on **2026-11-07**. Check the
[current pricing](https://www.aikido.dev/pricing) before relying on a changed
allowance or enabling another integration.

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
| **Aikido Issues** | Creates and synchronizes GitHub issues. | Can uninstall while staying on Developer. |
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
before relying on local scans or finding access. This repository does not
configure an MCP connection or require the retired REST credentials.

## Inspecting findings

1. Open [Repositories](https://app.aikido.dev/repositories) and select
   `codezorz/home-assistant-mijnted`. Confirm it is active, its scanned branch,
   and its last scan. A visible repository or installed app alone does not prove
   a recent scan completed.
2. Open the relevant finding in the repository or feed. Record its dashboard
   URL, available finding/repository IDs, severity, rule/advisory, affected
   package/path/version, and scan coverage. Keep raw secret evidence private.
3. Compare the finding against the current code and dependency graph. An older
   scan can remain open after a fix; check coverage before treating that as a
   failed remediation. The free plan has scheduled scans, not manual rescans.

If dashboard access or scan metadata is unavailable, record what could and
could not be verified. Do not request API credentials as a fallback.

## Finding identity and GitHub tracking

Search existing GitHub records, including closed issues, by stable finding IDs,
advisories, dashboard URLs, and technical root cause before creating another.
Use `gh` and the [issue policy](../../../../.github/instructions/issues.instructions.md)
for authorized GitHub updates. GitHub issue synchronization is not included in
this plan; tracking updates are manual.

Keep existing region/repository/finding-specific markers unchanged so earlier
records remain discoverable. When the dashboard exposes both numeric IDs, the
existing format is:

```text
<!-- aikido:app.aikido.dev:repo:123:issue:456 -->
<!-- aikido:app.aikido.dev:repo:123:issue:457 -->
```

Use actual IDs only; do not substitute a display-group ID for an individual
finding ID. If the UI does not expose those identifiers, retain the exact
dashboard URL and technical context instead of inventing a marker.

One root-cause record can contain multiple finding markers. Retain each
finding's severity, affected component, and repository/branch. Follow the
[label policy](../../../../.github/instructions/git-workflow.instructions.md#labels-and-issue-closure)
and reuse the existing `aikido` source label where available.

## Dashboard dispositions

Use individual-finding controls scoped to this repository. A display group may
contain findings from other projects; do not apply a group-wide ignore merely
to complete this repository's triage.

| Disposition | Aikido action and verification |
|---|---|
| Valid and actionable | Leave open, add a tracking reference where supported, and remediate through a reviewed PR. |
| False positive / unaffected | Ignore the individual finding with technical evidence and its root-cause tracking reference; verify the state and explanation. |
| Accepted risk / won't fix | Ignore each applicable individual finding with rationale and tracking; verify all states and explanations before closing GitHub tracking as not planned. |
| Deferred | Snooze until a future review date with a reason and tracking reference; verify the date and state. |
| Already tracked | Reuse the existing root-cause record and retain its finding links. |

Reopen the finding after an action and read back its state and rationale. Use
an available note/history entry to preserve the full explanation if the UI's
status label is generic. **Ignored** is different from **solved**. If an
individual disposition, note, or verification is unavailable, report the
remaining step instead of claiming both systems are synchronized.

After a remediation merges, wait for a scheduled scan covering the fix or
perform an equivalent reassessment against the fixed code. Record the evidence
and follow [post-merge policy](../../../../.github/instructions/security-triage.instructions.md#pr-closure-and-post-merge-follow-up).
Neither merging an AutoFix PR nor an old open finding proves the new code's
scan result.

## References

- [Scheduled scan frequencies and free-plan restrictions](https://help.aikido.dev/code-scanning/miscellaneous/scanning-frequencies)
- [Source-code GitHub connection](https://help.aikido.dev/code-scanning/connect-your-source-code/connect-github-account-to-aikido)
- [GitHub Issues integration and plan availability](https://integrations.aikido.dev/integrations/github-issues)
- [AutoFix overview](https://help.aikido.dev/autofix-and-remediation/overview-aikido-autofix)
- [Aikido feed](https://app.aikido.dev/issues)
- [AutoFix settings](https://app.aikido.dev/issues/fix/settings)
- [Ignore findings](https://help.aikido.dev/getting-started/core-functionalities/ignore-issues-to-remove-issues-from-main-feed)
- [Snooze findings](https://help.aikido.dev/getting-started/core-functionalities/snooze-issues-for-later)
