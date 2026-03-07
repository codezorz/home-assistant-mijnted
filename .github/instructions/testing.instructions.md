---
applyTo: "tests/**"
---

# Testing

## Running tests

Activate the Home Assistant venv first (cross-OS):

- Linux/macOS (`bash`/`zsh`): `source ~/.venv-home-assistant/bin/activate`
- Windows PowerShell: `& "$HOME\.venv-home-assistant\Scripts\Activate.ps1"`
- Windows cmd: `%USERPROFILE%\.venv-home-assistant\Scripts\activate.bat`

```
python -m pip install -r requirements_test.txt
pytest
```

Config lives in `pytest.ini`: test discovery in `tests/`, async mode `auto` (no `@pytest.mark.asyncio` needed).

Dependencies (`requirements_test.txt`): `pytest`, `pytest-asyncio`, `PyJWT`, `aiohttp`, `pkce`, `requests`.

## How the Home Assistant mock works

Tests run **outside** the HA runtime. `tests/conftest.py` injects a `MagicMock` tree into `sys.modules` for every `homeassistant.*` submodule the integration imports at module scope. This lets `from homeassistant.core import HomeAssistant` resolve without installing HA.

### Key pieces in conftest.py

| Symbol | Purpose |
|--------|---------|
| `_ha` | Root `MagicMock` standing in for the `homeassistant` package. |
| `_SUBMODULES` dict | Maps every `homeassistant.*` path the integration touches to the corresponding attribute on `_ha`. Registered in `sys.modules` before any test import. |
| `_ha.const.Platform.SENSOR` / `.BUTTON` | Set to literal `"sensor"` / `"button"` because `const.py` reads them at import time. |
| `_CoordinatorEntity`, `_SensorEntity`, `_ButtonEntity` | Real (empty) classes assigned to the mock tree. Required because sensor classes use multiple inheritance; two `MagicMock` bases cause a metaclass conflict. |

### When to update conftest.py

Add a new entry to `_SUBMODULES` whenever:

- The integration gains a new `from homeassistant.<submodule> import ...` that executes at **import time** (top-level or in a module-scope variable).
- A test itself needs to import from a `homeassistant.*` path that is not yet registered.

If the new import references a constant or class used at module scope (like `Platform.SENSOR`), assign a concrete value on `_ha` instead of relying on the `MagicMock` default.

If a new HA base class is used in multiple-inheritance (e.g. a new entity type), add a real empty class for it in conftest and assign it to the mock, following the existing `_CoordinatorEntity` / `_SensorEntity` / `_ButtonEntity` pattern.

## What to mock

### Layer 1 -- Pure utilities (no mocking needed)

