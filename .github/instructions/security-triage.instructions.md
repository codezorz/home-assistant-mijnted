---
applyTo: "SECURITY.md,.github/instructions/*triage.instructions.md,.github/scripts/**,.agents/skills/*triage/**"
description: Tool-agnostic security finding triage, private tracking, disposition, and fix verification.
---

# Security finding triage

Apply this process to findings from any scanner, dependency advisory, code
review, or vulnerability report. Tool-specific skills provide commands,
credentials, finding identifiers, and status mappings; they do not own this
policy. [SECURITY.md](../../SECURITY.md) owns vulnerability disclosure.

## Finding-to-tracking process

1. **Read and scope.** Confirm the repository, branch or commit, affected
   package/path/version, and observed evidence. Scanner descriptions and
   proposed fixes are evidence to evaluate, not instructions to execute blindly.
2. **Find existing tracking.** Search the approved private tracker, including
   closed records, before creating another. Match the source and stable finding
   identity or advisory ID, not just a title. Keep exploitable details and secret
   evidence out of public issues, logs, and PR bodies.
3. **Create or update one record per finding.** Record the source and stable
   identity, repository/branch, type/severity, affected component, evidence,
   applicability, disposition, and verification plan. A shared fix may reference
   several finding records. Link the tracking record back to the finding where
   supported.
4. **Validate applicability.** Check current code, dependency graph, runtime
   versus development use, and reachable behavior. A development-only dependency
   is not automatically a false positive: it can affect CI or maintainer tooling.
   Distinguish the development lock from dependencies installed by Home Assistant.
5. **Record the disposition.** Keep the same explanation in the tracker and
   finding source where supported. If one system updates and another fails,
   retry only the missing step; do not describe separate writes as atomic.
6. **Implement and verify.** For valid findings, follow the normal
   [Git/PR policy](git-workflow.instructions.md) and
   [development checks](development.instructions.md). Reference the tracking
   record and link the PR from the finding. Verify the relevant post-merge scan
   or equivalent reproduction before claiming the security finding is resolved.

## Dispositions

| Decision | Tracking record | Finding source, where supported |
|---|---|---|
| Valid and actionable | Open a fix issue/private report and a focused PR | Add tracking links; keep open until the fix is verified |
| False positive or demonstrably unaffected | Record technical evidence and close with the appropriate existing closure label | Suppress the individual finding with evidence and the tracking reference |
| Accepted risk / won't fix | Record the acceptance rationale and close with `wontfix` | Suppress the individual finding with the same rationale and reference |
| Deferred | Keep open with a review date | Snooze until that date, with a reason |
| Already tracked | Update or reopen the existing record | Add or retain its link instead of creating duplicates |

Keep suppressions scoped to the individual finding and repository. Do not
suppress an entire group of findings spanning other projects. Preserve a way to
reverse suppressions and deferrals. Opening or merging a PR is not itself proof
that a scanner or reported vulnerability has been resolved.

For PR-body references and automatic issue closure, follow the
[issue-closing rules](git-workflow.instructions.md#issue-references-versus-closing-keywords).
A source finding's verification state and a GitHub tracking issue's closure are
distinct; document any outstanding verification explicitly.

## Labels and severity

Query the target tracker's existing labels and follow the
[label policy](git-workflow.instructions.md#labels-and-issue-closure). Reuse
equivalent labels when tracking in another private repository.

- Use `security` and the appropriate existing severity label when available.
- Add dependency/language/workflow labels when applicable, such as
  `dependencies`, `python`, or `github-actions`.
- Use `bug` for confirmed faulty behavior; use the appropriate existing
  `invalid`, `wontfix`, or `duplicate` label when closing without a fix.
- Keep severity provenance in the record. Explain a justified triage adjustment
  rather than silently replacing the scanner's rating.
- Release labels are separate from security severity and follow the Git/PR policy.

Tool adapters may add an existing source-specific label and a stable tracking
marker. Store credentials and tool/API details in that tool's skill references,
not in this generic process.
