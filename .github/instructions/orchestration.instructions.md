---
applyTo: "custom_components/mijnted/**"
description: Coordinator ownership, shared projections, persistence, and partial-refresh invariants.
---

# Orchestration

- Keep the flow: config entry → coordinator → platforms → entities reading
  `coordinator.data`. One coordinator per entry owns API fetching in `__init__.py`;
  entities make no cloud requests and do not depend on each other's enabled state.
- [Reporting architecture](../../docs/USAGE_REPORTING.md) owns module responsibilities,
  payloads, storage keys/retention, and recorder ownership. Prepare detached
  projections before listeners run; preserve each view's own period metadata.
- Keep monthly cache, daily observations, and device-name reservations separate.
  Restore before accepting updates, retry pending writes, and preserve durable
  state on load failure. Respect storage versions and configured retention constants.
- [Month lifecycle](../../docs/MONTH_SWITCH.md) owns boundary validation/repair.
  Use `DateUtil` for `YYYY-MM` cache keys and `M.YYYY` display/API IDs; do not mix them.
- A refresh can be partial. Preserve values only under the
  [sensor contract](../../docs/SENSORS.md); a returned payload does not prove every
  endpoint succeeded. [API/auth instructions](api-auth.instructions.md) own request,
  credential, token, and retry boundaries.
