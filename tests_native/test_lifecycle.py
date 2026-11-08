"""Real HA calendar callbacks, delayed reading periods, and full-instance restart."""

from datetime import date, datetime, timedelta, timezone
import asyncio
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from homeassistant.helpers.storage import Store
from homeassistant.helpers import frame
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant.common import async_fire_time_changed, async_test_home_assistant

from tests_native.conftest import config_entry, load_native_registries
from tests_native.helpers import ENTRY_ID, own_id, query, refresh, reporting_entities, settled

ZONE = ZoneInfo("Europe/Amsterdam")


@pytest.mark.parametrize(("start_at", "scenario", "boundary"), [
    (datetime(2026, 10, 31, 23, 59, tzinfo=ZONE),
     {"reading_date": date(2026, 10, 30), "reading": 868, "october_average": None},
     datetime(2026, 11, 1, tzinfo=ZONE)),
    (datetime(2026, 3, 28, 23, 59, tzinfo=ZONE),
     {"reading_date": date(2026, 3, 27), "reading": 829},
     datetime(2026, 4, 1, tzinfo=ZONE)),
    (datetime(2026, 10, 24, 23, 59, tzinfo=ZONE),
     {"reading_date": date(2026, 10, 23), "reading": 868, "october_average": None},
     datetime(2026, 11, 1, tzinfo=ZONE)),
    (datetime(2026, 12, 31, 23, 59, tzinfo=ZONE),
     {"reading_date": date(2026, 12, 30), "reading": 900},
     datetime(2027, 1, 1, tzinfo=ZONE)),
    (datetime(2028, 2, 29, 23, 59, tzinfo=ZONE),
     {"reading_date": date(2028, 2, 28), "reading": 5},
     datetime(2028, 3, 1, tzinfo=ZONE)),
], indirect=["start_at", "scenario"])
async def test_real_calendar_callback_keeps_reading_period_separate(
    hass, runtime, scenario, boundary, freezer, native_api,
):
    """Native month/year/leap/DST scheduling -> calendar zero, unchanged dated report."""
    entities = reporting_entities(hass, runtime)
    monthly_id = entities["monthly_usage"].entity_id
    report_id = entities["published_usage"].entity_id
    before = hass.states.get(report_id)
    previous_state = before.state
    previous_date = before.attributes["reading_date"]
    # Isolate the calendar callback from the coordinator's independent poll timer.
    await hass.data["mijnted"][runtime.entry_id].async_shutdown()
    requests = native_api.get_filter_status.await_count
    just_before = boundary - timedelta(seconds=1)
    freezer.move_to(just_before)
    async_fire_time_changed(hass, just_before)
    await settled(hass)
    assert hass.states.get(monthly_id).attributes["month_id"] == f"{just_before.month}.{just_before.year}"
    freezer.move_to(boundary)
    async_fire_time_changed(hass, boundary)
    await settled(hass)
    monthly = hass.states.get(monthly_id)
    assert float(monthly.state) == 0
    assert monthly.attributes["month_id"] == f"{boundary.month}.{boundary.year}"
    assert monthly.attributes["days"] == 0
    report = hass.states.get(report_id)
    assert report.state == previous_state
    assert report.attributes["reading_date"] == previous_date
    assert report.attributes["month_id"] == f"{scenario.reading_date.month}.{scenario.reading_date.year}"
    assert native_api.get_filter_status.await_count == requests
    results = await query(hass, {own_id()}, boundary, boundary + timedelta(days=1))
    assert results == {}
    month_start = datetime(scenario.reading_date.year, scenario.reading_date.month, 1, tzinfo=ZONE)
    actual = await query(hass, {own_id()}, month_start, boundary - timedelta(seconds=1), period="hour")
    assert len(actual[own_id()]) == 1
    assert actual[own_id()][0]["start"] == month_start.timestamp()


@pytest.mark.parametrize("scenario", [{"reading_date": date(2026, 10, 30),
                                      "reading": 868, "october_average": None}], indirect=True)
@pytest.mark.parametrize("start_at", [datetime(2026, 11, 1, 12, tzinfo=ZONE)], indirect=True)
@pytest.mark.parametrize("november_reading", [870, 873])
async def test_late_first_reading_uses_its_date_without_a_synthetic_zero(
    hass, runtime, scenario, freezer, november_reading,
):
    """November 1 data received November 3 -> real zero/nonzero value in its own bucket."""
    entities = reporting_entities(hass, runtime)
    report_id = entities["published_usage"].entity_id
    monthly_id = entities["monthly_usage"].entity_id
    assert float(hass.states.get(monthly_id).state) == 0
    assert float(hass.states.get(report_id).state) == 39
    assert await query(hass, {own_id()}, datetime(2026, 11, 1, tzinfo=ZONE),
                       datetime(2026, 11, 2, tzinfo=ZONE)) == {}
    freezer.move_to(datetime(2026, 11, 2, 12, tzinfo=timezone.utc))
    scenario.reading_date, scenario.reading = date(2026, 10, 31), 870
    scenario.october_average = 139.05
    await refresh(hass, runtime)
    assert float(hass.states.get(report_id).state) == 41
    assert hass.states.get(report_id).attributes["month_id"] == "10.2026"
    freezer.move_to(datetime(2026, 11, 3, 12, tzinfo=timezone.utc))
    scenario.reading_date, scenario.reading = date(2026, 11, 1), november_reading
    await refresh(hass, runtime)
    report = hass.states.get(report_id)
    expected = november_reading - 870
    assert float(report.state) == expected
    assert report.attributes["reading_date"] == "2026-11-01"
    assert report.attributes["month_id"] == "11.2026"
    assert report.last_updated.date() == date(2026, 11, 3)
    identifiers = {own_id(), f"mijnted:{ENTRY_ID}_reported_daily_usage"}
    results = await query(hass, identifiers, datetime(2026, 11, 1, tzinfo=ZONE),
                          datetime(2026, 11, 1, 23, 59, tzinfo=ZONE), period="hour")
    for identifier in identifiers:
        assert len(results[identifier]) == 1
        assert results[identifier][0]["mean"] == expected
        assert results[identifier][0]["start"] == datetime(2026, 11, 1, tzinfo=ZONE).timestamp()


