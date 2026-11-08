# Sensors Reference

This document describes all MijnTed sensors, what they represent, and how they behave in edge cases.

## Scope

- Integration domain: `mijnted`
- Platforms: `sensor`, `button`
- Sensor code:
  - `custom_components/mijnted/sensor.py`
  - `custom_components/mijnted/sensors/usage.py`
  - `custom_components/mijnted/sensors/diagnostics.py`
  - `custom_components/mijnted/sensors/device.py`
  - `custom_components/mijnted/sensors/base.py`

## How Sensor Values Are Produced

- Sensors do not call the API directly. They only read `coordinator.data`.
- The `DataUpdateCoordinator` fetches API data and updates all sensors.
- Sensor availability is shared:
  - Available when `coordinator.last_update_success` is true and data exists.
  - Unavailable when a refresh fails with `UpdateFailed`.
- Some sensors keep an in-memory `_last_known_value` and return that during partial outages.
- `_last_known_value` is not persisted across Home Assistant restarts.
- Entity names use the configured device name as their prefix through Home
  Assistant's `has_entity_name` behavior.
- Unique IDs use `mijnted_<configEntryId>_<entityKey>` so multiple config
  entries remain independent. Entity IDs are managed by Home Assistant's registry.

## Sensor Catalog

### Language and display names

MijnTed provides English, Dutch, and German UI labels. Names in this catalog are
the English defaults. Setup/options/reauthentication dialogs and supported
frontend state/attribute labels follow Home Assistant's interface language.

Default entity names use the Home Assistant **server language** when the platform
is set up. Upgrading replaces integration-owned defaults through the existing
entity registry entries. After changing the server language, reload the MijnTed
integration or restart Home Assistant to refresh its defaults. Changing only your
profile's language does not rename entities. Your configured device name, entity
name overrides, existing entity IDs, and history are retained.

Known room codes (`KA` and `W`) appear as translated room context in device and
water-meter names. Unknown codes and arbitrary room names remain verbatim; a
missing room uses the device number. Room-context changes update default names
on refresh without changing identity or replacing custom names.

All five external reporting-statistic names use the same installation-level
language policy. Existing metadata names are refreshed on setup, including when
there is no new data to import. A recorder metadata failure does not block sensor
creation; name updates retry after a later successful refresh. Statistic IDs,
units, timestamps, and stored measurements stay intact. Shared series receive the
same name from every exporter, including when standalone comparison entities are disabled. The
calendar **Monthly usage** entity and the external **Published usage** series
retain their different meanings. Custom dashboard/card labels remain yours.

Some diagnostic content deliberately retains its raw representation:

- Model identifiers, API delivery codes, unknown unit descriptions, and raw room
  attributes remain technical/API values. Known unit descriptions use the
  diagnostic sensor's [translated state](#units-of-measurement).
- **Latest available insight** retains its existing `MonthName YYYY` state for
  compatibility with templates/history. Its month text uses the Python process
  locale, not the HA server/profile language; HA's state translations cannot
  format this dynamic month/year string with placeholders. Its entity name and
  supported attribute labels are translated.
- Nested `current`, `history`, statistics-tracking, and residential-unit payloads
  retain raw keys/values. HA's entity attribute translations label top-level
  attributes, not arbitrary nested JSON. Canonical units such as `Units` and `m³`
  remain unchanged so recorder data keeps the same meaning.

## Usage Sensors

### Monthly usage

- Class: `MijnTedMonthlyUsageSensor`
- Unique ID: `mijnted_<configEntryId>_monthly_usage`
- Name: `<configured device name> Monthly usage`
- Unit: `Units`
- State class: `TOTAL`
- Purpose: current calendar month usage.
- Value logic:
  - Normal case: `total_usage_end - total_usage_start`
  - January: `total_usage_end` (year reset handling)
  - Fallback: `current.total_usage` from month cache
  - If data is missing: returns last known value
- Attributes:
  - `month_id` (`M.YYYY`)
  - `start_date` (`YYYY-MM-DD`)
  - `end_date` (`YYYY-MM-DD`)
  - `days` (inclusive day count)
  - `monthly_statistic_id` (canonical consumption-month graph series)
- A local month-boundary callback resets the projection to zero even between API
  polls. Cached last-known values are scoped to their calendar month. Normal
  coordinator failures still make the entity unavailable.
- Verified closing-reading corrections can revise the following month's baseline
  and lower its provisional usage; a start lock does not prevent reconciliation.

