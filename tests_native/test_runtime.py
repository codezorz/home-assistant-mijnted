"""HA-native reporting registration, storage, and recorder checks."""

from datetime import date, datetime, timedelta, timezone
from calendar import monthrange
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from homeassistant.components.recorder.models import StatisticData, StatisticMeanType, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics, async_import_statistics, get_metadata,
)
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.storage import Store
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import async_fire_time_changed

from tests_native.helpers import ENTRY_ID, own_id, query, refresh, reporting_entities, settled

ZONE = ZoneInfo("Europe/Amsterdam")


def stale_months():
    """Represent accepted October/November readings awaiting a verified correction."""
    return {
        "2026-10": {"month_id": "10.2026", "year": 2026, "month": 10,
                    "start_date": "2026-10-01", "end_date": "2026-10-31", "total_usage": 39,
                    "average_usage": 139.05, "finalized": True, "state": "FINALIZED", "start_locked": True,
                    "devices": [{"id": 1, "start": 829, "end": 868, "usage": 39}]},
        "2026-11": {"month_id": "11.2026", "year": 2026, "month": 11,
                    "start_date": "2026-11-01", "end_date": "2026-11-06", "total_usage": 20,
                    "average_usage": None, "state": "OPEN", "start_locked": True,
                    "devices": [{"id": 1, "start": 868, "end": 888, "usage": 20}]},
    }


async def test_native_registration_metadata_and_icon(hass, runtime):
    """Real HA platform setup -> device-linked Published usage with owned metadata."""
    entities = reporting_entities(hass, runtime)
    published = entities["published_usage"]
    state = hass.states.get(published.entity_id)
    assert float(state.state) == 18
    assert state.attributes["icon"] == "mdi:chart-timeline-variant"
    assert state.attributes["reading_date"] == "2026-11-06"
    assert state.attributes["month_id"] == "11.2026"
    assert not any(key.startswith(("average_", "last_year_")) for key in state.attributes)
    assert published.original_name == "Published usage"
    assert published.translation_key == "published_usage"
    assert all(row.device_id == published.device_id for row in entities.values())
    device = device_registry.async_get(hass).async_get(published.device_id)
    assert device.identifiers == {("mijnted", "native-unit")}
    average = hass.states.get(entities["average_monthly_usage"].entity_id)
    assert float(average.state) == 139.05
    assert average.attributes["month_id"] == "10.2026"


async def test_native_recorder_four_monthly_series(hass, runtime):
    """Actual recorder import/query -> four independent October aggregates."""
    keys = ("monthly_usage", "average_monthly_usage", "last_year_monthly_usage", "last_year_average_monthly_usage")
    identifiers = {f"mijnted:{ENTRY_ID}_{key}" for key in keys}
    metadata = await get_instance(hass).async_add_executor_job(get_metadata, hass)
    assert identifiers <= metadata.keys()
    for identifier in identifiers:
        assert metadata[identifier][1]["source"] == "mijnted"
        assert metadata[identifier][1]["has_sum"] is False
        assert metadata[identifier][1]["mean_type"] == StatisticMeanType.ARITHMETIC
        assert metadata[identifier][1]["unit_of_measurement"] == "Units"
    result = await query(
        hass, identifiers,
        datetime.fromisoformat("2026-10-01T00:00:00+02:00"),
        datetime.fromisoformat("2026-10-31T23:59:59+01:00"),
    )
    assert {key: result[f"mijnted:{ENTRY_ID}_{key}"][0]["mean"] for key in keys} == {
        "monthly_usage": 41, "average_monthly_usage": 139.05,
        "last_year_monthly_usage": 17, "last_year_average_monthly_usage": 181.01,
    }


@pytest.mark.parametrize(("language", "expected"), [
    ("nl", "Gepubliceerd verbruik"), ("de", "Veröffentlichter Verbrauch"),
], indirect=["language"])
async def test_native_report_translation(hass, runtime, expected):
    """HA's translation loader supplies the Published usage entity-local label."""
    published = reporting_entities(hass, runtime)["published_usage"]
    assert published.original_name == expected
    assert expected in hass.states.get(published.entity_id).attributes["friendly_name"]


