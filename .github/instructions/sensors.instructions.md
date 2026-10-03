---
applyTo: "custom_components/mijnted/sensor.py,custom_components/mijnted/button.py,custom_components/mijnted/sensors/**"
description: Entity creation, sensor source/fallback contracts, statistics, units, and registration.
---

# Sensors and buttons

## Adding an entity

1. Implement usage metrics in `sensors/usage.py`, diagnostics in
   `sensors/diagnostics.py`, or per-device readings in `sensors/device.py`.
   Sensors inherit `MijnTedSensor`, which already sets the standard unique ID
   from `sensor_type`; do not duplicate that setup unnecessarily.
2. Export the class from `sensors/__init__.py` and register it in `sensor.py`.
   Buttons belong in `sensors/button.py` and are registered in `button.py`.
   The integration's `__init__.py` forwards platforms, not entity lists.
3. Entities read `coordinator.data`; do not add direct API calls to sensors.
   Dynamic devices are created at platform setup, not on every refresh.
4. Follow `conventions.instructions.md` for entity identity compatibility and
   `documentation.instructions.md` for required documentation updates.

## Values, availability, and statistics

- `doc/SENSORS.md` owns the per-sensor source and missing-data contract. A
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
- Recorder injection helpers live in `sensors/base.py`. Preserve deduplication
  and late-correction reinjection behavior; average statistics are state-only.
- Reuse `_build_device_info` for sensor/button device association.
- Follow `doc/MONTH_SWITCH.md` for calendar-month identity, zero-day API lag,
  previous-month completion, and current-month baseline locking.
