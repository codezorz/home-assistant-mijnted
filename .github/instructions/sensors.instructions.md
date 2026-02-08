---
applyTo: "custom_components/mijnted/sensors/**"
---

# Sensors: adding one and choosing type

**Adding a sensor:**

1. Implement a class that inherits from `MijnTedSensor` in `sensors/base.py`. Constructor: `coordinator`, `sensor_type`, `name`. Set `_attr_unique_id` (e.g. `f"{DOMAIN}_{sensor_type.lower()}"`).
2. Put the class in the right module: `usage.py` (usage metrics), `diagnostics.py` (metadata/info), or `device.py` (per-device/room).
3. Export it from `sensors/__init__.py` and add it to the list of entities built in `__init__.py` / `sensor.py` (where the platform creates entities from the coordinator).

**Choosing the type (which file):**

- **Usage** (`usage.py`): Values derived from usage data (monthly, total, average, last year). Often use recorder/statistics (`async_import_statistics`, `StatisticMetaData`, `StatisticData`) and state classes like `STATE_CLASS_TOTAL` or `STATE_CLASS_TOTAL_INCREASING`. Historical injection logic lives in `sensors/base.py`.
- **Diagnostics** (`diagnostics.py`): Informational (last update, active model, delivery types, residential unit, etc.). No statistics injection.
- **Device** (`device.py`): Per-device or per-room sensors, created dynamically from API data.

**Other:**

- Device info: Use `MijnTedSensor._build_device_info(coordinator.data)` so all entities attach to the same MijnTed device.
- Units: Use `const.UNIT_MIJNTED` (or other constants from `const.py`). Usage sensors typically show zero decimal places.
- Do not change or remove `unique_id` without a migration or release note; automations and dashboards depend on entity identity.
- **Docs**: When adding or changing sensors, update **README.md** (Usage section) so the sensor list and descriptions stay accurate.
