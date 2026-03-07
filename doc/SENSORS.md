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

## Sensor Catalog

## Usage Sensors

### Monthly usage

- Class: `MijnTedMonthlyUsageSensor`
- Unique ID: `mijnted_monthly_usage`
- Name: `MijnTed monthly usage`
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

### Last year monthly usage

- Class: `MijnTedLastYearMonthlyUsageSensor`
- Unique ID: `mijnted_last_year_monthly_usage`
- Name: `MijnTed last year monthly usage`
- Unit: `Units`
- State class: `TOTAL`
- Purpose: usage for the same month in the previous year.
- Value source: previous-year same-month entry in `monthly_history_cache` (`total_usage`).
- Missing data behavior: returns last known value.
- Attributes:
  - `month_id` (current month key)
  - `last_year_month_id`

### Average monthly usage

- Class: `MijnTedAverageMonthlyUsageSensor`
- Unique ID: `mijnted_average_monthly_usage`
- Name: `MijnTed average monthly usage`
- Unit: `Units`
- State class: `TOTAL`
- Purpose: latest available historical monthly average.
- Value source: newest history entry with non-null `average_usage`.
- Missing data behavior: returns `None` (no last-known fallback in this sensor).
- Attributes:
  - `month_id` (of the history entry used for the value)

### Last year average monthly usage

- Class: `MijnTedLastYearAverageMonthlyUsageSensor`
- Unique ID: `mijnted_last_year_average_monthly_usage`
- Name: `MijnTed last year average monthly usage`
- Unit: `Units`
- State class: `TOTAL`
- Purpose: average usage for the same month in the previous year.
- Value source: previous-year same-month entry in `monthly_history_cache` (`average_usage`).
- Missing data behavior: returns last known value.
- Attributes:
  - `month_id` (current month key)
  - `last_year_month_id`

### Total usage

- Class: `MijnTedTotalUsageSensor`
- Unique ID: `mijnted_total_usage`
- Name: `MijnTed total usage`
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

## Diagnostic Sensors

### Last update

- Class: `MijnTedLastUpdateSensor`
- Unique ID: `mijnted_last_update`
- Name: `MijnTed last update`
- Device class: `timestamp`
- Category: `diagnostic`
- Purpose: date for which device readings are currently available (often 1-2 days behind calendar date), converted to ISO timestamp at midnight UTC.
- Accepted source formats: `DD/MM/YYYY`, `YYYY-MM-DD`, or ISO-like strings.
- Missing/invalid source behavior: returns `None`.

### Last successful sync

- Class: `MijnTedLastSuccessfulSyncSensor`
- Unique ID: `mijnted_last_successful_sync`
- Name: `MijnTed last successful sync`
- Device class: `timestamp`
- Category: `diagnostic`
- Purpose: calendar timestamp of the most recent successful synchronization with the API (integration refresh success moment).
- Note: this is sync time, not the "readings available until" date.

### Active model

- Class: `MijnTedActiveModelSensor`
- Unique ID: `mijnted_active_model`
- Name: `MijnTed active model`
- Category: `diagnostic`
- Purpose: active model identifier.
- Missing data behavior: returns `None`.

### Delivery type

- Class: `MijnTedDeliveryTypesSensor`
- Unique ID: `mijnted_delivery_types`
- Name: `MijnTed delivery type`
- Category: `diagnostic`
- Purpose: comma-separated delivery types.
- Missing/empty behavior: returns `None`.

### Residential unit

- Class: `MijnTedResidentialUnitDetailSensor`
- Unique ID: `mijnted_residential_unit_detail`
- Name: `MijnTed residential unit`
- Category: `diagnostic`
- Purpose: residential unit identifier plus full detail attributes.
- State: `residential_unit`
- Attributes: `residential_unit_detail` payload.

### Unit of measures

- Class: `MijnTedUnitOfMeasuresSensor`
- Unique ID: `mijnted_unit_of_measures`
- Name: `MijnTed unit of measures`
- Category: `diagnostic`
- Purpose: display name of the first unit entry returned by API.
- Value source: first element of `unit_of_measures` list, field `displayName`.
- Missing data behavior: returns last known value.
- Attributes:
  - `unit_of_measures`: raw list payload (if list)

### Latest available insight

- Class: `MijnTedLatestAvailableInsightSensor`
- Unique ID: `mijnted_latest_available_insight`
- Name: `MijnTed latest available insight`
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

## Dynamic Device Sensors

- Class: `MijnTedDeviceSensor`
- Unique ID pattern:
  - With room code: `mijnted_device_<sanitized_room>_<deviceNumber>`
  - Without room code: `mijnted_device_<deviceNumber>`
- Name pattern:
  - With room: `MijnTed device <translated room>`
  - Without room: `MijnTed device <deviceNumber>`
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

## Edge Cases and Expected Behavior

| Edge case | Expected behavior |
|---|---|
| Full refresh fails (`UpdateFailed`) | All sensors become unavailable (`available = false`) until next successful refresh. |
| Connection error with valid token and cached coordinator data | Coordinator returns cached data; sensors keep previous values and stay available. |
| Partial API failure inside `asyncio.gather` | Failed endpoints are replaced with empty defaults (`{}` or `[]`). Sensors react per type (fallback to cache, `None`, or unchanged). |
| `filter_status` becomes empty due timeout/maintenance | `monthly_usage`, `total_usage`, and device sensors return last known values if available; dynamic device entities are not removed. |
| `unit_of_measures` endpoint fails/returns empty | `unit_of_measures` sensor keeps last known state. |
| `delivery_types` empty | `delivery type` sensor returns `None`. |
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
- Previous-month finalization closes/finalizes that month but does not shift already-locked current-month starts.

## Statistics Injection Behavior

Usage sensors inject historical statistics into Home Assistant recorder when possible.

- Injecting sensors:
  - `monthly_usage`
  - `last_year_monthly_usage`
  - `average_monthly_usage`
  - `last_year_average_monthly_usage`
  - `total_usage`
- Preconditions:
  - Entity has `entity_id`
  - `hass` is available
  - Recorder integration is loaded
- Duplicate protection:
  - `statistics_tracking` stores the last injected month key per sensor type
  - When a historical month value is corrected later (for example previous month final-day data arrives after month switch), a one-time reinjection hint allows that corrected month to be imported even if it is older than `last_injected`
- `total_usage` injection:
  - Uses monthly `total_usage_end` states and updates `sum` cumulatively
- `average_monthly_usage` and `last_year_average_monthly_usage` injection:
  - Imports one monthly state value per period (state-only statistics, no mean/sum aggregation)
  - In Statistics UI, use the state view for these two entities
- Reset path:
  - The reset button clears persisted cache and `statistics_tracking`, then triggers refresh

## Related Button

- Button: `MijnTed reset statistics` (`mijnted_reset_statistics`)
- Purpose: clear monthly cache and statistics tracking so recorder history can be re-injected from scratch on next refresh.
