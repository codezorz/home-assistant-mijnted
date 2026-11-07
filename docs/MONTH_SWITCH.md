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
  - resets to zero at the HA-local start of each calendar month using a local
    callback, independently of hourly API polling. Availability still follows the
    coordinator; a full failure can make the sensor unavailable.
  - increases during the month as new readings become available.
- `Published usage`: a reading-month own-usage view. It stays on October while
  available readings still describe October, then switches to November's actual
  total when November readings arrive, even if the first value is nonzero. There
  is no synthetic midnight reset in this entity. Dated daily attributes and the separate daily series use forward observations,
  without a historical scan; see [daily reporting](SENSORS.md#reported-daily-usage-report-attributes-and-statistics).

## Invariants

- Current month is always based on calendar month, not API month.
- Previous month is moved to history when calendar month changes.
- Current month start readings should align to previous month end readings when available.
- If API data is still in previous month, new current month usage must remain zero.

## Month Lifecycle State

Each month in cache has an explicit lifecycle state:

- `OPEN`: month is still in progress or boundary is not complete yet.
- `COMPLETE_READINGS`: month last-day readings are available; later revisions
  remain possible until and after publication.
- `FINALIZED`: month has insight average and is closed.

Boundary rule for the next month:

- When previous month reaches `COMPLETE_READINGS`, current month `start` readings are recalculated from previous-month `end` readings and marked as locked (`start_locked = true`).
- The integration prefers the previous month's last-day API anchor. Empty or incompatible anchor responses use the cached device set as a temporary baseline but leave it unlocked so a later complete anchor can correct it.
- An anchor that contains all cached devices can repair an incomplete historical cache. Missing month-start readings are restored from the preceding month's cache or last-day anchor; correction remains unlocked for retry if a required start is unavailable.
- `start_locked = true` protects an accepted baseline from incomplete responses.
  Verified reconciliation can still replace it when late readings correct a
  historical boundary. Ordinary finalization alone does not invent a new baseline.
- `FINALIZED` identifies a published historical month, not an immutable cache row.
  A usable non-null building average plus a finite nonnegative own total is the
  current publication proxy; a zero with null average is an unpublished placeholder.
  A valid published zero is retained, and subsequent published revisions are accepted.
- Opening and closing anchors are validated together. An inconsistent opening
  baseline is refreshed from the preceding dated anchor while verification is
  pending, including months whose insight has not been published.

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
- February is marked as published.
- February's published own total and average are reconciled even if its cached
  state was already complete/finalized. It remains correctable after publication.
- March remains `OPEN`. Its baseline shifts only when compatible per-device
  boundary evidence supports a correction, not from distributing an aggregate
  difference across devices.

### Phase E: A previously accepted boundary is revised

If a cached October end of 868 later becomes 870, with September end 829:

- October's published usage becomes 41, even when the corrected anchor is not
  available yet. `boundary_reconciled` remains false until anchor repair succeeds.
- Compatible October-end readings repair November's start from 868 to 870. With
  latest readings totaling 888, November usage is 18.
- Pending repairs use persisted retry backoff (one hour, up to six hours after
  repeated failures). Provisional boundaries remain revisable before publication.
- Published totals are reconsidered throughout the retained history. A later
  revision reopens an already reconciled boundary. January retains its annual zero
  baseline when December is revised.
- External monthly statistics upsert October's 41 in October, independent of when
  HA receives it. If the latest received reading date is October 31, Published
  usage shows 41 with `month_id = 10.2026`; if it is November 6, the sensor shows
  November's corrected 18 with `reading_date = 2026-11-06`.

### Dated switch versus receipt time

- November 1 calendar boundary: Monthly usage becomes zero; Published usage can
  still report October 30's provisional 39.
- October 31 readings received November 2: Published usage reports October's 41;
  October's monthly statistic is corrected in October.
- November 1 readings received November 3: Published usage switches to November's
  available usage, for example 3. Monthly and daily statistics use the November 1
  reporting bucket/date; ordinary entity state history records November 3 receipt.
- A real zero is supported, but no extra zero is injected at 00:00 followed by an
  invented 23:59 observation. API date-only data cannot establish those times.

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
- If February monthly totals are corrected after March already started, the
  canonical external monthly series is upserted and March's verified baseline is
  repaired. Later automatic live states cannot override that external series.
- Restore a cache with pending boundaries and verify reconciliation. Exercise
  publication and anchor arrival in both orders.

## Manual Recovery

- In rare edge cases where month-boundary cache values look stale or incorrect, use button `button.mijnted_reset_statistics` to rebuild cache/statistics from fresh data.
- This resets integration cache/injection tracking, not recorder data. See the [reset behavior](SENSORS.md#related-button). Entity IDs are examples; use your registry's actual ID.