### Published usage

- Class: `MijnTedPublishedUsageSensor`
- Unique ID: `mijnted_<configEntryId>_published_usage`
- English name: `<configured device name> Published usage`
- Unit: `Units`; state class: none.
- Purpose: a lagging month-to-date own-usage report following the API's reading
  month, not the calendar month. October 31's 41 can arrive on November 2; when
  November 1's readings arrive on November 3, the report switches to November's
  actual available usage. That first value may already be nonzero.
- "Published" in the entity name means available from MijnTed, not permanently
  final. Its coordinator-owned `reading_report` uses the latest complete received
  dated observation and that month's cached opening baseline. A final-day report
  uses a valid official monthly total when available; otherwise it uses the dated
  meter difference. Historical publication recognition still uses a finite
  nonnegative own total plus usable non-null building average, independently of
  whether current-month readings are available. Placeholder zero is not a
  published monthly result; actual observed/official zero is valid.
- No calendar reset or synthetic midnight/end-of-day zero is inserted into this
  entity. API dates do not prove a precise 23:59 observation time. Ordinary state
  history records receipt time; external statistics identify reporting periods.
- Missing data: unknown until a usable reading snapshot/baseline exists. Partial
  endpoints keep the last complete dated observation; restart restores its
  checkpoint. Shared coordinator failures make the entity unavailable.
- Own-period attributes: `month_id`, `reading_date`, `start_date`, `end_date`,
  `value_source` (`reported` or `published`), `start_locked`, and
  `boundary_reconciled`. Calculations belong to the coordinator. Average/comparison
  values and their period metadata remain in their own standalone views; they are
  not copied into this sensor with the reading month's date.
- Daily attributes: `reported_daily_usage` and `reported_daily_date`, when a day
  can be calculated. These have their own reading date and do not change the
  monthly main state. There is no additional daily sensor entity.
- Own graph IDs: `monthly_statistic_id` and `daily_statistic_id`.
  Each average/comparison view exposes its own `monthly_statistic_id`.
  All series are independently selectable from source **mijnted**.
- It shares the canonical own-usage monthly series with Monthly usage. Existing
  retained historical months are backfilled into that series, including late
  corrections. Ordinary state history begins when the entity is created.
- `boundary_reconciled: false` means the published total is usable but repair of
  the associated per-device boundary is still pending for a completed month;
  an open month simply has no verified closing boundary yet.
- It exports all four monthly reporting series and the forward daily series.
  Average/comparison entities provide selectable views for ordinary entity
  cards; the report's graph imports do not depend on them
  being enabled. Canonical current-month graph totals use the last complete dated
  report. The month receives a sample when its readings are available, including
  an actual reported zero. The calendar Monthly usage entity owns the calendar
  zero projection and its entity-based statistics independently.

### Reported daily usage (report attributes and statistics)

- Available through Published usage's `reported_daily_usage` and
  `reported_daily_date` attributes and external **Reported daily usage** statistic.
  This is a date-aligned daily series, not a separate entity.
- Unit: `Units`. Daily information describes the latest computable reported date,
  often behind today, and does not reset at midnight.
- Source: newly received primary-meter readings with the API's readings-available
  date. The first complete observation seeds a checkpoint. A result requires two
  consecutive dates with compatible device sets; January 1 uses the annual zero
  baseline. Valid daily zero is reported.
- There is **no historical daily backfill or dated-endpoint scan**. A gap, invalid
  reading, or changed device set is not converted into fabricated daily usage.
  Tracking resumes once consecutive compatible observations are available.
- Repeat observations of the latest date can revise that day's total. Older dates
  are not actively revisited; this is reported data, without a daily publication/
  finality marker. Daily sums are not the authoritative published monthly report.
- Two dated checkpoints and up to 500 observed daily results are persisted in a
  separate entry-scoped store, surviving integration reloads and HA restarts.
- Daily attributes are absent until the first computable day. During a gap/partial
  failure the latest valid daily value keeps its original date. The report's
  monthly state and normal availability contract are independent of daily gaps.
- For a daily Statistics graph, use the external `daily_statistic_id` with
  **Day + Mean**. Each mean sample is a single daily consumption total, placed at
  HA-local midnight of its reading date, independent of arrival time. Month + Mean
  on this daily series would show an average of daily totals; use the separate
  monthly series for monthly consumption.

### Last year monthly usage

