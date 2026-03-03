# Temporary Month Switch Notes (2026-03-03)

This is a temporary working note to continue the month-switch fix later.

## What We Observed

- On `2026-03-02` around `03:00`, monthly usage jumped from `0` to `169`.
- The jump came from `end` readings being refreshed while `start` readings stayed from an older snapshot.
- The older snapshot appears to be tied to the period when February was considered finalized (average availability event), not to the final end-of-month device readings.

## Core Insight

Current month start values must be treated differently before and after previous-month finalization.

- Before finalization: start values are still provisional and can be corrected.
- After finalization: month boundary is closed and should be stable.

## Two Important Dates / Signals

1. **`last_update` reaches last day of previous month**  
   Example: `last_update = 2026-02-28` while current month is March.  
   Meaning: previous month device readings are complete enough to align next month starts.

2. **`average_usage` becomes available for previous month**  
   Meaning: month is finalized/closed and should no longer be changed.

## Expected Behavior (Target)

- When `last_update` becomes previous month last day:
  - Update previous month end readings.
  - Align current month start readings to those end readings.
- When `last_update` moves into new month:
  - Start normal accumulation for current month (`days`, per-device usage, averages).
- When average becomes available for previous month:
  - Finalize/close previous month.
  - Stop modifying finalized month data.

## Proposed Rule Set

- **Before previous month is finalized**:
  - Derive current month starts from latest available previous month end readings.
  - Recompute current month totals from current start/end (not stale cached totals).
- **After previous month is finalized**:
  - Freeze previous month data.
  - Keep current month baseline derived from finalized previous-month ends.

## Suggested State Model

For each month, use explicit states:

- `OPEN`: month in progress
- `COMPLETE_READINGS`: last day readings known (boundary can be aligned)
- `FINALIZED`: average available, month closed

Transitions:

- `OPEN -> COMPLETE_READINGS` when `last_update >= previous_month_last_day`
- `COMPLETE_READINGS -> FINALIZED` when `average_usage` becomes available

## Implementation Direction (Next Session)

- Keep month-boundary alignment logic driven by previous-month end readings while not finalized.
- Separate "final readings complete" from "finalized by insight average".
- Keep `current.total_usage` derived from start/end whenever available.
- Add debug logs for:
  - boundary alignment updates,
  - finalization transition,
  - current month start recalculation decisions.

