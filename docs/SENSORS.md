# Sensors Reference

Current entity values, names, attributes, availability, and graph configuration.
Domain: `mijnted`; platforms: `sensor` and `button`. Implementation locations are
in the [layout guide](../.github/instructions/layout.instructions.md).

## How Sensor Values Are Produced

Entities share coordinator availability: a failed refresh makes them unavailable;
a successful partial response can leave individual values stale or unknown.
Last-known live values are in-memory. Persistence of reports and caches is
described in the [reporting architecture](USAGE_REPORTING.md).

HA manages entity IDs. Unique IDs use `mijnted_<configEntryId>_<entityKey>` so
installations remain independent. Example entity IDs are defaults; use your
registry's actual IDs in templates and dashboards.

## Sensor Catalog

### Language and display names

English, Dutch, and German are supported. This catalog uses English defaults.
Forms and supported frontend state/attribute labels follow the interface language.
Default entity names use the server language at setup and the configured device
name as their prefix. Reload MijnTed or restart HA after changing the server
language. Entity IDs, history, and user-assigned names remain stable.

Known room codes `KA` and `W` provide translated bedroom/living-room context.
Unknown codes and arbitrary room names remain verbatim; a missing room uses the
device number. Room-context updates affect default names only.

All five external reporting-statistic names use the server language. Setup updates
existing name metadata even without new samples; recorder failures defer the
rename until a successful refresh without blocking sensor creation. The calendar
**Monthly usage** entity and **Published usage** reporting series have distinct
meanings. Dashboard/card labels remain user-owned.