@pytest.mark.parametrize("scenario", [{"reading_date": date(2026, 12, 31), "reading": 1000}], indirect=True)
@pytest.mark.parametrize("start_at", [datetime(2027, 1, 1, 12, tzinfo=timezone.utc)], indirect=True)
@pytest.mark.parametrize("january_reading", [0, 2])
async def test_annual_zero_baseline_is_applied_to_real_daily_imports(
    hass, runtime, scenario, freezer, january_reading,
):
    """Actual January reset -> nonnegative daily and month-to-date buckets, including true zero."""
    freezer.move_to(datetime(2027, 1, 2, 12, tzinfo=timezone.utc))
    scenario.reading_date, scenario.reading = date(2027, 1, 1), january_reading
    await refresh(hass, runtime)
    entities = reporting_entities(hass, runtime)
    report = hass.states.get(entities["published_usage"].entity_id)
    assert float(report.state) == january_reading
    assert report.attributes["month_id"] == "1.2027"
    assert report.attributes["reading_date"] == "2027-01-01"
    identifier = f"mijnted:{ENTRY_ID}_reported_daily_usage"
    rows = await query(hass, {identifier, own_id()}, datetime(2027, 1, 1, tzinfo=ZONE),
                       datetime(2027, 1, 1, 23, 59, tzinfo=ZONE), period="hour")
    assert rows[identifier][0]["mean"] == january_reading
    assert rows[own_id()][0]["mean"] == january_reading


def test_real_ha_restart_restores_checkpoints_registries_and_recorder(
    native_api, scenario, freezer, async_setup_recorder_instance, tmp_path,
):
    """Two stopped/started HA instances and event loops reuse actual registry, Store and SQL files."""
    original = {}

    async def phase(restarting):
        """Run one complete HA lifecycle on its own event loop."""
        async with async_test_home_assistant(config_dir=str(tmp_path), load_registries=False) as native:
            frame.async_setup(native)
            entry = config_entry()
            entry.add_to_hass(native)
            try:
                await load_native_registries(native)
                await async_setup_recorder_instance(native, {
                    "db_url": "sqlite:///" + str(tmp_path / "native-reporting.db"), "commit_interval": 0,
                })
                assert await native.config_entries.async_setup(entry.entry_id)
                await settled(native)
                entities = reporting_entities(native, entry)
                if not restarting:
                    original["entity"] = entities["published_usage"].entity_id
                    original["device"] = entities["published_usage"].device_id
                    scenario.reading_date, scenario.reading = date(2026, 11, 7), 890
                    await refresh(native, entry)
                    assert Path(native.config.path(".storage", f"mijnted_daily_{entry.entry_id}")).is_file()
                else:
                    assert entities["published_usage"].entity_id == original["entity"]
                    assert entities["published_usage"].device_id == original["device"]
                    report = native.states.get(entities["published_usage"].entity_id)
                    assert float(report.state) == 23
                    assert report.attributes["reading_date"] == "2026-11-08"
                    identifier = f"mijnted:{ENTRY_ID}_reported_daily_usage"
                    recorded = await query(native, {identifier}, datetime(2026, 11, 1, tzinfo=ZONE),
                                           datetime(2026, 11, 30, tzinfo=ZONE), period="day")
                    assert [row["mean"] for row in recorded[identifier]] == [2, 3]
                    stored = await Store(native, 1, f"mijnted_daily_{entry.entry_id}").async_load()
                    assert stored["results"] == {"2026-11-07": 2, "2026-11-08": 3}
            finally:
                if entry.state is ConfigEntryState.LOADED:
                    assert await native.config_entries.async_unload(entry.entry_id)
                    await settled(native)
                await native.async_stop()

    freezer.move_to(datetime(2026, 11, 7, 12, tzinfo=timezone.utc))
    asyncio.run(phase(False))
    freezer.move_to(datetime(2026, 11, 9, 12, tzinfo=timezone.utc))
    scenario.reading_date, scenario.reading = date(2026, 11, 8), 893
    asyncio.run(phase(True))