async def test_report_imports_continue_with_comparison_views_disabled(hass, runtime, scenario):
    """Registry-disabled views -> actual reporting jobs still update every monthly series."""
    entities = reporting_entities(hass, runtime)
    registry = entity_registry.async_get(hass)
    keys = ("average_monthly_usage", "last_year_monthly_usage", "last_year_average_monthly_usage")
    for key in keys:
        registry.async_update_entity(entities[key].entity_id, disabled_by=entity_registry.RegistryEntryDisabler.USER)
    await settled(hass)
    scenario.october_usage = 42
    scenario.october_average = 140
    await refresh(hass, runtime)
    identifiers = {f"mijnted:{ENTRY_ID}_{key}" for key in ("monthly_usage", *keys)}
    result = await query(hass, identifiers, datetime(2026, 10, 1, tzinfo=ZONE), datetime(2026, 10, 31, 23, tzinfo=ZONE))
    assert {key: result[f"mijnted:{ENTRY_ID}_{key}"][0]["mean"] for key in ("monthly_usage", *keys)} == {
        "monthly_usage": 42, "average_monthly_usage": 140,
        "last_year_monthly_usage": 17, "last_year_average_monthly_usage": 181.01,
    }
    assert all(registry.async_get(entities[key].entity_id).disabled_by is not None for key in keys)


@pytest.mark.parametrize(("total", "average"), [(42, 140), (40, 138), (0, 0)])
async def test_native_late_corrections_upsert_a_single_bucket(hass, runtime, scenario, total, average):
    """Revised/downward/zero publications -> one corrected SQL row and adjacent baseline."""
    scenario.october_usage = total
    scenario.october_average = average
    await refresh(hass, runtime)
    await refresh(hass, runtime)
    identifier = own_id()
    result = await query(hass, {identifier}, datetime(2026, 10, 1, tzinfo=ZONE),
                         datetime(2026, 10, 31, 23, tzinfo=ZONE), period="hour")
    assert len(result[identifier]) == 1
    assert result[identifier][0]["mean"] == total
    entities = reporting_entities(hass, runtime)
    report = hass.states.get(entities["published_usage"].entity_id)
    assert float(report.state) == 888 - (829 + total)
    assert report.attributes["reading_date"] == "2026-11-06"


async def test_native_entity_observation_cannot_override_report_statistics(hass, runtime):
    """A real recorder entity-state row of 39 stays independent of October's reported 41."""
    monthly = reporting_entities(hass, runtime)["monthly_usage"].entity_id
    async_import_statistics(hass, StatisticMetaData(
        source="recorder", statistic_id=monthly, name="Monthly usage",
        mean_type=StatisticMeanType.NONE, has_sum=True, unit_of_measurement="Units", unit_class=None,
    ), [StatisticData(start=datetime(2026, 10, 31, 23, tzinfo=ZONE), state=39, sum=38)])
    await settled(hass)
    result = await query(hass, {monthly, own_id()}, datetime(2026, 10, 1, tzinfo=ZONE),
                         datetime(2026, 10, 31, 23, 59, tzinfo=ZONE), types={"state", "mean"})
    assert result[monthly][0]["state"] == 39
    assert result[own_id()][0]["mean"] == 41
    metadata = await get_instance(hass).async_add_executor_job(get_metadata, hass)
    published = reporting_entities(hass, runtime)["published_usage"].entity_id
    assert published not in metadata


async def test_mixed_dashboard_queries_entity_state_and_report_means(hass, runtime):
    """The configured mixed four-line graph resolves each series' supported statistic type."""
    comparison = reporting_entities(hass, runtime)["last_year_monthly_usage"].entity_id
    expected = {
        own_id(): ("mean", 41),
        f"mijnted:{ENTRY_ID}_average_monthly_usage": ("mean", 139.05),
        comparison: ("state", 17),
        f"mijnted:{ENTRY_ID}_last_year_average_monthly_usage": ("mean", 181.01),
    }
    rows = await query(hass, set(expected), datetime(2026, 10, 1, tzinfo=ZONE),
                       datetime(2026, 10, 31, 23, 59, tzinfo=ZONE), types={"state", "mean"})
    for identifier, (kind, value) in expected.items():
        assert rows[identifier][0][kind] == value


async def test_native_history_coverage_and_retained_periods(hass, runtime):
    """Retained cache source months define coverage; recorder periods outside it persist."""
    keys = ("monthly_usage", "average_monthly_usage", "last_year_monthly_usage", "last_year_average_monthly_usage")
    identifiers = {f"mijnted:{ENTRY_ID}_{key}" for key in keys}
    result = await query(hass, identifiers, datetime(2025, 7, 1, tzinfo=ZONE), datetime(2026, 11, 30, 23, tzinfo=ZONE))
    assert {key: len(result[f"mijnted:{ENTRY_ID}_{key}"]) for key in keys} == {
        "monthly_usage": 17, "average_monthly_usage": 16,
        "last_year_monthly_usage": 5, "last_year_average_monthly_usage": 5,
    }
    start = datetime(2024, 6, 1, tzinfo=ZONE)
    async_add_external_statistics(hass, StatisticMetaData(
        source="mijnted", statistic_id=own_id(), name="Published usage", has_sum=False,
        mean_type=StatisticMeanType.ARITHMETIC, unit_of_measurement="Units", unit_class=None,
    ), [StatisticData(start=start, mean=7)])
    await refresh(hass, runtime)
    result = await query(hass, {own_id()}, start, datetime(2024, 6, 30, 23, tzinfo=ZONE))
    assert result[own_id()][0]["mean"] == 7


