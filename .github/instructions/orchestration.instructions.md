---
applyTo: "custom_components/mijnted/**"
---

# How the integration is orchestrated

- **One coordinator per config entry**: `DataUpdateCoordinator` is created in `__init__.py` and does all API fetching. It stores the result in `coordinator.data`.
- **Sensors never call the API**: They only read from `coordinator.data`. The coordinator’s update method (e.g. `async_update_data` in `__init__.py`) calls the API and updates the cache.
- **Platform setup**: `__init__.py` forwards platform setup to `sensor.py` and `button.py`. Those modules create entities (sensors/buttons) and pass them the coordinator.
- **Cache and persistence**: Monthly history cache is loaded/saved in `__init__.py` (`_load_persisted_cache` / `_save_persisted_cache`). Respect `const.CACHE_HISTORY_MONTHS` and the existing cache key/format when changing cache behavior.
- **Auth**: Token refresh lives in `auth.py`. The API layer uses it; config entry stores tokens/identifiers, not raw passwords.

When adding or changing behavior, keep this flow: config entry → coordinator → platforms → entities reading from `coordinator.data`.
