---
applyTo: "custom_components/mijnted/**"
description: Coordinator ownership, platform setup, monthly cache persistence, and partial-refresh semantics.
---

# How the integration is orchestrated

- **One coordinator per config entry**: `DataUpdateCoordinator` is created in `__init__.py` and does all API fetching. It stores the result in `coordinator.data`.
- **Sensors never call the API**: They only read from `coordinator.data`. The coordinator’s update method (e.g. `async_update_data` in `__init__.py`) calls the API and updates the cache.
- **Platform setup**: `__init__.py` forwards platform setup to `sensor.py` and `button.py`. Those modules create entities (sensors/buttons) and pass them the coordinator.
- **Cache and persistence**: Monthly history cache is loaded/saved in `__init__.py` (`_load_persisted_cache` / `_save_persisted_cache`). Respect `const.CACHE_HISTORY_MONTHS` and the existing cache key/format when changing cache behavior.
- **Reconciliation**: `reconciliation.py` rechecks pending historical boundaries,
  including months with accepted starts or finalized results. Published own totals are recognized
  separately from complete readings and remain revisable. Persist provenance and
  bounded retry state; repair the following baseline only from compatible real
  device anchors. `FINALIZED`/`start_locked` must not block verified corrections.
- **Forward daily data**: `daily.py` owns entry-scoped dated checkpoints/results
  and feeds `coordinator.data["daily_usage"]`. It uses received latest statuses,
  not historical scans. Only consecutive compatible dates produce consumption;
  preserve gaps and January's annual reset. Its store survives monthly resets.
- **Device naming**: `naming.py` restores and reserves duplicate-name ordinals in
  `mijnted_device_names_<entry_id>`, separately from monthly/daily storage. Prepare
  the `device_names` projection before coordinator listeners run. Group by raw
  context and label family/kind, never translated text or response order. Retain
  reservations and last known contexts through partial failures; do not reclaim
  slots or clear them during monthly resets. Failed loads defer allocation and
  failed writes retry on subsequent refreshes without blocking readings.
- **Reading-month projection**: the coordinator builds `reading_report` from the
  latest complete persisted checkpoint and the matching month's baseline using
  `utils/readings.py`. Partial new-date responses must not advance its date or
  replace canonical graph values with mixed-date totals. Entities own their
  metadata and read this projection; they never depend on another entity's state.
- **Auth**: Follow `api-auth.instructions.md` for credential storage, token callbacks, and refresh behavior.
- **Partial failures**: `_fetch_and_normalize_api_data` uses `gather(return_exceptions=True)` for most data endpoints and replaces failures with empty defaults. Delivery-type fetching is outside that gather. A returned coordinator payload can therefore represent a partial refresh; `last_successful_sync` does not prove every endpoint succeeded. Preserve cached values only according to each sensor's documented contract.
- **Month identity**: Cache dictionary keys use `YYYY-MM`; API/display month IDs use `M.YYYY`. Use the appropriate `DateUtil` formatter/parser rather than interchanging formats. Lifecycle and baseline-locking invariants are in `docs/MONTH_SWITCH.md`.

When adding or changing behavior, keep this flow: config entry → coordinator → platforms → entities reading from `coordinator.data`.

See [usage reporting architecture](../../docs/USAGE_REPORTING.md) for period
selection, persisted reading checkpoints, and statistics ownership.