@pytest.mark.parametrize("scenario", [{"extra_readings": {2: 500}}], indirect=True)
@pytest.mark.parametrize("response", ["empty", "missing_meter"])
async def test_partial_response_preserves_complete_report_and_metric_metadata(hass, runtime, scenario, response):
    """Empty or missing-meter response -> complete dated report and independent comparisons remain valid."""
    scenario.reading_date = date(2026, 11, 7)
    scenario.reading = 890
    scenario.partial = response == "empty"
    scenario.omitted_devices = {2}
    await refresh(hass, runtime)
    entities = reporting_entities(hass, runtime)
    report = hass.states.get(entities["published_usage"].entity_id)
    assert float(report.state) == 18
    assert report.attributes["reading_date"] == "2026-11-06"
    average = hass.states.get(entities["average_monthly_usage"].entity_id)
    comparison = hass.states.get(entities["last_year_monthly_usage"].entity_id)
    assert float(average.state) == 139.05
    assert average.attributes["month_id"] == "10.2026"
    assert float(comparison.state) == 193
    assert comparison.attributes["last_year_month_id"] == "11.2025"
    stored = await Store(hass, 1, f"mijnted_daily_{runtime.entry_id}").async_load()
    assert "2026-11-07" not in stored["checkpoints"]
    assert "2026-11-07" not in stored["results"]
    result = await query(hass, {own_id()}, datetime(2026, 11, 1, tzinfo=ZONE), datetime(2026, 11, 30, tzinfo=ZONE))
    assert result[own_id()][0]["mean"] == 18
    daily = f"mijnted:{ENTRY_ID}_reported_daily_usage"
    assert await query(hass, {daily}, datetime(2026, 11, 7, tzinfo=ZONE),
                       datetime(2026, 11, 8, tzinfo=ZONE), period="day") == {}


@pytest.mark.parametrize("scenario", [{"october_average": None}], indirect=True)
async def test_monthly_publication_updates_average_during_meter_outage(hass, runtime, scenario):
    """Closing readings before publication -> independent average/report update despite missing live meters."""
    coordinator = hass.data["mijnted"][runtime.entry_id]
    assert coordinator.data["monthly_history_cache"]["2026-10"].published_usage is None
    entities = reporting_entities(hass, runtime)
    average = entities["average_monthly_usage"].entity_id
    assert hass.states.get(average).attributes["month_id"] == "9.2026"
    scenario.october_average = 139.05
    scenario.partial = True
    scenario.reading_date = date(2026, 11, 7)
    await refresh(hass, runtime)
    october = coordinator.data["monthly_history_cache"]["2026-10"]
    assert october.published_usage == 41
    assert october.boundary_reconciled
    assert float(hass.states.get(average).state) == 139.05
    assert hass.states.get(average).attributes["month_id"] == "10.2026"
    report = hass.states.get(entities["published_usage"].entity_id)
    assert float(report.state) == 18
    assert report.attributes["month_id"] == "11.2026"
    assert report.attributes["reading_date"] == "2026-11-06"


@pytest.mark.parametrize("bad_date", [date(2026, 11, 5), date(2026, 11, 9)])
async def test_invalid_new_observation_date_cannot_replace_complete_report(hass, runtime, scenario, bad_date):
    """Regressing/future endpoint date -> recorder keeps the last complete known reading."""
    scenario.reading_date, scenario.reading = bad_date, 900
    await refresh(hass, runtime)
    report = hass.states.get(reporting_entities(hass, runtime)["published_usage"].entity_id)
    assert float(report.state) == 18
    assert report.attributes["reading_date"] == "2026-11-06"
    recorded = await query(hass, {own_id()}, datetime(2026, 11, 1, tzinfo=ZONE),
                           datetime(2026, 11, 30, tzinfo=ZONE))
    assert recorded[own_id()][0]["mean"] == 18


