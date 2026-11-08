# Usage reporting architecture

The integration exposes calendar progress, dated reading reports, and
consumption-period statistics from one coordinator. The
[sensor reference](SENSORS.md) defines entity values and metadata;
[month lifecycle](MONTH_SWITCH.md) defines boundary behavior; the
[API reference](ENDPOINTS.md) defines upstream sources.

## Reporting periods

| View | Period selection |
| --- | --- |
| Monthly usage | Current HA-local calendar month; zero at the month boundary while readings lag |
| Published usage | Month-to-date own usage for the latest complete received reading date |
| Average monthly usage | Latest historical month with an available building average |
| Last-year comparisons | Corresponding calendar month in the previous year |

"Published" in the report name means available from MijnTed. Available readings
and completed monthly results can receive corrections.

A November 1 reading received November 3 belongs to November 1. Published usage
advances to November when that reading is available and displays its actual
month-to-date amount, including a nonzero first value. Ordinary entity history
records receipt time; statistics timestamps identify reporting buckets. Date-only
responses do not establish a precise time-of-day observation.

Each sensor owns its value, reporting-period attributes, units, availability,
and statistic-ID attributes. Average/comparison views keep their own metadata;
the reading report's month is not assigned to another metric. Sensors read shared
coordinator data independently of other entities' enabled state.
Comparison lookups use their own month-keyed cache, independent of current meter
responses. Their last-known fallbacks are scoped to the comparison period.

## Coordinator data flow

1. `__init__.py` fetches and normalizes API responses, updates the monthly cache,
   and applies yearly publication data.
2. `reconciliation.py` validates pending historical closing anchors and repairs
   adjacent opening baselines from compatible per-device readings.
3. `daily.py` stores complete dated observations and derives forward daily
   consumption where consecutive compatible checkpoints are available.
4. `utils/readings.py` builds `reading_report` from the latest complete checkpoint
   and its month's opening baseline.
5. Entities project coordinator data; reporting helpers import period-aligned
   statistics.

`reading_report` contains the resolved value and its `month_id`, `reading_date`,
period boundaries, source kind, and boundary metadata. A partial newer-date
response leaves the most recent complete checkpoint and its reading date intact.
Month-to-date usage is available from the first complete observation when its
opening baseline is known. A final-day report uses an available official monthly
total for that period; otherwise it uses the dated meter difference.

## Monthly cache and boundary reconciliation

Monthly entries are keyed by `YYYY-MM`; display/API month IDs use `M.YYYY`.
The cache retains 16 historical months and the current month. Publication,
per-device readings, and boundary verification are separate facts:

- `published_usage` records a usable official own monthly total, including zero.
- `boundary_reconciled` identifies per-device boundaries verified against that
  result.
- `boundary_retry_at` and `boundary_retry_count` persist pending repair with
  bounded one-hour-to-six-hour retry backoff.
- `start_locked` protects an accepted opening baseline from incomplete responses.

A finite nonnegative historical own total and a usable non-null building average
form the monthly publication predicate. A zero total with no building average is
an unpublished placeholder. The API provides no immutable/final flag.

Refresh reconciles pending boundaries, including months marked `FINALIZED`.
A revised published total reopens verification. Closing-reading corrections
repair the following month's opening baseline using actual compatible devices;
aggregate differences are not allocated across fabricated device readings.
January uses the annual zero baseline.

Published monthly totals can be available while their per-device anchor repair
is pending. Useful readings and pending work are persisted, and corrected
baselines recalculate the dated reading report.

## Forward daily tracking

The entry-scoped daily store contains two complete dated checkpoints and up to
500 observed daily results. It survives monthly cache resets and adds no API
requests.

Storage restoration completes before observations are accepted. Pending writes
are retried on refresh, including polls with unchanged or unavailable API data.

The first complete observation seeds a checkpoint. A daily result requires
consecutive dates and compatible device sets. January 1 uses the annual zero
baseline. Gaps and incomplete responses remain unallocated; tracking continues
when compatible observations are available. Repeat observations of the latest
date can revise its daily result.

Daily results are reported observations without a monthly-style finality marker.
They begin with forward observations; historical daily endpoints are not scanned,
and past daily dates are not actively revisited. Daily attributes carry their own
date alongside the reading report's month-to-date value.

## Independently selectable statistics

Published usage exports four external monthly series and a daily series through
`sensors/base.py` and `sensors/daily.py`. The
[graph setup](SENSORS.md#monthly-usage-and-building-average-graphs) lists their IDs
and card configuration. Standalone average/comparison entities provide ordinary
entity-card selections; external graph imports operate independently of them.

Series labels follow the installation-language policy in
[language and display names](SENSORS.md#language-and-display-names). The canonical
series key determines the label, so the consolidated report and standalone views
cannot overwrite one series with different names. Reloading also updates existing
name metadata without needing a new reading or changing stored data.

- Monthly series contain one arithmetic-mean sample carrying an aggregate per
  HA-local consumption month. Last-year comparison periods are shifted forward
  one year; future target months are excluded.
- Current-month graph totals use the last complete dated report. A month receives
  its sample when readings for that month are available, including a true zero.
  Available totals upsert the same bucket. The calendar-zero projection belongs
  to Monthly usage and its entity-based statistics.
- Daily series contain one arithmetic-mean sample carrying daily consumption at
  the HA-local reading-date bucket.
- Imports upsert retained periods on refresh, including late corrections.
- Entity-based usage statistics include live observations and imported monthly
  states. Consumption-period reporting uses the external mean series.

Published usage has no automatic state-class statistics. The monthly graph uses
**Month + Mean**; the daily graph uses **Day + Mean**. These aggregate samples do
not represent additional midnight or end-of-day meter observations.

## Validation

Behavior tests exercise boundary corrections, adjacent baselines, source arrival
order, published zero, incomplete devices, restart persistence, and local month/
year transitions. Graph tests execute the pinned HA 2026.11.0 pure reducers under
`tests/fixtures/`, with upstream source and license provenance recorded there.

Dated-report tests cover delayed arrival, zero and nonzero first readings,
same-date revisions, partial newer-date responses, and distinct entity metadata.
Named-zone tests use the `tzdata` development dependency.

Use the [development guide](DEVELOPMENT.md) for validation commands and the HA
smoke procedure covering entity labels, lifecycle callbacks, statistics readback,
and dashboard cards.