- Class: `MijnTedLastYearMonthlyUsageSensor`
- Unique ID: `mijnted_<configEntryId>_last_year_monthly_usage`
- Name: `<configured device name> Last year monthly usage`
- Unit: `Units`
- State class: `TOTAL`
- Purpose: usage for the same month in the previous year.
- Value source: previous-year same-month entry in `monthly_history_cache` (`total_usage`).
- Missing data behavior: returns the last known value within the same comparison
  period; unknown when that period has no known value. Current meter response
  availability does not gate historical cache lookup.
- Attributes:
  - `month_id` (current month key)
  - `last_year_month_id`
  - `monthly_statistic_id` (import-only last-year own-usage comparison)

### Average monthly usage

- Class: `MijnTedAverageMonthlyUsageSensor`
- Unique ID: `mijnted_<configEntryId>_average_monthly_usage`
- Name: `<configured device name> Average monthly usage`
- Unit: `Units`
- State class: none (monthly statistics are imported separately).
- Purpose: latest available historical monthly average.
- Value source: newest history entry with non-null `average_usage`.
- Missing data behavior: returns `None` (no last-known fallback in this sensor).
- Attributes:
  - `month_id` (of the history entry used for the value)
  - `monthly_statistic_id` (import-only monthly-average series for graphs)

### Last year average monthly usage

- Class: `MijnTedLastYearAverageMonthlyUsageSensor`
- Unique ID: `mijnted_<configEntryId>_last_year_average_monthly_usage`
- Name: `<configured device name> Last year average monthly usage`
- Unit: `Units`
- State class: none (monthly statistics are imported separately).
- Purpose: average usage for the same month in the previous year.
- Value source: previous-year same-month entry in `monthly_history_cache` (`average_usage`).
- Missing data behavior: returns the last known value within the same comparison
  period; unknown when that period has no known value. Current meter response
  availability does not gate historical cache lookup.
- Attributes:
  - `month_id` (current month key)
  - `last_year_month_id`
  - `monthly_statistic_id` (import-only last-year comparison series for graphs)

### Total usage

- Class: `MijnTedTotalUsageSensor`
- Unique ID: `mijnted_<configEntryId>_total_usage`
- Name: `<configured device name> Total usage`
- Unit: `Units`
- State class: `TOTAL_INCREASING`
- Purpose: current cumulative reading (sum of `currentReadingValue` across devices).
- Value source: `filter_status`.
- Missing data behavior: returns last known value.
- Attributes:
  - `current`: month payload for current month
  - `history`: list of month payloads for historical months
  - `current` and every `history` entry share the same month-level keys:
    - `month_id`
    - `year`
    - `month`
    - `start_date`
    - `end_date`
    - `average_usage`
    - `devices`
    - `days`
    - `average_usage_per_day`
    - `total_usage_start`
    - `total_usage_end`
    - `total_usage`
     - `status` (`OPEN`, `COMPLETE_READINGS`, `FINALIZED`)
     - `published_usage` (published own total, or null)
     - `value_source` (`published` or `readings`)
     - `boundary_reconciled` (historical boundary verified against publication)

## Diagnostic Sensors

### Last update

- Class: `MijnTedLastUpdateSensor`
- Unique ID: `mijnted_<configEntryId>_last_update`
- Name: `<configured device name> Last update`
- Device class: `timestamp`
- Category: `diagnostic`
- Purpose: date for which device readings are currently available (often 1-2 days behind calendar date), converted to ISO timestamp at midnight UTC.
- Accepted source formats: `DD/MM/YYYY`, `YYYY-MM-DD`, or ISO-like strings.
- Missing/invalid source behavior: returns `None`.

### Last successful sync

- Class: `MijnTedLastSuccessfulSyncSensor`
- Unique ID: `mijnted_<configEntryId>_last_successful_sync`
- Name: `<configured device name> Last successful sync`
- Device class: `timestamp`
- Category: `diagnostic`
- Purpose: calendar timestamp of the most recent successful synchronization with the API (integration refresh success moment).
- Note: this is sync time, not the "readings available until" date.
- A partial refresh can still advance this timestamp: failures inside the concurrent endpoint fetch are replaced with empty defaults. It is not an all-endpoints-success indicator. Returning cached coordinator data after a connection error retains the earlier timestamp.

### Active model

- Class: `MijnTedActiveModelSensor`
- Unique ID: `mijnted_<configEntryId>_active_model`
- Name: `<configured device name> Active model`
- Category: `diagnostic`
- Purpose: active model identifier.
- Missing data behavior: returns `None`.

