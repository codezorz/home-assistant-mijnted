# Usage reporting architecture

This guide owns computation/data ownership and persistence. The
[sensor reference](SENSORS.md) owns entity behavior and graph configuration;
[month lifecycle](MONTH_SWITCH.md) owns boundary rules;
[endpoints](ENDPOINTS.md) owns API/auth contracts.

## Coordinator data flow

One config-entry coordinator fetches/normalizes data and prepares projections
before platform listeners run. Entities consume that data independently of each
other's enabled state.

| Owner | Output/responsibility |
|---|---|
| `__init__.py` | API payloads, monthly cache load/save/enrichment, coordinator/platform setup |
| `reconciliation.py` | Compatible opening/closing anchor repair and persisted retry metadata |
| `daily.py` | Complete dated checkpoints, `daily_usage`, and the latest `reading_snapshot` |
| `utils/readings.py` | `reading_report` from the complete checkpoint and matching opening baseline |
| `naming.py` | Detached `device_names` context/ordinal projection |
| `localization.py` | HA-loaded labels and reporting-series name synchronization |
| `sensors/` | Entity-local values/period metadata and recorder imports |

`reading_report` pairs its value with `month_id`, `reading_date`, boundaries, and
provenance. Partial newer-date responses cannot advance a complete report's date
or replace it with mixed-date readings. Each average/comparison view identifies
its own selected period rather than inheriting the report's date.

## Monthly cache and boundary reconciliation

The monthly store `mijnted_monthly_cache_<entry_id>` retains 16 historical months
and the current month. Dictionary keys are `YYYY-MM`; API/display IDs are `M.YYYY`.
Entries contain per-device readings, averages, publication provenance, and
boundary state. A monthly reset rebuilds this cache/injection tracking.

Reconciliation uses real per-device anchors to repair adjacent baselines, with
persisted `boundary_retry_at`/`boundary_retry_count` and one-to-six-hour retry
backoff. It does not distribute an aggregate correction across fabricated device
readings. [Month lifecycle](MONTH_SWITCH.md#month-lifecycle-state) defines
publication, locking, revision, and January rules.

## Forward daily tracking

`mijnted_daily_<entry_id>` stores two complete dated checkpoints and up to 500
observed daily results. `daily.py` validates the device set and dates before
advancing checkpoints; it consumes newly received readings without historical scans.
The [daily sensor contract](SENSORS.md#reported-daily-usage-report-attributes-and-statistics)
defines computability and graph interpretation.

## Device-name reservations

`mijnted_device_names_<entry_id>` stores context groups, reserved ordinals, and each
device's latest naming context. It is independent of monthly/daily consumption
storage and language. The [naming contract](SENSORS.md#duplicate-device-names)
defines grouping and visible suffixes.

Daily observations and name reservations survive monthly resets. Their trackers
restore storage before accepting updates and retry dirty writes even when a
successful poll's inputs are unchanged. Failed loads preserve durable data.

## Independently selectable statistics

`sensors/base.py` and `sensors/daily.py` import canonical period-aligned series.
Published usage owns all four monthly exports and the daily export; standalone
views provide entity-card selections and can import their corresponding series.
All exporters share series identity/name resolution.

Recorder owns stored statistics independently of integration caches. External
reporting means and entity-state collection/imports are separate series; retained
periods are upserted for corrections. [Graph configuration](SENSORS.md#monthly-usage-and-building-average-graphs)
owns their IDs, reduction types, and examples.

## Validation

[Testing instructions](../.github/instructions/testing.instructions.md) own mock
boundaries and native/reducer coverage. Use the [development guide](DEVELOPMENT.md)
for commands and installed-HA verification.
