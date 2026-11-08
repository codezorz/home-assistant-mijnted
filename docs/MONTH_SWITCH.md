# Month Switch Behavior

Current calendar/API boundary rules. [SENSORS.md](SENSORS.md) owns per-entity
values and availability; [reporting architecture](USAGE_REPORTING.md) owns storage
and data flow.

## Terminology

- **Calendar date:** HA-local date.
- **Last update:** API readings-available date, often behind the calendar.
- **Last successful sync:** time of a returned refresh payload; a partial response
  can still advance it.

## Month Identity

Cache keys use `YYYY-MM`; API/display month IDs use `M.YYYY`. The current cache
month follows the calendar. On rollover the completed calendar month enters history.

## Invariants

- Monthly usage resets to zero at HA-local month start independently of polling,
  and remains zero while available readings belong to the preceding month.
- Published usage follows the latest complete reading month, without a synthetic
  calendar reset. Its first available new-month value can be zero or nonzero.
- The live Total usage counter follows API readings; a calendar change alone does
  not reset it. January calculations use the annual zero baseline.
- Opening readings align with compatible preceding-month closing readings.
  Corrections remain possible after publication and can lower provisional usage.
- Entity history records receipt time. External statistics identify reporting
  periods; date-only API data does not imply a midnight/end-of-day observation.

## Month Lifecycle State

| State | Meaning |
|---|---|
| `OPEN` | In progress or incomplete boundary |
| `COMPLETE_READINGS` | Month's final-day readings available; revisable |
| `FINALIZED` | Published own total and usable building average; revisable |

A finite nonnegative own total plus a usable non-null building average identifies
publication. Zero with a null average is an unpublished placeholder; valid
published zero is retained.

### Boundary reconciliation

- Prefer the preceding month's final-day API anchor to establish the opening
  readings. Empty/incompatible anchors may seed a cached temporary baseline but
  leave it unlocked for correction.
- Anchors containing all cached devices can repair incomplete history. Recover
  missing starts from the preceding cache/anchor and keep verification pending
  if required starts remain unavailable.
- `start_locked` protects an accepted baseline from incomplete responses, not
  verified corrections. Validate opening and closing anchors together; refresh an
  inconsistent opening baseline while repair is pending.
- Accept published revisions throughout retained history, reopening verification
  when needed. Use compatible per-device evidence, never allocate an aggregate
  difference across fabricated readings. January keeps its annual zero baseline.
- `boundary_reconciled` marks verified historical boundaries. Pending work and
  one-to-six-hour retry backoff survive restart.

## Month Switch Timeline

Illustrative October-to-November reading sequence:

| Event | Monthly usage | Published usage / cache |
|---|---|---|
| November 1 calendar boundary; readings cover October 30 | November zero | October report; October cache is history |
| October 31 readings arrive | Still November zero | October closing readings become available; establish/lock a compatible November baseline |
| November 1 readings arrive | November consumption | Switch to November's actual available value; `days = 1` |
| October publication becomes available | Keep the evidence-based November baseline | Enrich/finalize October and upsert its reporting bucket |
| A verified October boundary is corrected | Recalculate provisional November consumption | Repair both historical boundary and adjacent opening readings |

During calendar/API lag, current-month per-device `start == end`, `days = 0`, and
average per day is zero. Once readings enter the month, consumption uses the
opening baseline and available end readings.

For example, correcting a closing counter from 100 to 104 makes the next month's
opening counter 104. With a latest counter of 110, next-month usage is 6. A
published monthly total can be usable before anchor repair completes; its report
retains the matching month/date. Separate [daily reporting](SENSORS.md#reported-daily-usage-report-attributes-and-statistics)
uses consecutive compatible observed dates rather than spreading gaps.

## Quick Checks for Validation

Exercise local rollover/API lag, January reset, valid zero/nonzero first readings,
publication/anchor arrival in both orders, corrected locked boundaries, and restart
with pending repair. Use [development verification](DEVELOPMENT.md#home-assistant-smoke-test)
for execution and report the dates/periods exercised.

## Manual Recovery

Use [Reset statistics](SENSORS.md#related-button) to rebuild monthly cache/tracking
when investigating stale boundaries. That section owns what the action preserves.
