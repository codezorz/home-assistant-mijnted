---
applyTo: "custom_components/mijnted/sensor.py,custom_components/mijnted/button.py,custom_components/mijnted/sensors/**"
description: Entity creation, sensor source/fallback contracts, statistics, units, and registration.
---

# Sensors and buttons

## Adding an entity

1. Implement monthly/total/report entities in `sensors/usage.py`, daily report
   projections/import helpers in `sensors/daily.py`, diagnostics in
   `sensors/diagnostics.py`, or per-device readings in `sensors/device.py`.
   Sensors inherit `MijnTedSensor`, which already sets the standard unique ID
   from the config-entry ID and `sensor_type`; do not duplicate that setup
   unnecessarily.
2. Export the class from `sensors/__init__.py` and register it in `sensor.py`.
   Buttons belong in `sensors/button.py` and are registered in `button.py`.
   The integration's `__init__.py` forwards platforms, not entity lists.
3. Entities read `coordinator.data`; do not add direct API calls to sensors.
   Primary device sensors are created at platform setup. Water discovery also
   runs after successful coordinator refreshes, adding only unseen delivery-type/
   device-number pairs and removing its listener on config-entry unload.
4. Follow `conventions.instructions.md` for entity identity compatibility and
   `documentation.instructions.md` for required documentation updates.

## Display names

- Follow [translation instructions](translations.instructions.md) for entity-local
  names, dynamic room context, installation language, and shared statistic labels.
  HA supplies the entity's device context; reporting-series identity determines
  the related statistic label, independently of which entity exports it.

## Values, availability, and statistics

- `docs/SENSORS.md` owns the per-sensor source and missing-data contract. A
  failed coordinator refresh makes sensors unavailable; a successful partial
  refresh can leave individual values stale or unknown.
- Preserve `_last_known_value` only for sensors designed to cache it. Do not
  turn empty/error responses into a new zero that overwrites a known value.
  A valid zero and missing data are different cases. The average-monthly,
  timestamp, and other diagnostics do not all have last-known fallbacks.
- `_last_known_value` is in-memory only. Persisted monthly history is a
  separate coordinator cache; do not treat one as a substitute for the other.
- Choose units and `SensorStateClass` based on the quantity. Use `UNIT_MIJNTED`
  for usage units and zero suggested display precision where appropriate;
  display precision does not round underlying values.
- Recorder injection helpers live in `sensors/base.py`. Keep canonical external
  monthly usage/average series isolated from automatic live-entity statistics.
  Upsert consumption-month aggregate samples as means from available dated
  reports, including revisions and actual reported zero. Import retained periods on refresh so
  corrections to any cached month are applied.
  Published usage does not auto-collect statistics; it owns all four external
  monthly reporting series and the forward daily series independently of the
  standalone average/comparison entities. Retain those entities' identities for
  ordinary dashboard selection. Daily values are attributes and statistics, not
  another entity. The report state follows the received reading month, without
  a synthetic calendar zero. Read `coordinator.data["reading_report"]` rather than
  duplicating calculations or reading another entity. Each comparison/average
  view keeps its own period metadata; do not relabel a lagged average with the
  reading report's month. Daily data is independently dated.
  Daily imports use the reading date and only observed forward daily results;
  never fabricate gaps or scan daily history during setup/reset.
  Apply the `docs/SENSORS.md` missing-data contract consistently to live values
  and recorder imports.
- Reuse `_build_device_info` for sensor/button device association.
- Follow `docs/MONTH_SWITCH.md` for calendar-month identity, zero-day API lag,
  previous-month completion, and correctable baseline locking. Monthly usage's
  local rollover callback must be cancelled on unload; scope its fallback to the
  calendar month so a previous-month value cannot leak across midnight.
