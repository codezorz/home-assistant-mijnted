---
applyTo: ".github/scripts/aikido.py,.github/scripts/aikido.test.py,doc/SECURITY_TRIAGE.md,.agents/skills/aikido-triage/**"
description: Local Aikido credentials, scoped API operations, security triage, and private finding tracking.
---

# Local Aikido triage tooling

- `doc/SECURITY_TRIAGE.md` owns setup and the triage process; `SECURITY.md`
  owns disclosure. This tooling runs locally on demand.
- Read one Windows Generic Credential through the native API. Do not add
  credential files, environment fallbacks, token-printing commands, or logging
  of authentication values/response bodies. Release native buffers on errors.
- Authenticate only to a documented regional Aikido origin. Keep tokens in
  memory and refuse redirects. Preserve explicit repository/branch checks,
  individual finding IDs, pagination, and credential-safe failures.
- Group-wide suppression can affect other repositories; use individual finding
  writes. Prefix shared-group notes with the source repository/finding.
- Preserve stable tracking markers, reasoned dispositions, and the distinction
  between opening a fix PR and verifying that a scan has resolved a finding.
- Mock HTTP and native APIs in unit tests. Live smoke tests are read-only;
  applying finding dispositions is a separate explicit operation.
