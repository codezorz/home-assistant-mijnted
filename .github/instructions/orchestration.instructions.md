---
applyTo: "custom_components/mijnted/**"
description: Coordinator ownership, platform setup, monthly cache persistence, and partial-refresh semantics.
---

# How the integration is orchestrated

- **One coordinator per config entry**: `DataUpdateCoordinator` is created in `__init__.py` and does all API fetching. It stores the result in `coordinator.data`.
- **Sensors never call the API**: They only read from `coordinator.data`. The coordinator’s update method (e.g. `async_update_data` in `__init__.py`) calls the API and updates the cache.
- **Platform setup**: `__init__.py` forwards platform setup to `sensor.py` and `button.py`. Those modules create entities (sensors/buttons) and pass them the coordinator.
- **Cache and persistence**: Monthly history cache is loaded/saved in `__init__.py` (`_load_persisted_cache` / `_save_persisted_cache`). Respect `const.CACHE_HISTORY_MONTHS` and the existing cache key/format when changing cache behavior.
- **Auth**: Follow `api-auth.instructions.md` for credential storage, token callbacks, and refresh behavior.
- **Partial failures**: `_fetch_and_normalize_api_data` uses `gather(return_exceptions=True)` for most data endpoints and replaces failures with empty defaults. Delivery-type fetching is outside that gather. A returned coordinator payload can therefore represent a partial refresh; `last_successful_sync` does not prove every endpoint succeeded. Preserve cached values only according to each sensor's documented contract.
- **Month identity**: Cache dictionary keys use `YYYY-MM`; API/display month IDs use `M.YYYY`. Use the appropriate `DateUtil` formatter/parser rather than interchanging formats. Lifecycle and baseline-locking invariants are in `doc/MONTH_SWITCH.md`.

When adding or changing behavior, keep this flow: config entry → coordinator → platforms → entities reading from `coordinator.data`.
