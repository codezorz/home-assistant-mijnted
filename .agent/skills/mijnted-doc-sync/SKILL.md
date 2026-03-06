---
name: mijnted-doc-sync
description: Use when code changes may require documentation updates, and you need a fast mapping from change type to required docs in this repo.
---

# Mijnted Documentation Sync

Use this skill when implementing changes that might require docs updates in the same PR.

## Change-to-doc mapping

- API/auth changes (`custom_components/mijnted/api.py`, `auth.py`, endpoint behavior):
  - Update `doc/ENDPOINTS.md`.
- Sensor additions/renames/behavior/attributes/state class changes:
  - Update `README.md` (Usage section).
  - Update `doc/SENSORS.md` when catalog behavior or edge cases change.
- Month-switch or monthly state behavior:
  - Update `doc/MONTH_SWITCH.md`.
- Config flow/options/text changes:
  - Update `custom_components/mijnted/translations/en.json`.
  - Update `README.md` configuration guidance.
- Version/requirements changes:
  - Ensure user-facing docs remain accurate.

## Execution checklist

1. Identify files changed under `custom_components/mijnted/**`.
2. Map each behavior change to required docs using the table above.
3. Update docs in the same PR as code changes.
4. Confirm no stale sensor/API descriptions remain.

## References

- `.github/instructions/documentation.instructions.md`
- `.github/instructions/sensors.instructions.md`
- `.github/instructions/api-auth.instructions.md`
- `README.md`
- `doc/SENSORS.md`
- `doc/MONTH_SWITCH.md`
- `doc/ENDPOINTS.md`

