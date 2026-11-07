---
applyTo: ".agents/skills/aikido-triage/**,.github/instructions/aikido-triage.instructions.md"
description: Aikido Developer-plan boundaries and dashboard-based, repository-scoped security triage.
---

# Aikido Developer-plan triage

- Use the free Developer-plan setup in the [Aikido reference](../../.agents/skills/aikido-triage/references/aikido.md#developer-plan-and-github-apps).
  The public REST API, GitHub issue sync, and PR security review require an
  upgrade. Do not request API credentials or re-enable paid PR checks as part of
  routine triage. The retired local REST helper is no longer supported.
- Use the [Aikido skill](../../.agents/skills/aikido-triage/SKILL.md) and its
  [dashboard reference](../../.agents/skills/aikido-triage/references/aikido.md)
  for finding identity, manual tracking, and disposition verification.
- Follow [security triage policy](security-triage.instructions.md) and
  [SECURITY.md](../../SECURITY.md). Scope every finding and disposition to this
  repository and the scanned branch; scanner groups can span repositories.
- Verify scan coverage and dashboard state before claiming a finding is solved
  or ignored. If UI access or individual-finding controls are unavailable,
  report the verification gap rather than assuming a write or scan succeeded.