async def test_forward_daily_observations_persist_and_correct_in_recorder(hass, runtime, scenario, freezer, native_api):
    """New consecutive dates, same-date correction, gap and recovery use actual Store and SQL."""
    identifier = f"mijnted:{ENTRY_ID}_reported_daily_usage"
    initial = await query(hass, {identifier}, datetime(2026, 11, 1, tzinfo=ZONE), datetime(2026, 11, 30, tzinfo=ZONE), period="day")
    assert initial == {}
    freezer.move_to(datetime(2026, 11, 12, tzinfo=timezone.utc))
    for day, value in ((7, 890), (7, 891), (9, 899), (10, 902)):
        scenario.reading_date = date(2026, 11, day)
        scenario.reading = value
        await refresh(hass, runtime)
    result = await query(hass, {identifier}, datetime(2026, 11, 1, tzinfo=ZONE), datetime(2026, 11, 30, tzinfo=ZONE), period="day")
    assert [row["mean"] for row in result[identifier]] == [3, 3]
    assert [datetime.fromtimestamp(row["start"], ZONE).day for row in result[identifier]] == [7, 10]
    stored = await Store(hass, 1, f"mijnted_daily_{runtime.entry_id}").async_load()
    assert stored["results"] == {"2026-11-07": 3, "2026-11-10": 3}
    assert Path(hass.config.path(".storage", f"mijnted_daily_{runtime.entry_id}")).is_file()
    assert native_api.get_device_statuses_for_date.call_count > 0
    for call in native_api.get_device_statuses_for_date.call_args_list:
        target = call.args[0]
        assert target.day in (1, monthrange(target.year, target.month)[1])


async def test_daily_device_set_change_seeds_compatible_observations(hass, runtime, scenario, freezer):
    """An additional meter does not create a cumulative-counter spike in daily consumption."""
    freezer.move_to(datetime(2026, 11, 9, tzinfo=timezone.utc))
    scenario.extra_readings = {2: 500}
    scenario.reading_date, scenario.reading = date(2026, 11, 7), 890
    await refresh(hass, runtime)
    identifier = f"mijnted:{ENTRY_ID}_reported_daily_usage"
    assert await query(hass, {identifier}, datetime(2026, 11, 1, tzinfo=ZONE), datetime(2026, 11, 30, tzinfo=ZONE), period="day") == {}
    scenario.extra_readings = {2: 502}
    scenario.reading_date, scenario.reading = date(2026, 11, 8), 893
    await refresh(hass, runtime)
    result = await query(hass, {identifier}, datetime(2026, 11, 1, tzinfo=ZONE), datetime(2026, 11, 30, tzinfo=ZONE), period="day")
    assert [row["mean"] for row in result[identifier]] == [5]


@pytest.mark.parametrize("initial_months", [stale_months()], indirect=True)
async def test_native_store_restores_and_repairs_accepted_boundary(hass, runtime):
    """File-backed accepted 39 -> native refresh resolves October 41 and November 18."""
    cache = hass.data["mijnted"][runtime.entry_id].data["monthly_history_cache"]
    assert cache["2026-10"].published_usage == cache["2026-10"].total_usage == 41
    assert cache["2026-10"].boundary_reconciled
    assert cache["2026-11"].devices[0].start == 870
    assert cache["2026-11"].total_usage == 18
    stored = await Store(hass, 1, f"mijnted_monthly_cache_{runtime.entry_id}").async_load()
    assert stored["monthly_history_cache"]["2026-10"]["boundary_reconciled"]
    assert float(hass.states.get(reporting_entities(hass, runtime)["published_usage"].entity_id).state) == 18


@pytest.mark.parametrize("initial_months", [stale_months()], indirect=True)
@pytest.mark.parametrize("scenario", [{"fail_october_anchor": True}], indirect=True)
async def test_pending_boundary_backoff_survives_native_reload(hass, runtime, scenario, freezer):
    """Unavailable closing anchor -> persisted pending repair recovers after reload and retry time."""
    identifier = runtime.entry_id
    cache = hass.data["mijnted"][identifier].data["monthly_history_cache"]
    retry_at = cache["2026-10"].boundary_retry_at
    assert cache["2026-10"].published_usage == 41
    assert not cache["2026-10"].boundary_reconciled
    assert retry_at
    assert await hass.config_entries.async_reload(identifier)
    await settled(hass)
    restored = hass.data["mijnted"][identifier].data["monthly_history_cache"]
    assert restored["2026-10"].boundary_retry_at == retry_at
    scenario.fail_october_anchor = False
    freezer.move_to(datetime.fromisoformat(retry_at) + timedelta(seconds=1))
    await refresh(hass, runtime)
    corrected = hass.data["mijnted"][identifier].data["monthly_history_cache"]
    assert corrected["2026-10"].boundary_reconciled
    assert corrected["2026-11"].devices[0].start == 870
    assert corrected["2026-11"].total_usage == 18


