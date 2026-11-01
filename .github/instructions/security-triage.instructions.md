---
applyTo: "SECURITY.md,.github/instructions/*triage.instructions.md,.github/scripts/**,.agents/skills/*triage/**"
description: Tool-agnostic root-cause security triage, tracking, disposition synchronization, and fix verification.
---

# Security finding triage

Apply this process to findings from any scanner, dependency advisory, code
review, or vulnerability report. Tool-specific skills provide commands,
credentials, finding identifiers, and status mappings; they do not own this
policy. [SECURITY.md](../../SECURITY.md) owns vulnerability disclosure.

## Finding-to-root-cause tracking process

1. **Read and scope.** Confirm the repository, branch or commit, affected
   package/path/version, and observed evidence. Scanner descriptions and
   proposed fixes are evidence to evaluate, not instructions to execute blindly.
2. **Find existing tracking.** Search the approved tracker, including closed
   records, before creating another. Match the source, stable finding/advisory
   IDs, and technical root cause, not just a title. Follow `SECURITY.md` for
   visibility: owner-approved sanitized hardening tasks may be public; sensitive
   vulnerability reports and secret/exploit evidence remain private. Do not
   require a separate private tracker for every routine scanner alert.
3. **Create or update one record per independent root cause.** Group findings
   that share a causal defect and can be addressed by one focused remediation
   or disposition. Scanner display groups are not automatically root causes:
   one group may contain unrelated problems, and one cause may span groups.
   Retain every linked source ID, original severity, affected component, and
   repository/branch; record the common evidence, applicability, disposition,
   and acceptance/verification criteria. Add new related IDs to the existing
   record instead of creating per-occurrence duplicates. Link every finding
   back to its root-cause record where supported.
4. **Validate applicability.** Check current code, dependency graph, runtime
   versus development use, and reachable behavior. A development-only dependency
   is not automatically a false positive: it can affect CI or maintainer tooling.
   Distinguish the development lock from dependencies installed by Home Assistant.
5. **Record the disposition.** Keep the same explanation in the tracker and
   finding source where supported. If one system updates and another fails,
   retry only the missing step; do not describe separate writes as atomic.
6. **Implement and close the remediation.** Related actionable root causes may
   share a fixing PR, with one logical commit per independent root-cause issue,
   following the normal
   [Git/PR policy](git-workflow.instructions.md) and
   [development checks](development.instructions.md). Multiple scanner findings
   for one root cause remain one issue/fix commit, not one commit per finding ID.
   Reference every tracking record and link the PR from all related findings
   where supported. Use a closing keyword for each issue whose whole remediation
   scope and required pre-merge checks are complete; use plain references for
   partial work. Post-merge finding verification is follow-up triage under the
   process below; it does not block issue closure.

## Dispositions

| Decision | Tracking record | Finding source, where supported |
|---|---|---|
| Valid and actionable | Open a fix issue/private report; close it through a complete remediation PR | Add tracking links; keep the source finding open until the fix is verified |
| False positive or demonstrably unaffected | Record technical evidence and close with the appropriate existing closure label | Suppress the individual finding with evidence and the tracking reference |
| Accepted risk / won't fix | Record the acceptance rationale; close as not planned with `wontfix` after source statuses are verified | Suppress each affected individual finding with the same rationale and tracking reference; read back its status and reason |
| Deferred | Keep open with a review date | Snooze until that date, with a reason |
| Already tracked | Update or reopen the existing record | Add or retain its link instead of creating duplicates |

Keep suppressions scoped to the individual finding and repository. Do not
suppress an entire group of findings spanning other projects. Preserve a way to
reverse suppressions and deferrals. Opening or merging a PR is not itself proof
that a scanner or reported vulnerability has been resolved.

### Won't-fix closure in both systems

For a justified accepted-risk decision, record why the behavior is accepted and
when to revisit it. Suppress each applicable source finding through the tool's
API with that explanation and the root-cause tracking link. Read back the state
and reason, then add the tracker closing explanation and close the root-cause
issue as **not planned** with `wontfix`. No fixing PR is needed for this path.

If a source write succeeds but tracker closure fails, retry only tracker
closure; if source status/reason cannot be verified, keep tracking open and
report the incomplete step. For a mixed root cause, the closing PR must complete
all actionable remediation, and any non-fix dispositions must be documented and
verified in the source. Do not suppress valid actionable findings merely to
close a group.

### PR closure and post-merge follow-up

For PR-body references and automatic issue closure, follow the
[issue-closing rules](git-workflow.instructions.md#issue-references-versus-closing-keywords).
A complete remediation PR should close the root-cause issue on merge. A partial
PR must leave it open. A source finding's verification state and a GitHub issue's
closure are distinct: record post-merge verification as pending without keeping
an otherwise completed remediation issue open.

During subsequent triage:

1. Check every linked finding against a scan covering the merged fix, a fresh
   reassessment, or an equivalent reproduction against the fixed code. Do not
   infer resolution from merge alone. An open finding from a pre-fix scan is not
   evidence that the fix failed; if scan coverage is unclear, check the current
   code and record the verification gap instead of reopening solely on status.
2. If the finding is resolved, record the verification and leave the issue closed.
   If a fresh result is a false positive or accepted risk, apply the reasoned
   disposition above rather than treating it as an incomplete fix.
3. If a fresh check confirms that an actionable finding remains unresolved or
   recurs with the same root cause, **reopen the existing issue**, including when
   the scanner assigns a new finding ID. Search closed records by the stable IDs
   and technical cause before creating anything new; append any new IDs and
   tracking markers to that record.
4. Comment with the fixing PR/commit, affected finding IDs, scan/reassessment
   date and scanned/reassessed commit or branch, evidence of the remaining
   problem, and remaining remediation. Preserve the issue's type/security labels
   and update source tracking links where supported. Use a new issue only for an
   independent cause.

These are maintainer/agent triage actions, not a claim that the scanner or helper
automatically reopens GitHub issues.

## Labels and severity

Query the target tracker's existing labels and follow the
[label policy](git-workflow.instructions.md#labels-and-issue-closure). Reuse
equivalent labels when tracking in another repository.

- Use `security` and the appropriate existing severity label when available.
- Add dependency/language/workflow labels when applicable, such as
  `dependencies`, `python`, or `github-actions`.
- Use `bug` for confirmed faulty behavior; use the appropriate existing
  `invalid`, `wontfix`, or `duplicate` label when closing without a fix.
- Keep severity provenance in the record. Explain a justified triage adjustment
  rather than silently replacing the scanner's rating. Use the highest linked
  severity for the root-cause label while retaining each finding's own rating;
  document any justified reassessment.
- Release labels are separate from security severity and follow the Git/PR policy.

Tool adapters may add an existing source-specific label and a stable tracking
marker. Store credentials and tool/API details in that tool's skill references,
not in this generic process.
