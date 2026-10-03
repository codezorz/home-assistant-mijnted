---
applyTo: "tests/**,pytest.ini,requirements_test.txt,.github/workflows/python-tests.yml"
description: Test design, mock boundaries, async behavior, and Home Assistant stand-ins for local tests.
---

# Testing

Environment setup, check commands, CI, and HA smoke testing are owned by
`doc/DEVELOPMENT.md`. Test discovery and async mode are configured in `pytest.ini`.
Dependency lists belong in `requirements_test.txt` and the runtime manifest.

## Test design

- Add meaningful tests for changed behavior, especially month/year rollover,
  API lag, partial failure, baseline locking, and late statistics corrections.
- Do not add application tests for documentation-only edits or assertions that
  merely duplicate implementation details.
- Group by feature/module (`test_date_util.py`, `test_cache_refresh_retry.py`).
  Follow existing class-based grouping and use fixtures for reusable data.
- Write `async def test_...` directly; `asyncio_mode = auto` handles the loop.
- Use `AsyncMock` for awaited calls and `MagicMock` for synchronous calls.
- Patch where the symbol is looked up by the code under test, not only where
  originally defined. Keep orchestration-module imports consistent with nearby tests.
- Freeze/patch the date at the module that uses it; never make boundary tests
  depend on the real current month.
- Give modules/classes a brief purpose docstring and test methods a one-line
  condition/result description. Standard pytest `-v` shows node IDs, not these
  docstrings automatically.

## Home Assistant stand-ins

`tests/conftest.py` registers a `MagicMock` tree for imported `homeassistant.*`
modules in `sys.modules`. It also supplies concrete values/classes where mocks
cannot behave like the real type:

| Symbol | Purpose |
|---|---|
| `_ha`, `_SUBMODULES` | Root mock and registered HA module paths |
| `_ha.const.Platform.SENSOR` / `.BUTTON` | Literal platform strings read by `const.py` at import time |
| `_CoordinatorEntity`, `_SensorEntity`, `_ButtonEntity` | Real empty classes preventing multiple-inheritance metaclass conflicts |
| `_ConfigFlow`, `_OptionsFlow`, `_ConfigEntry` | Config-flow stand-ins, including domain subclass arguments and a read-only `config_entry` property |
| `_pkce` | Deterministic PKCE pair for imports/auth-flow tests |

When adding an import-time `homeassistant.*` dependency, register the module.
Set concrete values for constants/classes read at import time. Add a real
stand-in class if a mock would be used as a base class. These stand-ins test
Python logic, not compatibility with a real HA API.

## Mock boundaries

| Layer | Approach |
|---|---|
| Pure date/list/data/JWT helpers | Test directly; patch the clock where needed. Not every utility is pure: OAuth and retry helpers involve I/O or timing. |
| Cache/coordinator helpers in `__init__.py` | Patch sibling fetching/persistence functions at the importing module; assert state transitions and retry behavior. |
| API/auth | Mock HTTP sessions or the API method boundary. Never contact production MijnTed in unit tests. |
| HA objects | Use `hass.data = {}` and realistic `entry.entry_id` / `entry.data`; mock async methods explicitly. |
| Persistence | Prefer patching `_load_persisted_cache` / `_save_persisted_cache`; otherwise mock `Store.async_load` / `async_save` as async methods. |
| Recorder | The import is mocked by conftest; assert payload/metadata when injection is the behavior under test. |

Build domain objects with small factory helpers (`DeviceReading`,
`MonthCacheEntry`). Keep month IDs, cache keys, and lifecycle states realistic.
Extract repeated patch groups only when it makes a test's intent easier to see.

## Common failures

| Failure | Fix |
|---|---|
| `ModuleNotFoundError: homeassistant.*` | Register the imported module in `_SUBMODULES`. |
| Metaclass conflict | Supply a real stand-in base class rather than multiple `MagicMock` bases. |
| Missing import-time constant | Assign the concrete constant on `_ha` before imports. |
| Cannot await a `MagicMock` / coroutine never awaited | Use `AsyncMock` for async targets and verify awaited calls. |
| Unexpected persistence call | Mock the persistence helper or async `Store` methods. |
| Missing non-HA dependency | Install test/runtime requirements in the documented environment. |

Do not dismiss behavioral assertion failures as "outside HA." Only actual
runtime-specific checks belong in the real-HA verification step.

## Agent tooling tests

Session-hook tests run the shell script in temporary Git repositories to verify
worktree-root discovery, metadata-only output, and missing-directory handling.
Keep these tests independent of HA and production network access.
