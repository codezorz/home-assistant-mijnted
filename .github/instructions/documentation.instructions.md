---
applyTo: "custom_components/mijnted/**,README.md,AGENTS.md,CLAUDE.md,SECURITY.md,doc/**,.github/instructions/**,.agents/**,.claude/**"
description: Authoritative documentation homes, change-to-doc mapping, and DRY shared-agent guidance.
---

# Documentation ownership and synchronization

Update documentation in the same change when behavior or developer workflows
change. Verify claims against code; distinguish existing behavior from proposals.

## Authoritative homes

| Subject | Home | Related updates |
|---|---|---|
| Installation, setup, options, troubleshooting | `README.md` | Config-flow translations in `custom_components/mijnted/translations/en.json` |
| Sensor catalog, attributes, availability, statistics, reset button | `doc/SENSORS.md` | README overview; sensor implementation guidance if its contract changes |
| Month lifecycle and boundary timeline | `doc/MONTH_SWITCH.md` | Link from sensor docs; update related cache tests for code changes |
| HTTP endpoints, auth lifecycle, request/response formats | `doc/ENDPOINTS.md` | README setup if credentials/options change |
| Development setup, check commands, CI, manual verification | `doc/DEVELOPMENT.md` | Testing instructions when mock/test architecture changes |
| Branches, version policy, publishing, labels | `.github/instructions/git-workflow.instructions.md` | Skills should reference this policy |
| Worktree placement and naming | `.agents/skills/git-worktrees/SKILL.md` | Keep generic and repository-relative |
| Issue reporting / private vulnerability reporting | `doc/ISSUE_REPORTING.md` / `SECURITY.md` | GitHub issue forms when report fields change |

## Keep guidance DRY

- `AGENTS.md` is a short entry point and map, not a copy of every policy.
- `.github/instructions/` contains scoped implementation/policy guidance;
  keep `applyTo` patterns aligned with the files that need it.
- `.agents/skills/` contains on-demand workflows. Reference authoritative
  policy/command docs instead of reproducing them in skill checklists.
- `CLAUDE.md` imports shared entry instructions and README. The Claude
  session hook advertises instruction scopes and skill names/descriptions
  from their headers. Keep skill bodies in `.agents/skills/` only.
- README provides a user overview; link detailed reference material rather
  than maintaining a second API catalog or statistics specification.
- Use working relative Markdown links for navigation. Verify local targets,
  example field names, class names, and attributes before finishing.
- Follow the Git/version policy for bumps; documentation changes alone do
  not require an integration version bump.