async def test_unload_cancels_native_timers_and_listeners(hass, runtime, native_api, freezer):
    """Actual platform unload -> no live calendar callback or coordinator polling remains."""
    coordinator = hass.data["mijnted"][runtime.entry_id]
    entities = reporting_entities(hass, runtime)
    calendar = hass.data["sensor"].get_entity(entities["monthly_usage"].entity_id)
    listener_count = len(coordinator._listeners)
    assert listener_count > 0 and calendar._cancel_month_timer is not None
    assert await hass.config_entries.async_unload(runtime.entry_id)
    await settled(hass)
    assert not coordinator._listeners
    assert calendar._cancel_month_timer is None
    requests = native_api.get_filter_status.await_count
    later = dt_util.utcnow() + timedelta(hours=2)
    freezer.move_to(later)
    async_fire_time_changed(hass, later)
    await settled(hass)
    assert native_api.get_filter_status.await_count == requests
    assert await hass.config_entries.async_setup(runtime.entry_id)
    await settled(hass)
    fresh = hass.data["mijnted"][runtime.entry_id]
    assert fresh is not coordinator
    assert len(fresh._listeners) == listener_count
    assert native_api.get_filter_status.await_count > requests
    active_calendar = hass.data["sensor"].get_entity(entities["monthly_usage"].entity_id)
    assert active_calendar is not calendar
    assert active_calendar._cancel_month_timer is not None
    assert reporting_entities(hass, runtime)["published_usage"].entity_id == entities["published_usage"].entity_id
    result = await query(hass, {own_id()}, datetime(2026, 11, 1, tzinfo=ZONE),
                         datetime(2026, 11, 30, tzinfo=ZONE), period="hour")
    assert len(result[own_id()]) == 1


async def test_native_storage_retries_unchanged_failed_write(hass, runtime, scenario, monkeypatch):
    """A real Store write error -> unchanged observation retries and persists its daily result."""
    key = f"mijnted_daily_{runtime.entry_id}"
    real_save = Store.async_save
    attempts = 0
    blocked = True
    async def failing_save(store, data):
        """Block the selected checkpoint write until recovery is allowed."""
        nonlocal attempts
        if store.key == key:
            attempts += 1
            if blocked:
                raise OSError("synthetic temporary write failure")
        await real_save(store, data)
    monkeypatch.setattr(Store, "async_save", failing_save)
    scenario.reading_date, scenario.reading = date(2026, 11, 7), 890
    await refresh(hass, runtime)
    path = Path(hass.config.path(".storage", key))
    before = json.loads(path.read_text())["data"]
    assert "2026-11-07" not in before["checkpoints"]
    blocked = False
    await refresh(hass, runtime)
    persisted = json.loads(path.read_text())["data"]
    assert attempts >= 2
    assert persisted["results"] == {"2026-11-07": 2}
    assert "2026-11-07" in persisted["checkpoints"]


async def test_native_restore_failure_does_not_overwrite_file_history(hass, runtime, scenario, monkeypatch):
    """Restore I/O error during reload -> saved checkpoint is protected and read retried."""
    key = f"mijnted_daily_{runtime.entry_id}"
    path = Path(hass.config.path(".storage", key))
    original = path.read_bytes()
    assert await hass.config_entries.async_unload(runtime.entry_id)
    await settled(hass)
    real_load = Store.async_load
    failures = 0
    blocked = True
    async def failing_load(store):
        """Block checkpoint restore while keeping all other Store operations real."""
        nonlocal failures
        if store.key == key and blocked:
            failures += 1
            raise OSError("synthetic temporary restore failure")
        return await real_load(store)
    monkeypatch.setattr(Store, "async_load", failing_load)
    scenario.reading_date, scenario.reading = date(2026, 11, 7), 890
    assert await hass.config_entries.async_setup(runtime.entry_id)
    await settled(hass)
    assert path.read_bytes() == original
    published = reporting_entities(hass, runtime)["published_usage"].entity_id
    assert hass.states.get(published).state == "unknown"
    assert failures >= 1
    blocked = False
    await refresh(hass, runtime)
    assert float(hass.states.get(published).state) == 20
    assert json.loads(path.read_text())["data"]["results"] == {"2026-11-07": 2}
