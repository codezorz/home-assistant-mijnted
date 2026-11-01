---
applyTo: ".github/scripts/aikido.py,.github/scripts/aikido.test.py,.agents/skills/aikido-triage/**,.github/instructions/aikido-triage.instructions.md"
description: Aikido helper implementation rules for credentials, scoped API operations, and mocked validation.
---

# Local Aikido triage tooling

- [Security triage instructions](security-triage.instructions.md) own the generic
  process; [SECURITY.md](../../SECURITY.md) owns disclosure. The
  [Aikido skill](../../.agents/skills/aikido-triage/SKILL.md) and its
  [tool reference](../../.agents/skills/aikido-triage/references/aikido.md)
  own Aikido setup and commands. This tooling runs locally on demand.
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
  A root-cause issue may contain multiple individual markers; link and verify
  every affected finding without broadening API suppression to its display group.
  Follow the [disposition verification policy](security-triage.instructions.md#wont-fix-closure-in-both-systems)
  for source-state read-back requirements.
- Mock HTTP and native APIs in unit tests. Live smoke tests are read-only;
  applying finding dispositions is a separate explicit operation.