### Delivery type

- Class: `MijnTedDeliveryTypesSensor`
- Unique ID: `mijnted_<configEntryId>_delivery_types`
- Name: `<configured device name> Delivery type`
- Category: `diagnostic`
- Purpose: comma-separated delivery types.
- Missing/empty behavior: returns `None`.

### Residential unit

- Class: `MijnTedResidentialUnitDetailSensor`
- Unique ID: `mijnted_<configEntryId>_residential_unit_detail`
- Name: `<configured device name> Residential unit`
- Category: `diagnostic`
- Purpose: residential unit identifier plus full detail attributes.
- State: `residential_unit`
- Attributes: `residential_unit_detail` payload.

### Units of measurement

- Class: `MijnTedUnitOfMeasuresSensor`
- Unique ID: `mijnted_<configEntryId>_unit_of_measures`
- Name: `<configured device name> Units of measurement`
- Category: `diagnostic`
- Purpose: localized description of the first unit entry returned by API.
- Device class: `enum`; no measurement unit or automatic statistics.
- Value source: first element of `unit_of_measures`. Known identifier `eenheid`
  and known labels `Units`, `Eenheden`, and `Einheiten` resolve to the stable raw
  state `units`. HA displays **Units** (English), **Eenheden** (Dutch), or
  **Einheiten** (German) using the interface language, with English fallback.
- Unrecognized descriptions and symbols such as `m3`, `m³`, and `kWh` are
  displayed verbatim. The integration does not guess their meaning or change
  spelling/capitalization. Actual usage-sensor and recorder units remain unchanged.
- Missing data behavior: returns last known value.
- Attributes:
  - `unit_of_measures`: raw list payload (if list)
- Compatibility: entity/unique IDs and stored history remain intact. Templates
  or automations comparing this diagnostic sensor's state to `Eenheden`,
  `Einheiten`, or `Units` must now compare it to `units`. Existing historical
  states retain their original text; the raw API descriptions remain available
  in the `unit_of_measures` attribute. Unknown descriptions retain their raw states.

### Latest available insight

- Class: `MijnTedLatestAvailableInsightSensor`
- Unique ID: `mijnted_<configEntryId>_latest_available_insight`
- Name: `<configured device name> Latest available insight`
- Category: `diagnostic`
- Purpose: latest month with usable insight data.
- State format: `MonthName YYYY` (for example `January 2026`).
- Value search order:
  - Latest month with non-null average in `energy_usage_data`
  - Compare against `usage_last_year` and keep the newer month
  - Fallback to `monthly_history_cache` month with non-null `average_usage`
- Missing data behavior: returns `None`.
- Attributes:
  - `statistics` (tracking structure, when available)
  - `month_id`
  - `has_average`
  - `usage_unit`

The state can fall back to previous-year/cache sources, but these insight
attributes are derived from current-year `energy_usage_data`. They can therefore
be absent or refer to a different month than the fallback state.

## Dynamic Device Sensors

- Class: `MijnTedDeviceSensor`
- Unique ID pattern:
  - `mijnted_<configEntryId>_device_<deviceNumber>`
  - Room metadata is excluded so renaming a room cannot change entity identity.
- Name pattern:
  - With room: `<configured device name> Device <translated room>`
  - Without room: `<configured device name> Device <deviceNumber>`
- Unit:
  - `"Einheiten"` and `"Eenheden"` are normalized to `Units`
  - Other unit strings are passed through as-is
- Purpose: current reading per device (`currentReadingValue`).
- Attributes:
  - `room`
  - `device_id`
  - `measurement_device_id`

Device sensor creation behavior:

- Created during `async_setup_entry` based on current `filter_status`.
- One sensor per unique `deviceNumber`.
- If new devices appear later, entities are not auto-created until integration reload.
- If a known device disappears from API response, state falls back to last known value.

## Water Sensors

