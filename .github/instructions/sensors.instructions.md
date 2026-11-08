---
applyTo: "custom_components/mijnted/sensor.py,custom_components/mijnted/button.py,custom_components/mijnted/sensors/**"
description: Entity registration, value contracts, units, statistics, and lifecycle rules.
---

# Sensors and buttons

- Use the [module layout](layout.instructions.md). Inherit `MijnTedSensor` for its
  entry-scoped identity and reuse `_build_device_info` for device association.
  Export classes from `sensors/__init__.py`; register sensors/buttons in their
  platform entry points. `__init__.py` forwards platforms, not entity lists.
- Read coordinator data, not APIs or another entity's state. Follow the
  [reporting architecture](../../docs/USAGE_REPORTING.md) for projections and storage.
- [SENSORS.md](../../docs/SENSORS.md) owns sources, availability, per-view periods,
  missing-data behavior, discovery, units, and statistic IDs. Apply that contract
  consistently to live states and imports; do not replace missing data with zero
  or extend last-known caching to views that do not support it.
- Use quantity-correct state classes, `UNIT_MIJNTED` for usage, and suggested
  precision for presentation only. Do not round underlying measurements.
- Use the shared recorder helpers in `sensors/base.py`/`sensors/daily.py`.
  Keep automatic entity statistics separate from external reporting means, preserve
  period alignment/corrections, and read `coordinator.data["reading_report"]`
  instead of duplicating its calculation.
- [Translation instructions](translations.instructions.md) own default labels,
  dynamic placeholders, room context, and shared statistic-name resolution.
  [Compatibility conventions](conventions.instructions.md) own stable identities.
- Follow [month lifecycle](../../docs/MONTH_SWITCH.md) for baseline/zero handling.
  Scope live/comparison fallbacks to their periods and cancel callbacks/listeners
  on unload. Follow [documentation ownership](documentation.instructions.md) when behavior changes.
