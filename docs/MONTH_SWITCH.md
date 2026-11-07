# Month Switch Behavior

This document defines expected behavior when calendar month boundaries and API data availability are not aligned.

## Terminology

- `calendar date`: current local date in Home Assistant.
- `last successful sync` sensor:
  - calendar timestamp of the integration's successful API refresh.
  - entity: `sensor.mijnted_last_successful_sync`.
- `last update` sensor:
  - date for which device readings are available from MijnTed API.
  - usually 1-2 days behind the calendar date.
  - entity: `sensor.mijnted_last_update`.

## Month Identity

- Cache month key format: `YYYY-MM` (for example `2026-03`).
- Sensor month id format: `M.YYYY` (for example `3.2026`).

## Sensor Expectations

- `Total usage`:
  - cumulative, total-increasing in `Units`.
  - follows API meter readings; annual resets are handled in usage/statistics calculations. A calendar change alone does not synthesize a reset of the live total while the API is behind.
  - attributes:
    - `current`: current calendar month data.
    - `history`: historical months (current month excluded).
- `Monthly usage`:
  - monthly total for current calendar month.
  - resets on first day of each calendar month.
  - increases during the month as new readings become available.

## Invariants

- Current month is always based on calendar month, not API month.
- Previous month is moved to history when calendar month changes.
- Current month start readings should align to previous month end readings when available.
- If API data is still in previous month, new current month usage must remain zero.

## Month Lifecycle State

Each month in cache has an explicit lifecycle state:

- `OPEN`: month is still in progress or boundary is not complete yet.
- `COMPLETE_READINGS`: month last-day readings are complete and stable.
- `FINALIZED`: month has insight average and is closed.

Boundary rule for the next month:

- When previous month reaches `COMPLETE_READINGS`, current month `start` readings are recalculated from previous-month `end` readings and marked as locked (`start_locked = true`).
- The integration prefers the previous month's last-day API anchor. Empty or incompatible anchor responses use the cached device set as a temporary baseline but leave it unlocked so a later complete anchor can correct it.
- An anchor that contains all cached devices can repair an incomplete historical cache. Missing month-start readings are restored from the preceding month's cache or last-day anchor; correction remains unlocked for retry if a required start is unavailable.
- `start_locked = true` protects an accepted baseline from incomplete responses. Verified closing anchors can reconcile that baseline when upstream values change.

## Month Switch Timeline

Example: month switch from February to March 2026.

### Phase A: Calendar switches, API still behind

State:

- Calendar date: `2026-03-01` (for example sync at 03:00).
- `last successful sync`: `2026-03-01T03:00:00Z` (example).
- `last update`: `2026-02-27`.

Expected behavior:

- New current month is March (`2026-03` / `3.2026`).
- February (`2026-02` / `2.2026`) is in history.
- March current start values are seeded from last known February end values.
- Because API is behind (`last_update < 2026-03-01`):
  - per-device `start == end`
  - `days = 0`
  - monthly usage = `0`
  - average per day = `0`

### Phase B: API catches up to the last day of previous month

State:

- `last update` becomes `2026-02-28`.

Expected behavior:

- February month is updated with final end readings.
- February transitions `OPEN -> COMPLETE_READINGS`.
- March start values are aligned to February end values and locked (`start_locked = true`).
- March usage remains zero while API date is still before `2026-03-01`.

### Phase C: API enters the new month

State:

- `last update` becomes `2026-03-01` (or later).

Expected behavior:

- Current month starts normal accumulation.
- `days` becomes `1` on `2026-03-01`.
- Per-device usage is computed as `end - start`.
- Monthly usage starts increasing.
- Average per day starts being calculated.

### Phase D: Previous month insight finalization

State:

- Latest available insight becomes February 2026.

Expected behavior:

- February cache entry receives average insight fields.
- February transitions `COMPLETE_READINGS -> FINALIZED`.
- February is marked as published and remains correctable.
- March remains `OPEN`. Its baseline follows verified per-device closing readings, including corrections to an accepted boundary.

## Quick Checks for Validation

- On `2026-03-01` with `last update = 2026-02-27`:
  - March current exists.
  - February is in history.
  - March usage is zero.
- When `last update` moves to `2026-03-01`:
  - `days = 1` for March.
  - usage becomes non-zero only if readings changed.
- After February insight finalization:
  - February averages are populated.
  - March start alignment remains consistent with February end.
- If February monthly totals are corrected after March already started, recorder statistics for February are re-injected once so history reflects the corrected value.

## Manual Recovery

- In rare edge cases where month-boundary cache values look stale or incorrect, use button `button.mijnted_reset_statistics` to rebuild cache/statistics from fresh data.
- This resets integration cache/injection tracking, not recorder data. See the [reset behavior](SENSORS.md#related-button). Entity IDs are examples; use your registry's actual ID.

## Published totals and pending boundaries

Yearly API data reconciles historical own totals and building averages. A finite
nonnegative own total and usable non-null building average identify a published
monthly result. Published zero is valid; zero with a null average is a placeholder.

The cache retains 16 historical months plus the current month. It persists
`published_usage`, `boundary_reconciled`, `boundary_retry_at`, and
`boundary_retry_count`. Provisional months and pending repairs survive restarts.
Pending boundaries use compatible real device anchors and bounded one-hour-to-six-hour
retry backoff. Verified closing readings repair the following opening baseline;
January retains its annual zero baseline. A revised published result reopens
verification of that boundary.
Opening and closing anchors are validated together; an inconsistent cached
opening baseline is refreshed from the preceding dated anchor while pending.