Every additional delivery type returned by `address/deliveryTypes` is fetched
each refresh and stored in `coordinator.data["extra_delivery_data"]`, keyed by
delivery type ID. Water discovery also uses the primary delivery type's
already-fetched payload, so water-only accounts and accounts with water listed
first are supported without duplicate API requests. Delivery types that report
`m³` (device `unitOfMeasure` or `unitOfMeasures`) get water sensors; other types
are ignored. Primary entities follow their documented source and unit contracts.
A delivery type that fails to load never affects the heat sensors: failed
endpoints become empty defaults, and a type
whose whole fetch fails is skipped for that refresh. Water entities are created
from data available at setup and discovered again after successful coordinator
refreshes. If a fetch fails at startup, the missing entities are added once
their data becomes available; no integration reload is needed. New meters are
also added automatically. Known delivery-type/device-number pairs are retained
across partial failures and room changes, preventing replacement or duplicate
entities. The discovery listener is removed when the config entry unloads.

Names use the active model (`WWZF*` = warm, `KWZF*` = cold) and fall back to the
delivery type ID (`2` = warm, `3` = cold, as observed). With neither, the
generic name `Water meter <deviceNumber>` is used.
Water sensors are never persisted in the monthly cache and have no recorder
injection. A monthly water usage sensor is not provided yet.

### Water meter

- Class: `MijnTedWaterMeterSensor`
- Unique ID: `mijnted_<configEntryId>_water_<deliveryType>_device_<deviceNumber>`
- Name: `<configured device name> <Warm|Cold> water meter <translated room>`
  (without room: `... water meter <deviceNumber>`)
- Source: `currentReadingValue` of the device in that delivery type's `deviceStatuses`.
- Unit/classes: `m³`, device class `water`, state class `total_increasing`, so it
  can be used directly in the Energy dashboard's water consumption.
- Attributes: `delivery_type`, `room`, `device_id`, `measurement_device_id`.
- Created at setup and after successful refreshes, one per unique delivery type
  and `deviceNumber`; new devices do not need a reload.
  If the device disappears from the API response, the last known reading is kept.
  A reading of `0` (or below) is treated as missing data, never as a new value:
  a `total_increasing` sensor would otherwise record a meter reset and later add
  the whole counter to the Energy statistics. Unknown until the first valid reading.

## Edge Cases and Expected Behavior

| Edge case | Expected behavior |
|---|---|
| Full refresh fails (`UpdateFailed`) | All sensors become unavailable (`available = false`) until next successful refresh. |
| Connection error with valid token and cached coordinator data | Coordinator returns cached data; sensors keep previous values and stay available. |
| Partial API failure inside `asyncio.gather` | Failed endpoints are replaced with empty defaults (`{}` or `[]`). Sensors react per type (fallback to cache, `None`, or unchanged). |
| `filter_status` becomes empty due timeout/maintenance | Current-month usage keeps a same-month last-known/cache value; API-behind calendar projection is zero. Total/device sensors keep last known values; dynamic entities are not removed. |
| Non-empty `filter_status` temporarily omits devices | Calendar-month usage merges cached readings; the reading-date report and canonical graph keep the last complete snapshot and its original date. |
| Newly observed device without a known month-start reading | Its first observed reading becomes the usage baseline outside January; January uses the annual zero baseline. |
| `unit_of_measures` endpoint fails/returns empty | `unit_of_measures` sensor keeps last known state. |
| `delivery_types` empty | `delivery type` sensor returns `None`. |
| Water delivery type fails to load | Heat sensors are unaffected; existing water sensors keep their last known value (or stay unknown). Missing water entities are added automatically on a later successful refresh with their data. |
| API last sync date cannot be parsed | Sensors that require parsed date from `_build_current_data` cannot recompute current period and use fallback behavior. |
| Start of a month while API still reports previous month (`api_behind`) | Current period uses current calendar month key, `days = 0`, `end_date = start_date`, and monthly usage resolves to 0 or fallback to last known if source data is empty. |
| January month rollover | Usage calculations use end totals directly (no subtraction from previous year baseline). |
| Current total is 0 or non-positive | `calculate_filter_status_total` treats it as unavailable (`None`), so `total_usage` and related calculations fall back to last known or unknown state. |
| First run with no historical finalized month averages | `average monthly usage` can be `None` until data is available. |
| Last-year cache entry missing | Last-year sensors return last known value; if no prior value exists, state is unknown (`None`). |

## Month Switch Behavior (Detailed)

Detailed month-switch rules and examples are documented in [MONTH_SWITCH.md](./MONTH_SWITCH.md).

Summary:

- Current month is always calendar-based.
- Previous month moves to history on month switch.
- When API data is behind the new month, current month usage remains zero (`days = 0`, `start == end`).
- When API enters the new month, normal usage/day/average accumulation starts.
- Previous-month `COMPLETE_READINGS` transition locks current-month start values for continuity.
- Published totals and compatible corrected anchors can reconcile an already
  locked boundary and repair the following baseline. `FINALIZED` means published,
  not immutable. Pending repair and bounded retry state survive restarts.

