# Temporary Month Switch Issue

Something strange happened on `2026-03-02` around `03:00`.

## Observed Behavior

- On `2026-03` monthly usage jumped from `0` to `169`.
- Based on the attributes, `169` is theoretically correct by calculation.
- On `2026-03-01` the start device readings matched previous-month end readings (`start 2026.03 == end 2026.02`).
- On `2026-03-02` the start readings changed, which caused the `169` usage jump.
- The changed starts looked like values from `2026-02-06` (origin was unclear).
- Around the same time, `sensor.mijnted_last_update` changed from `2026-02-28` to `2026-03-01`.

## Current Snapshot

```yaml
last_update_date: '2026-03-02'
month_id: '3.2026'
start_date: '2026-03-01'
end_date: '2026-03-02'
devices:
  - id: 21724686
    start: 99
    end: 113
    usage: 14
  - id: 21726092
    start: 0
    end: 0
    usage: 0
  - id: 15837606
    start: 0
    end: 0
    usage: 0
  - id: 15837773
    start: 524
    end: 679
    usage: 155
days: 2
last_year_usage: 20
last_year_average_usage: 333.16
total_usage_start: 623
total_usage_end: 792
total_usage: 0
average_usage_per_day: 0
```

## History Snapshot (Relevant)

```yaml
- month_id: '2.2026'
  year: 2026
  month: 2
  start_date: '2026-02-01'
  end_date: '2026-02-28'
  average_usage: null
  devices:
    - id: 21724686
      start: 88
      end: 113
      usage: 25
    - id: 15837773
      start: 447
      end: 679
      usage: 232
    - id: 21726092
      start: 0
      end: 0
      usage: 0
    - id: 15837606
      start: 0
      end: 0
      usage: 0
  days: 28
  average_usage_per_day: 9.18
  total_usage_start: 535
  total_usage_end: 792
  total_usage: 257
- month_id: '1.2026'
  year: 2026
```

## Expected Behavior

- When `last_update` becomes `2026-02-28`, update final device end readings for `2026.02` and fix start readings for `2026.03`.
- When `last_update` becomes `2026-03-01`, start calculating for `2026.03` (days start counting, averages become available, and end readings advance).

## Important Dates / Signals

- `last_update` reaches the last day of previous month: device readings are complete enough for boundary alignment.
- Previous-month `average_usage` becomes available: month can be treated as closed/finalized.