`DateUtil`, `ListUtil`, `JwtUtil`, `DataUtil`, and other helpers in `utils/` are pure functions. Test them directly. The only mock needed is `datetime.now()` when the function calls it internally -- patch `custom_components.mijnted.utils.date_util.datetime` (or the relevant module's `datetime`).

### Layer 2 -- `__init__.py` module-level functions

Functions like `_update_current_month_cache`, `_update_and_enrich_cache`, `_ensure_monthly_history_cache` live in `__init__.py`. Import the module as:

```python
import custom_components.mijnted.__init__ as init_mod
```

Then use `patch.object(init_mod, "<function_name>", ...)` to mock sibling functions called within the function under test. This keeps each test focused on one function's logic.

Common mocks at this layer:

| Target | Mock type | Typical return |
|--------|-----------|----------------|
| `init_mod._update_current_month_cache` | `AsyncMock` | `True` (success) or `False` (skip) |
| `init_mod._resolve_current_month_devices` | `AsyncMock` | `([device_dicts], start_total)` |
| `init_mod._enrich_cache_with_api_data` | `AsyncMock` | `None` |
| `init_mod._snapshot_cache_averages` | `MagicMock` | `{}` |
| `init_mod._lock_current_month_starts_when_previous_complete` | `AsyncMock` | `False` |
| `init_mod._recalculate_current_month_starts_if_previous_finalized` | `AsyncMock` | `False` |
| `init_mod._load_cache_from_coordinator` | `MagicMock` | `({}, "YYYY-MM-DD")` |
| `init_mod._load_or_build_cache` | `AsyncMock` | `({}, False)` |
| `init_mod._save_persisted_cache` | `AsyncMock` | `None` |
| `init_mod._get_or_create_statistics_tracking` | `MagicMock` | `MagicMock()` |

### Layer 3 -- API and auth

`MijntedApi` and `MijntedAuth` make real HTTP calls. **Always mock them** in tests:

- For unit tests of cache/coordinator logic, pass an `AsyncMock()` as `api`. Set specific return values on methods like `api.get_device_statuses_for_date`.
- For future integration tests of `api.py` itself, mock `aiohttp.ClientSession` (async) or `requests.Session` (sync, used in `OAuthUtil`).

### Layer 4 -- Home Assistant objects

For tests that call orchestration functions (`_ensure_monthly_history_cache`, `async_setup_entry`, etc.):

| HA object | How to create | Required attributes |
|-----------|---------------|---------------------|
| `hass` | `MagicMock()` | `hass.data = {}` |
| `entry` (ConfigEntry) | `MagicMock()` | `entry.entry_id = "test_entry"`, `entry.data = {...}` |
| `Store` | Patched via `init_mod._save_persisted_cache` / `_load_persisted_cache` (preferred) or mock `Store.async_load` / `async_save` directly. |
| `DataUpdateCoordinator` | Not instantiated in current tests; mock the functions that read from it (`_load_cache_from_coordinator`). |

### Layer 5 -- Recorder / statistics

`async_import_statistics` from `homeassistant.components.recorder.statistics` is already a `MagicMock` via conftest. If a test calls code that invokes it, no extra setup is needed -- but assert on the mock if the test cares about what statistics were injected.

## Avoiding common HA-related exceptions

| Problem | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: homeassistant.*` | A new HA import not registered in conftest | Add it to `_SUBMODULES` in `conftest.py` |
| `TypeError: metaclass conflict` | Multiple-inheritance with two `MagicMock` bases | Add a real empty class in conftest and assign it to the mock attribute (see `_SensorEntity` pattern) |
| `AttributeError` on `_ha.const.Platform.X` | Code reads a Platform constant at import time | Set `_ha.const.Platform.X = "x"` in conftest before imports |
| `TypeError: object MagicMock can't be used in 'await'` | Forgot `AsyncMock` for an async function | Use `AsyncMock()` or `new_callable=AsyncMock` in `patch.object` |
| `RuntimeWarning: coroutine was never awaited` | Patched an async call with plain `MagicMock` | Switch to `AsyncMock` |
| `StoreError` / persistence failure | Test calls `_save_persisted_cache` without mocking | Patch `init_mod._save_persisted_cache` with `AsyncMock` |

## Test file conventions

- **One test file per module or feature**: `test_date_util.py` for `utils/date_util.py`, `test_cache_refresh_retry.py` for cache retry behavior, etc.
- **Class-based grouping**: Group related tests in a class (`TestGetLastYear`, `TestUpdateCurrentMonthCacheReturnValue`). Class name matches the function or behavior under test.
- **Fixtures over setup methods**: Use `@pytest.fixture` for reusable objects (`api`, `hass`, `entry`, `now`). Keep fixtures in the test class when specific to that class; move to `conftest.py` when shared across files.
- **Async tests**: Write `async def test_...` directly. `asyncio_mode = auto` handles the event loop.
- **Descriptive assertion messages**: Use the second argument to `assert` for non-obvious checks (e.g. `assert date == OLD, "date must not advance on skip"`).

## Docstrings and documentation

Every level of the test hierarchy gets a docstring. The style differs by level:

### Test module docstring

The file starts with a multi-line module docstring describing what area of the codebase is under test and the overall goal. Keep it to 2-3 sentences.

```python
"""Tests for current-month cache refresh retry behavior.

Verifies that a skipped or failed _update_current_month_cache does not
advance cached_last_update_date, preserving the retry window for the
next poll cycle.
"""
```

For utility test files a shorter single-line docstring suffices:

```python
"""Tests for utils/date_util.py."""
```

### Test class docstring

Each test class gets a one-line or short multi-line docstring stating the function or behavior it covers:

```python
class TestUpdateCurrentMonthCacheReturnValue:
    """Verify the bool return from _update_current_month_cache."""
```

```python
class TestEnsureMonthlyHistoryCacheRetryBehavior:
    """Prove that cached_last_update_date is NOT advanced when refresh is
    skipped or fails, preserving the retry window for the next poll."""
```

### Test method docstring

Every `test_*` method gets a **one-line** docstring describing the scenario (input/condition) and expected outcome, separated by `->`:

```python
async def test_returns_false_when_filter_status_empty_and_cache_usable(self, api, now):
    """Empty filter_status + usable cache -> skip (False)."""
```

```python
async def test_skip_signal_when_refresh_raises(self, api, now):
    """When _update_current_month_cache raises, skip signal is True."""
```

```python
def test_january_wraps_to_december(self, mock_dt):
    """January wraps to previous year's December."""
```

The docstring format is: **condition/input** `->` **expected result**. Keep it on one line. Use the `->` arrow or a "When X, Y" phrasing -- pick whichever reads most naturally.

### Helper functions

Module-level helper functions (prefixed with `_`) get a one-line docstring explaining what they build or do:

```python
def _make_cache_entry(month, year, *, devices=None, total_usage=100.0):
    """Build a minimal MonthCacheEntry for testing."""
```

### What NOT to do

- Do not omit docstrings -- pytest uses them as the test description in verbose output (`-v`).
- Do not repeat the method name in prose ("Test that test_returns_false ...").
- Do not write multi-line docstrings for individual test methods; keep them to a single line.

## Helper patterns

### Building test data

Use factory helpers at module level for domain objects:

```python
def _make_cache_entry(month, year, *, devices=None, total_usage=100.0):
    """Build a minimal MonthCacheEntry for testing."""
    if devices is None:
        devices = [DeviceReading(id=1, start=0.0, end=50.0, usage=50.0)]
    return MonthCacheEntry(
        month_id=DateUtil.format_month_year_key(month, year),
        year=year, month=month,
        start_date=DateUtil.format_date_for_api(
            DateUtil.get_first_day_of_month(month, year)),
        end_date=f"{year}-{month:02d}-15",
        total_usage=total_usage, average_usage=3.0,
        devices=devices, finalized=False,
        state=MONTH_STATE_OPEN, start_locked=False,
    )
```

### Wrapping repeated patches

When a test class patches the same set of sibling functions repeatedly, extract them as methods that return context managers:

```python
def _patch_save(self):
    return patch.object(init_mod, "_save_persisted_cache", new_callable=AsyncMock)
```

Then compose them with `with (...):` blocks.

## Adding a new test file

1. Create `tests/test_<module>.py`.
2. If the module imports from `homeassistant.*`, verify the import is covered in `conftest.py`.
3. Use `import custom_components.mijnted.<module> as mod` for patching targets.
4. Follow the class-based, fixture-driven pattern from existing tests.
5. Run `pytest tests/test_<module>.py -v` to verify.
