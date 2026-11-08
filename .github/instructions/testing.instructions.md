---
applyTo: "tests/**,tests_native/**,.github/scripts/*.test.py,pytest.ini,pyproject.toml,uv.lock,requirements_test.txt,requirements_native.txt,.github/dependabot.yml,.github/workflows/validate-code.yml,.github/workflows/codeql.yml"
description: Meaningful test design, async/mock boundaries, and native Home Assistant verification.
---

# Testing

Use [development setup/checks](../../docs/DEVELOPMENT.md) for commands and dependency
maintenance; [CI policy](ci.instructions.md) owns workflows and fork approvals.
Dependency inputs belong in `pyproject.toml` with `uv.lock`; the pip export is generated.

## Test design

- Add behavioral coverage for changed contracts, not assertions that copy
  implementation details. Documentation-only changes need no application tests.
- Group by feature/module with reusable fixtures and small domain-object factories.
  Keep month IDs, cache keys, and lifecycle states realistic.
- Write async tests directly; `pytest.ini` configures discovery/import mode and
  `asyncio_mode = auto`. Use `AsyncMock` for awaited calls and `MagicMock` for sync calls.
- Patch where a symbol is looked up. Freeze/patch clocks at their use site;
  boundary tests must not depend on today's date.
- Give modules/classes brief purpose docstrings and tests a one-line
  condition/result description.

## Mock boundaries

| Layer | Approach |
|---|---|
| Pure data/date helpers | Test directly with controlled clocks. OAuth/retry helpers also require I/O/timing boundaries. |
| Coordinator/cache | Patch fetching/persistence at the importing module; assert state transitions, retries, and corrections. |
| API/auth | Mock HTTP/API methods; never contact production MijnTed in unit tests. |
| HA objects | Use realistic entry IDs/data and concrete `hass.data`; mock async methods explicitly. |
| Storage | Patch the owning load/save helper or use async `Store` methods with detached snapshots. |
| Recorder | Assert payload/metadata in logic tests; use native HA for database/API compatibility. |

## Home Assistant stand-ins

[`tests/conftest.py`](../../tests/conftest.py) owns the mocked `homeassistant.*`
module tree and concrete enum/entity/flow stand-ins. Register new import-time
dependencies there; use real constants/classes where a `MagicMock` cannot model
typing, inheritance, or read-only properties. These tests establish Python logic,
not compatibility with the real HA lifecycle or translation loader.

Run [`tests/ha_localization_check.py`](../../tests/ha_localization_check.py) directly
in the [native environment](../../docs/DEVELOPMENT.md#native-home-assistant-localization-checks),
outside that conftest. Pure recorder-reduction coverage uses the pinned fixture in
`tests/fixtures/`, which records upstream source/license provenance.

For cache/date/statistic changes, cover the applicable
[month lifecycle](../../docs/MONTH_SWITCH.md) and
[sensor contracts](../../docs/SENSORS.md): lag, rollover/DST, zero versus missing,
partial devices, period-scoped fallback, restart, and late corrections. Named-zone
tests use the `tzdata` development dependency.

## HA-native reporting tests

Use the [isolated reporting profile](../../docs/DEVELOPMENT.md#ha-native-reporting-tests),
outside the mocked conftest. Keep HA components and temporary Store/SQLite I/O real;
replace the external API with synthetic responses and block TCP networking. Query
through the recorder executor and flush pending work before assertions. Scope fault
injection to the selected Store key, and explicitly unload/stop restart instances.

## Tooling and failures

Tooling tests live beside scripts in `.github/scripts/*.test.py` or their feature
module under `tests/`. Hook tests use temporary repositories and no production access.
Run `actionlint` for changed Actions workflows.

Resolve missing dependencies/modules in the documented environment and fix failed
behavioral assertions. Report genuine native-HA verification gaps separately;
do not label a failing test as an environment limitation merely because HA is mocked.