Technical/model/API codes, raw room attributes, and nested diagnostic payloads
remain raw. HA translates supported top-level attribute labels, not arbitrary
nested JSON. Canonical measurement units are `Units` and `m³`. The
[unit diagnostic](#units-of-measurement) has translated textual states; the
[insight diagnostic](#latest-available-insight) uses process-locale month text.

#### Duplicate device names

Matching room context and label type receive suffixes such as **Device living
room 1** and **Device living room 2**. Singletons stay unsuffixed. Assignments are
per installation and independent of language; warm, cold, and generic water labels
form separate groups, including across delivery types.

The first batch follows natural device-number order; later arrivals append.
Reservations survive restarts, missing readings, and monthly resets. Once a group
is numbered, absent peers do not remove suffixes or free slots. Room moves use the
destination's reservations; returning meters recover their earlier slots there.
Absent devices retain known naming context. Custom names and raw room attributes
are unaffected.

## Usage Sensors

Usage values use `Units` and request zero displayed decimal places without
rounding stored values. Each view identifies its own reporting period.

### Monthly usage

Calendar-month progress; state class `total`. Normally calculated as
`total_usage_end - total_usage_start`, or `total_usage_end` in January. Missing
readings use the same-month cached/last-known value where available.

A local callback resets the projection to zero at HA-local month start,
independently of polling. Corrected boundaries can lower provisional usage.
See [month transitions](MONTH_SWITCH.md) for baseline and API-lag rules.

Attributes: `month_id` (`M.YYYY`), `start_date`, `end_date` (`YYYY-MM-DD`), `days`
(inclusive), and `monthly_statistic_id`.

### Published usage

Own usage for the latest complete received reading month. It uses that dated
observation and its opening baseline, with a valid official total taking precedence
on the month's final day. “Published” means available from MijnTed, not immutable.
The first value in a month can be zero or nonzero; this view has no calendar reset
or automatic state-class statistics.

Unknown until a usable observation/baseline exists. Partial responses retain the
last complete report and its date; restart restores the checkpoint. Entity history
records receipt time, while external statistics identify consumption periods.

Attributes:
- Own period: `month_id`, `reading_date`, `start_date`, `end_date`.
- Provenance: `value_source` (`reported` or `published`), `start_locked`,
  `boundary_reconciled`. For a completed month, an unreconciled boundary can remain
  pending while the published total is usable; an open month has no closing boundary.
- Graphs: `monthly_statistic_id` and `daily_statistic_id`.
- Computable daily result: `reported_daily_usage` and `reported_daily_date`.

The report exports all four monthly series and the daily series independently of
enabled standalone average/comparison views. Each standalone view exposes its own
`monthly_statistic_id`; all series are selectable from source **mijnted**.

### Reported daily usage (report attributes and statistics)

A daily result requires consecutive compatible received reading dates; the first
observation seeds a checkpoint. January 1 uses the annual zero baseline. Gaps,
invalid readings, and changed device sets remain unallocated. Repeated latest-date
observations can correct that day's value; earlier dates are not actively revisited.

Daily attributes belong to Published usage, with their own date, and appear only
after a result is computable. They persist across reloads/restarts, including through
gaps. There is no separate daily entity or historical daily scan. Use
[Day + Mean](#monthly-usage-and-building-average-graphs), not a monthly average of
daily totals, for the daily graph.

### Last year monthly usage

Usage from the same calendar month in the previous year's cache (`total_usage`);
state class `total`. Lookup is independent of current meter availability. A
last-known value is retained only within that comparison period; otherwise unknown.

Attributes: `month_id` (current comparison month), `last_year_month_id`,
`monthly_statistic_id`.

### Average monthly usage

Newest historical month with a non-null `average_usage`. Unknown if none exists;
no last-known fallback or automatic state-class statistics.

Attributes: `month_id` (the selected average's month), `monthly_statistic_id`.

### Last year average monthly usage

Average from the same calendar month in the previous year's cache (`average_usage`).
Lookup and last-known fallback follow the
[comparison-period contract](#last-year-monthly-usage). No automatic state-class
statistics.

Attributes: `month_id`, `last_year_month_id`, `monthly_statistic_id`.

### Total usage

Sum of current device meter readings (`currentReadingValue`); state class
`total_increasing`. Missing/non-positive aggregate data retains the last known value.

Attributes `current` and `history` expose the current calendar month and historical
months. Each month payload has:

| Fields | Meaning |
|---|---|
| `month_id`, `year`, `month`, `start_date`, `end_date`, `days` | Period identity and boundaries |
| `total_usage`, `total_usage_start`, `total_usage_end`, `average_usage`, `average_usage_per_day` | Consumption/readings and averages |
| `devices` | Per-device `id`, `start`, `end`, and `usage` |
| `status`, `published_usage`, `value_source`, `boundary_reconciled` | Lifecycle and provenance; source is `published` or `readings` |

Lifecycle states are defined in [month lifecycle](MONTH_SWITCH.md#month-lifecycle-state).

## Diagnostic Sensors

All entries below use HA's diagnostic category.

### Last update

The API's readings-available date, often behind the calendar, converted to midnight
UTC; device class `timestamp`. Accepts `DD/MM/YYYY`, `YYYY-MM-DD`, and supported
ISO-like source strings. Missing/invalid dates are unknown.

### Last successful sync

Timestamp of the latest returned refresh payload, not its readings-available date.
Partial endpoint failures can still advance it. Returning cached coordinator data
after a connection error retains the cached timestamp.

### Active model

Raw active model identifier; unknown when absent.

### Delivery type

Comma-separated API delivery-type IDs; unknown for empty/missing data.

### Residential unit

State: `residential_unit`. Attributes contain the raw `residential_unit_detail`
payload.

### Units of measurement

An enum diagnostic describing the first API unit. Known identifier `eenheid` and
labels `Units`, `Eenheden`, and `Einheiten` resolve to raw state `units`, displayed
as **Units**, **Eenheden**, or **Einheiten** by interface language. Templates compare
the raw state to `units`.

Unknown descriptions/symbols such as `m3`, `m³`, and `kWh` pass through verbatim.
Missing data retains the last known state. Attribute `unit_of_measures` holds the
raw API list. This diagnostic has no measurement unit or automatic statistics.

### Latest available insight

Latest month with a non-null average: compare `energy_usage_data` and
`usage_last_year`, then fall back to `monthly_history_cache`. Unknown if unavailable.
State is `MonthName YYYY`, using the Python process locale rather than the HA
interface language; HA state translations cannot format this dynamic month/year.

Attributes: `statistics` (tracking), `month_id`, `has_average`, `usage_unit`.
Insight attributes derive from current-year energy data, so they can be absent or
identify a different month than a fallback state.

## Dynamic Device Sensors

One sensor per primary `deviceNumber`, created at setup. Additional primary
devices require an integration reload. Unique ID:
`mijnted_<configEntryId>_device_<deviceNumber>`; room metadata does not affect identity.

- Value: `currentReadingValue`, with last-known fallback when the device is absent.
- Name: `Device <translated room>` or `Device <deviceNumber>`; apply
  [duplicate numbering](#duplicate-device-names) where needed.
- Unit: `Einheiten`/`Eenheden` normalize to `Units`; other units pass through.
- Attributes: `room`, `device_id`, `measurement_device_id`.

## Water Sensors

Deliveries reporting `m³` receive water sensors. Discovery includes the primary
payload and additional delivery types, adding unseen delivery/device pairs after
successful refreshes. Missing startup responses can recover without reload.
A failed water delivery leaves the heat sensors and other deliveries unaffected.

### Water meter

Unique ID: `mijnted_<configEntryId>_water_<deliveryType>_device_<deviceNumber>`.
Value: the delivery's `currentReadingValue`, in `m³`; device class `water`, state
class `total_increasing`, suitable for the Energy dashboard.

Names use `WWZF*`/`KWZF*` models for warm/cold water, falling back to observed
delivery IDs `2`/`3`. Unknown kinds use `Water meter`. Room/number context and
[duplicate suffixes](#duplicate-device-names) follow the shared naming policy.
Missing model metadata retains a known kind; an explicitly unknown model uses the
generic label.

Unknown until a valid positive reading exists. Absent or non-positive readings
retain the last known value, preventing false meter resets. Attributes:
`delivery_type`, `room`, `device_id`, `measurement_device_id`.

Water sensors use HA's ordinary state-class statistics, not integration recorder
injection or the monthly cache. A separate monthly water-usage sensor is not provided.

## Edge Cases and Expected Behavior

| Condition | Shared behavior |
|---|---|
| Failed coordinator refresh | Sensors become unavailable until recovery. |
| Connection error with valid token and cached data | Cached values/availability are retained. |
| Successful partial response | Sensor-specific fallback contracts above apply; successful sync time does not guarantee every endpoint succeeded. |
| Unreadable name reservations | New numbering waits for restoration; measurements continue. Unsaved assignments retry on refresh. |

## Month Switch Behavior (Detailed)

[Month transitions](MONTH_SWITCH.md) own calendar/API lag, January resets,
lifecycle states, anchor repair, and the worked boundary timeline.

## Statistics Injection Behavior

Canonical external reporting series contain period-aligned arithmetic means:

| Statistic ID suffix after `mijnted:<entry_id>_` | Quantity | Graph |
|---|---|---|
| `monthly_usage` | Own consumption; selector label **Published usage** | Month + Mean |
| `average_monthly_usage` | Building average | Month + Mean |
| `last_year_monthly_usage` | Previous-year own consumption | Month + Mean |
| `last_year_average_monthly_usage` | Previous-year building average | Month + Mean |
| `reported_daily_usage` | Observed daily consumption | Day + Mean |

Each mean sample carries one consumption total/average for its period, not an
average of live entity states. Own usage includes the current month when a dated
report exists, including actual zero. The current-year building-average series
excludes its current month.
Last-year series shift source periods forward one year and exclude future targets.
Refresh upserts cached periods, including corrections.

Monthly usage and Last year monthly usage also import entity-based state
statistics alongside live collection. Total usage imports month-end readings with
a cumulative `sum`. These entity-based series are separate from the external
reporting series. Recorder must be enabled for imports.

The [retained cache window](USAGE_REPORTING.md#monthly-cache-and-boundary-reconciliation)
limits backfill. Recorder data outside that window remains stored but is not
reconstructed by the cache.

### Monthly Usage and Building-Average Graphs

Select the four monthly statistics from source **mijnted** with **Month + Mean**.
Each usage/average view exposes its `monthly_statistic_id`; Published usage also
exposes `daily_statistic_id`. Attributes are convenient lookup aids, not a
requirement for selecting statistics. Standalone views must be enabled for entity
cards; external reporting imports operate independently of them.

Replace `<entry_id>` with the lowercase entry ID from the statistic attributes:

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

A card mixing entity-state and external-mean series requests
`stat_types: [state, mean]`. For the separate daily series use
`mijnted:<entry_id>_reported_daily_usage` with **Day + Mean**.

## Related Button

**Reset statistics** rebuilds persisted monthly cache/injection tracking and
requests a refresh. It preserves recorder history/statistics, live last-known
values, daily checkpoints, and device-name reservations. It does not scan historical
daily endpoints. Example ID: `button.mijnted_reset_statistics`.