## Statistics Injection Behavior

Usage sensors inject historical statistics into Home Assistant recorder when possible.
These are long-term statistics imports, not reconstructed ordinary state-history
rows. Use statistics-capable graphs to view the imported periods.

- Injecting sensors:
  - `monthly_usage`
  - `published_usage` (all four monthly reporting series and observed daily data)
  - `last_year_monthly_usage`
  - `average_monthly_usage`
  - `last_year_average_monthly_usage`
  - `total_usage`
- Preconditions:
  - Entity has `entity_id`
  - `hass` is available
  - Recorder integration is loaded
- `monthly_usage` and `last_year_monthly_usage` import into separate external
  `mijnted:<entry_id>_monthly_usage` and
  `mijnted:<entry_id>_last_year_monthly_usage` series. They upsert one arithmetic
  mean sample per HA-local consumption month, carrying the monthly aggregate.
  No automatic collection writes into these IDs. The current own-usage month is
  included when its complete dated report is available, including a true zero; last-year
  comparison months are shifted forward one year and future targets are excluded.
- Cached historical values are upserted on refresh, including corrections to
  retained periods.
- Monthly usage and Last year monthly usage also import historical entity-based
  state statistics. These series include live observations and imported monthly
  states. The separate external mean series provide consumption-period reporting.
- `total_usage` injection:
  - Uses monthly `total_usage_end` states and updates `sum` cumulatively
- `average_monthly_usage` and `last_year_average_monthly_usage` injection:
  - API history backfills separate monthly mean series; cached periods are reimported on refresh to include late values and corrections.
  - The current month is excluded from the average series; the last-year comparison shifts periods forward one year and excludes future comparison months.
- Reset path:
  - The reset button clears persisted monthly cache and in-memory `statistics_tracking`, then triggers refresh
  - It does not delete existing recorder history/statistics or clear each sensor's in-memory last-known state
  - Forward-only daily tracking uses separate storage and is retained; the reset
    does not trigger a daily historical scan.

### Monthly Usage and Building-Average Graphs

In a Statistics graph card, select all four monthly statistics from source
**mijnted** and choose **Month + Mean** (`stat_types: [mean]`). IDs are available
in the corresponding usage/average entity's `monthly_statistic_id` attribute.
The own-usage statistic is named **Published usage** in the selector. Monthly
usage's entity-based state statistic is separately selectable.
For a card combining entity-based state statistics with report mean statistics,
request both types (`stat_types: [state, mean]`). A card containing only the four
external monthly reporting series uses `stat_types: [mean]`.
Each sample carries one monthly aggregate; it is not an average of live states.
Published usage exports the four canonical monthly series and the daily series.
Those imports operate independently of the enabled state of standalone
average/comparison entities. Enable each standalone view needed by an entity card.

**Attributes are not required for graph selection.** In a Statistics graph,
select the statistic entries from source **mijnted**, or use their IDs in YAML.
Ordinary entity cards select the standalone sensor views.

Example four-line graph (replace `<entry_id>` with the lowercase entry ID from
the report's statistic attributes):

```yaml
type: statistics-graph
title: MijnTed
days_to_show: 120
period: month
chart_type: line
stat_types:
  - mean
entities:
  - mijnted:<entry_id>_monthly_usage
  - mijnted:<entry_id>_average_monthly_usage
  - mijnted:<entry_id>_last_year_monthly_usage
  - mijnted:<entry_id>_last_year_average_monthly_usage
```

For the forward-only daily graph, select
`mijnted:<entry_id>_reported_daily_usage` with **Day + Mean**. Daily and monthly
graphs use different statistic IDs; adding daily observations does not mix them
into the monthly report.

Historical API/cache values backfill the retained 16 historical months, plus the
current provisional month. Pending historical boundaries are reconciled during
refresh. Recorder periods outside the retained window remain stored; the cache
does not reconstruct those periods.

## Related Button

- Button: `<configured device name> Reset statistics` (`mijnted_<configEntryId>_reset_statistics`)
- Purpose: clear monthly cache and statistics tracking so recorder history can be re-injected from scratch on next refresh.

Entity IDs shown in examples are defaults; use the actual entity ID from your
Home Assistant entity registry if it has been renamed.
