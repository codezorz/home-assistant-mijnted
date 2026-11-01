---
applyTo: "custom_components/mijnted/**,README.md,CONTRIBUTING.md,AGENTS.md,CLAUDE.md,SECURITY.md,docs/**,.github/instructions/**,.agents/**,.claude/**"
description: Authoritative documentation homes, change-to-doc mapping, and DRY shared-agent guidance.
---

# Documentation ownership and synchronization

Update documentation in the same change when behavior or developer workflows
change. Verify claims against code; distinguish existing behavior from proposals.

## Authoritative homes

| Subject | Home | Related updates |
|---|---|---|
| Installation, setup, options, troubleshooting | `README.md` | Config-flow translations in `custom_components/mijnted/translations/en.json` |
| Sensor catalog, attributes, availability, statistics, reset button | `docs/SENSORS.md` | README overview; sensor implementation guidance if its contract changes |
| Month lifecycle and boundary timeline | `docs/MONTH_SWITCH.md` | Link from sensor docs; update related cache tests for code changes |
| HTTP endpoints, auth lifecycle, request/response formats | `docs/ENDPOINTS.md` | README setup if credentials/options change |
| Development rules | `.github/instructions/development.instructions.md` | Test design stays in testing instructions |
| Development setup, check commands, manual verification | `docs/DEVELOPMENT.md` | Development instructions link to the detailed guide |
| CI constraints | `.github/instructions/ci.instructions.md` | Workflow rules reference the operational guide |
| CI operation, CodeQL setup, fork troubleshooting | `docs/CI.md` | CI instructions own development constraints |
| Agent setup and discovery | `.github/instructions/agent-tooling.instructions.md` | Entry files and skills reference this policy |
| Brand artwork maintenance | `.github/instructions/layout.instructions.md` | README owns installed icon behavior |
| Branches, version policy, publishing, labels, issue references/closure | `.github/instructions/git-workflow.instructions.md` | Skills should reference this policy |
| Detailed release setup, operation, and recovery | `docs/RELEASING.md` | Git workflow instructions own release policy |
| Worktree placement and naming | `.agents/skills/git-worktrees/SKILL.md` | Keep generic and repository-relative |
| Issue reporting / private vulnerability reporting | `docs/ISSUE_REPORTING.md` / `SECURITY.md` | GitHub issue forms when report fields change |
| Tool-agnostic security finding triage | `.github/instructions/security-triage.instructions.md` | `SECURITY.md` owns disclosure |
| Aikido commands, credentials, API details | `.agents/skills/aikido-triage/references/aikido.md` | Skill links the generic triage policy; scoped instructions own helper implementation rules |

## Keep guidance DRY

- `AGENTS.md` is a short entry point and map, not a copy of every policy.
- `.github/instructions/` contains development instructions and repository
  policy for contributors and agents; keep `applyTo` patterns aligned with
  the files that need it. Keep rules concise and link detailed setup,
  operational explanations, and troubleshooting from `docs/`.
- `.agents/skills/` contains on-demand workflows. Reference authoritative
  policy/command docs instead of reproducing them in skill checklists.
- `docs/` contains integration references and detailed contributor/maintainer
  guides. Development rules and repository policy belong in
  `.github/instructions/`; reusable skill workflows and tool-specific resources
  belong in `.agents/skills/`. Choose by content and audience, not by treating
  every contributor guide as an agent instruction. Directory READMEs explain
  ownership and link authoritative guidance without copying it.
- `CONTRIBUTING.md` is a short, discoverable contributor entry point, not a
  second policy source. Keep security triage policy tool-agnostic; scanner
  commands and credentials belong to the relevant skill's references.
- `CLAUDE.md` imports shared entry instructions and README. The Claude
  session hook advertises instruction scopes and skill names/descriptions
  from their headers. Keep skill bodies in `.agents/skills/` only.
- README provides a user overview; link detailed reference material rather
  than maintaining a second API catalog or statistics specification.
- Use working relative Markdown links for navigation. Verify local targets,
  example field names, class names, and attributes before finishing.
- Follow the Git/version policy. Keep the source manifest's development version;
  release workflows allocate beta versions even for documentation-only commits.
