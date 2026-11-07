"""Regression coverage for late published totals and revisable month boundaries."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

import custom_components.mijnted.__init__ as coordinator
from custom_components.mijnted.reconciliation import async_reconcile_boundaries
from custom_components.mijnted.sensors import base, usage
from custom_components.mijnted.sensors.models import DeviceReading, MonthCacheEntry
from custom_components.mijnted.utils.readings import build_reading_report
from tests.fixtures.ha_statistics_2026_11 import _reduce_statistic, reduce_month_ts_factory

ZONE = ZoneInfo("Europe/Amsterdam")


def month_entry(month, *, start, end, published=None, year=2026, reconciled=False):
    """Build a real cache entry with a single synthetic meter."""
    last_day = coordinator.DateUtil.get_last_day_of_month(month, year)
    return MonthCacheEntry(
        month_id=f"{month}.{year}", month=month, year=year,
        start_date=f"{year}-{month:02}-01", end_date=last_day.isoformat(),
        total_usage=published if published is not None else end - start,
        average_usage=139.05 if published is not None else None,
        devices=[DeviceReading(id=1, start=start, end=end, usage=end-start)],
        finalized=True, state="FINALIZED", start_locked=True,
        published_usage=published, boundary_reconciled=reconciled,
    )


def api_month(total, *, month="10.2026", average=139.05):
    """Return a minimal API publication or placeholder payload."""
    return {"monthlyEnergyUsages": [{
        "monthYear": month, "totalEnergyUsage": total,
        "averageEnergyUseForBillingUnit": average,
    }]}


def make_sensor(cache, sensor_class=usage.MijnTedMonthlyUsageSensor, last_update="2026-11-06"):
    """Create a reading entity with real cache resolution and recorder enabled."""
    instance = sensor_class(SimpleNamespace(data={
        "monthly_history_cache": cache, "last_update": last_update,
        "filter_status": [{"deviceNumber": "1", "currentReadingValue": 888.0}],
    }, last_update_success=True), "test_entry")
    instance.entity_id = f"sensor.home_{instance.sensor_type}"
    instance.hass = MagicMock()
    instance.hass.config.components = {"recorder"}
    source_date = coordinator.DateUtil.parse_last_sync_date(last_update)
    source_key = coordinator.DateUtil.format_month_key(source_date.year, source_date.month) if source_date else ""
    entry = cache.get(source_key)
    instance.coordinator.data["reading_report"] = build_reading_report(
        {"date": last_update, "readings": {1: 888}}, entry.to_dict() if entry else {},
    )
    return instance


@pytest.fixture
def clock():
    """Freeze the shared HA-local clock while retaining real calendar operations."""
    with patch.object(base.dt_util, "now", return_value=datetime(2026, 11, 7, 12, tzinfo=ZONE)) as now:
        with patch.object(base.dt_util, "get_default_time_zone", return_value=ZONE):
            yield now


class TestPublishedBoundaryRepair:
    """Repair already-locked boundaries instead of trusting legacy finalization."""

    async def test_legacy_finalized_39_becomes_41_and_november_becomes_18(self, clock):
        """Published October plus corrected anchor -> consistent history, baseline and live value."""
        cache = {"2026-10": month_entry(10, start=829, end=868),
                 "2026-11": month_entry(11, start=868, end=888)}
        api = AsyncMock()
        api.get_device_statuses_for_date.return_value = [{"deviceNumber": "1", "currentReadingValue": 870}]
        result, skipped = await coordinator._update_and_enrich_cache(
            api, cache, [{"deviceNumber": "1", "currentReadingValue": 888}],
            "2026-11-06", api_month(41), False, clock.return_value,
        )
        assert result and not skipped
        assert cache["2026-10"].total_usage == cache["2026-10"].published_usage == 41
        assert cache["2026-10"].boundary_reconciled
        assert cache["2026-11"].devices[0].start == 870
        assert cache["2026-11"].total_usage == 18
        assert make_sensor(cache).state == 18
        reported = make_sensor(cache, usage.MijnTedPublishedUsageSensor)
        assert reported.state == 18
        assert reported.extra_state_attributes["month_id"] == "11.2026"
        assert reported.extra_state_attributes["reading_date"] == "2026-11-06"
        assert reported.state_class is None
        api.get_device_statuses_for_date.assert_awaited_once()

    async def test_publication_before_anchor_survives_restart_and_retries(self, clock):
        """Published 41 with stale/partial anchor -> persist pending repair, then recover."""
        cache = {"2026-10": month_entry(10, start=829, end=868),
                 "2026-11": month_entry(11, start=868, end=888)}
        coordinator._apply_enrichment_to_cache_entries(cache, {2026: api_month(41)}, clock.return_value)
        api = AsyncMock()
        api.get_device_statuses_for_date.return_value = []
        await async_reconcile_boundaries(api, cache, "2026-11-06", clock.return_value)
        assert cache["2026-10"].total_usage == 41
        assert not cache["2026-10"].boundary_reconciled
        assert cache["2026-11"].devices[0].start == 868
        store = MagicMock(async_save=AsyncMock(), async_load=AsyncMock())
        with patch.object(coordinator, "Store", return_value=store):
            await coordinator._save_persisted_cache(MagicMock(), "test_entry", cache)
            store.async_load.return_value = store.async_save.call_args.args[0]
            restored = await coordinator._load_persisted_cache(MagicMock(), "test_entry")
        assert restored["2026-10"].boundary_retry_at
        api.get_device_statuses_for_date.reset_mock()
        await async_reconcile_boundaries(api, restored, "2026-11-06", clock.return_value)
        api.get_device_statuses_for_date.assert_not_awaited()
        clock.return_value += timedelta(hours=1)
        api.get_device_statuses_for_date.return_value = [{"deviceNumber": "1", "currentReadingValue": 870}]
        await async_reconcile_boundaries(api, restored, "2026-11-06", clock.return_value)
        assert restored["2026-10"].boundary_reconciled
        assert restored["2026-11"].total_usage == 18

    async def test_verified_boundary_repairs_successor_without_refetching_stale_anchor(self, clock):
        """A verified historical boundary -> repair a stale adjacent baseline without downgrading it."""
        cache = {"2026-10": month_entry(10, start=829, end=870, published=41, reconciled=True),
                 "2026-11": month_entry(11, start=868, end=888)}
        cache["2026-11"].start_locked = False
        api = AsyncMock()
        api.get_device_statuses_for_date.return_value = [{"deviceNumber": "1", "currentReadingValue": 868}]
        await coordinator._update_and_enrich_cache(
            api, cache, [{"deviceNumber": "1", "currentReadingValue": 888}],
            "2026-11-06", api_month(41), False, clock.return_value,
        )
        assert cache["2026-10"].devices[0].end == 870
        assert cache["2026-11"].total_usage == 18
        api.get_device_statuses_for_date.assert_not_awaited()

    async def test_anchor_before_publication_remains_revisable_after_lock(self, clock):
        """A complete but provisional anchor -> later anchor correction is still applied."""
        cache = {"2026-10": month_entry(10, start=829, end=868),
                 "2026-11": month_entry(11, start=868, end=888)}
        api = AsyncMock()
        api.get_device_statuses_for_date.return_value = [{"deviceNumber": "1", "currentReadingValue": 868}]
        await async_reconcile_boundaries(api, cache, "2026-11-06", clock.return_value)
        assert not cache["2026-10"].boundary_reconciled
        clock.return_value += timedelta(hours=1)
        api.get_device_statuses_for_date.return_value = [{"deviceNumber": "1", "currentReadingValue": 870}]
        await async_reconcile_boundaries(api, cache, "2026-11-06", clock.return_value)
        assert cache["2026-10"].total_usage == 41
        assert cache["2026-11"].total_usage == 18
        coordinator._apply_enrichment_to_cache_entries(cache, {2026: api_month(41)}, clock.return_value)
        await async_reconcile_boundaries(api, cache, "2026-11-06", clock.return_value)
        assert cache["2026-10"].boundary_reconciled

    @pytest.mark.parametrize(("published", "anchor", "expected_current"), [(40, 869, 19), (0, 829, 59)])
    async def test_published_downward_revision_reopens_reconciled_boundary(self, clock, published, anchor, expected_current):
        """A revision, including zero -> upsert own total and reopen the accepted baseline."""
        cache = {"2026-10": month_entry(10, start=829, end=870, published=41, reconciled=True),
                 "2026-11": month_entry(11, start=870, end=888)}
        coordinator._apply_enrichment_to_cache_entries(cache, {2026: api_month(published)}, clock.return_value)
        api = AsyncMock()
        api.get_device_statuses_for_date.return_value = [{"deviceNumber": "1", "currentReadingValue": anchor}]
        await async_reconcile_boundaries(api, cache, "2026-11-06", clock.return_value)
        assert cache["2026-10"].published_usage == published
        assert cache["2026-10"].boundary_reconciled
        assert make_sensor(cache).state == expected_current

    @pytest.mark.parametrize(("total", "average"), [(0, None), (float("nan"), 10), (5, float("inf")), (-1, 10)])
    def test_placeholder_or_invalid_publication_preserves_known_result(self, clock, total, average):
        """Missing publication evidence or invalid values -> cached published 41 remains valid."""
        cache = {"2026-10": month_entry(10, start=829, end=870, published=41, reconciled=True)}
        coordinator._apply_enrichment_to_cache_entries(cache, {2026: api_month(total, average=average)}, clock.return_value)
        assert cache["2026-10"].published_usage == cache["2026-10"].total_usage == 41

    async def test_partial_or_inconsistent_anchor_never_fabricates_a_device(self, clock):
        """Published own total with incompatible readings -> leave baseline pending and unmodified."""
        previous = month_entry(10, start=829, end=868, published=41)
        previous.devices.append(DeviceReading(id=2, start=0, end=0, usage=0))
        cache = {"2026-10": previous, "2026-11": month_entry(11, start=868, end=888)}
        api = AsyncMock()
        api.get_device_statuses_for_date.return_value = [{"deviceNumber": "1", "currentReadingValue": 870}]
        await async_reconcile_boundaries(api, cache, "2026-11-06", clock.return_value)
        assert not cache["2026-10"].boundary_reconciled
        assert cache["2026-11"].devices[0].start == 868
        assert previous.devices[1].end == 0

    async def test_inconsistent_cached_start_is_refreshed_before_monthly_publication(self, clock):
        """Opening cache above closing anchor -> verify the real preceding anchor and recover."""
        cache = {"2026-10": month_entry(10, start=1000, end=868),
                 "2026-11": month_entry(11, start=868, end=888)}
        api = AsyncMock()
        async def anchor(target):
            """Supply compatible opening and closing readings for October."""
            return [{"deviceNumber": "1", "currentReadingValue": 829 if target.month == 9 else 870}]
        api.get_device_statuses_for_date.side_effect = anchor
        await async_reconcile_boundaries(api, cache, "2026-11-06", clock.return_value)
        assert cache["2026-10"].total_usage == 41
        assert cache["2026-10"].devices[0].start == 829
        assert cache["2026-11"].total_usage == 18

    async def test_december_repair_preserves_january_annual_zero(self, clock):
        """December end correction -> January still uses the annual zero baseline."""
        clock.return_value = datetime(2027, 1, 5, tzinfo=ZONE)
        cache = {"2026-12": month_entry(12, start=829, end=868, published=41),
                 "2027-01": month_entry(1, year=2027, start=0, end=5)}
        api = AsyncMock()
        api.get_device_statuses_for_date.return_value = [{"deviceNumber": "1", "currentReadingValue": 870}]
        await async_reconcile_boundaries(api, cache, "2027-01-04", clock.return_value)
        assert cache["2027-01"].devices[0].start == 0
        assert cache["2027-01"].total_usage == 5


class TestMonthlyEntitiesAndGraph:
    """Keep calendar progress, published periods, and graph ownership distinct."""

    @pytest.mark.parametrize(("year", "month", "source"), [(2026, 11, "2026-10-30"), (2027, 1, "2026-12-30"), (2028, 3, "2028-02-28")])
    async def test_calendar_start_is_zero_even_with_empty_endpoint(self, clock, year, month, source):
        """Calendar rollover while API lags -> calendar zero without a synthetic report sample."""
        clock.return_value = datetime(year, month, 1, tzinfo=ZONE)
        sensor = make_sensor({}, last_update=source)
        sensor.coordinator.data["filter_status"] = []
        sensor._last_known_month = "2026-10"
        sensor._last_known_value = 39
        assert sensor.state == 0
        assert sensor.extra_state_attributes["month_id"] == f"{month}.{year}"
        with patch.object(base, "StatisticData", side_effect=lambda **kwargs: kwargs), patch.object(base, "async_add_external_statistics") as external:
            await sensor._async_inject_statistics()
        external.assert_not_called()

    def test_published_period_and_zero_remain_paired_during_partial_failure(self, clock):
        """Latest published zero -> correct month retained despite failed live endpoints."""
        cache = {"2026-09": month_entry(9, start=800, end=829, published=29),
                 "2026-10": month_entry(10, start=829, end=829, published=0)}
        sensor = make_sensor(cache, usage.MijnTedPublishedUsageSensor, last_update="2026-10-31")
        sensor.coordinator.data["filter_status"] = []
        sensor.coordinator.data["last_update"] = {}
        assert sensor.state == 0
        assert sensor.extra_state_attributes["month_id"] == "10.2026"
        assert sensor.extra_state_attributes["monthly_statistic_id"] == "mijnted:test_entry_monthly_usage"
        assert sensor.state_class is None
        cache.clear()
        sensor.coordinator.data["reading_report"] = None
        assert sensor.state is None
        assert "month_id" not in sensor.extra_state_attributes

    def test_january_restart_does_not_use_previous_year_counter_as_usage(self, clock):
        """API-behind January cache plus missing endpoints -> preserve calendar zero."""
        clock.return_value = datetime(2027, 1, 1, tzinfo=ZONE)
        cache = {"2027-01": month_entry(1, year=2027, start=0, end=888)}
        cache["2027-01"].end_date = "2026-12-31"
        sensor = make_sensor(cache)
        sensor.coordinator.data.update({"filter_status": [], "last_update": {}})
        assert sensor.state == 0

    def test_missing_month_start_does_not_report_the_entire_cumulative_counter(self, clock):
        """No usable month-start cache -> unknown instead of the cumulative 888 as usage."""
        sensor = make_sensor({})
        assert sensor.state is None

    def test_rollover_callback_reschedules_and_cancels_on_unload(self, clock):
        """Local calendar timer -> no cloud call, immediate write, and cancellable next boundary."""
        clock.return_value = datetime(2026, 10, 31, 23, 59, tzinfo=ZONE)
        sensor = make_sensor({})
        sensor.async_write_ha_state = MagicMock()
        scheduled = []
        cancel = MagicMock()
        def schedule(hass, action, when):
            """Capture the real callback and local datetime."""
            scheduled.append((action, when))
            return cancel
        def close_task(coro):
            """Close the scheduled coroutine in this synchronous lifecycle exercise."""
            coro.close()
        sensor.hass.async_create_task.side_effect = close_task
        with patch.object(usage, "async_track_point_in_time", side_effect=schedule):
            sensor._schedule_month_rollover()
            assert scheduled[0][1] == datetime(2026, 11, 1, tzinfo=ZONE)
            clock.return_value = scheduled[0][1]
            scheduled[0][0](clock.return_value)
            sensor.async_write_ha_state.assert_called_once()
            assert scheduled[1][1] == datetime(2026, 12, 1, tzinfo=ZONE)
            sensor._remove_month_timer()
            cancel.assert_called_once()

    async def test_late_correction_upserts_old_month_in_external_series(self, clock):
        """An already imported month -> corrected value replaces its dated aggregate after restart."""
        cache = {"2026-10": month_entry(10, start=829, end=868)}
        sensor = make_sensor(cache)
        with patch.object(base, "StatisticData", side_effect=lambda **kwargs: kwargs), patch.object(base, "async_add_external_statistics") as external, patch.object(base, "async_import_statistics") as internal:
            await sensor._async_inject_statistics()
            assert external.call_args.args[2][0]["mean"] == 39
            cache["2026-10"].total_usage = 41
            sensor = make_sensor(cache)
            sensor.entity_id = "sensor.renamed_monthly_usage"
            await sensor._async_inject_statistics()
            metadata, rows = external.call_args.args[1:]
            assert metadata["statistic_id"] == "mijnted:test_entry_monthly_usage"
            assert rows[0] == {"start": datetime(2026, 10, 1, tzinfo=ZONE), "mean": 41}
            assert internal.call_args.args[1]["statistic_id"] == sensor.entity_id

    async def test_published_entity_backfills_shared_history_without_projecting_41_into_november(self, clock):
        """Published entity alone -> backfilled October 41 with stable own-usage series metadata."""
        sensor = make_sensor({"2026-10": month_entry(10, start=829, end=870, published=41)},
                             usage.MijnTedPublishedUsageSensor)
        with patch.object(base, "async_add_external_statistics", return_value=None) as external:
            await sensor._async_inject_statistics()
        own_import = next(call for call in external.call_args_list
                          if call.args[1]["statistic_id"] == "mijnted:test_entry_monthly_usage")
        metadata, rows = own_import.args[1:]
        assert metadata["statistic_id"] == "mijnted:test_entry_monthly_usage"
        assert metadata["name"] == "Published usage"
        assert rows == [{"start": datetime(2026, 10, 1, tzinfo=ZONE), "mean": 41}]

    async def test_consolidated_report_alone_exports_all_four_screenshot_lines(self, clock):
        """Only Published usage active -> four independently selectable October graph series."""
        cache = {"2026-10": month_entry(10, start=829, end=870, published=41),
                 "2025-10": month_entry(10, year=2025, start=500, end=517, published=17)}
        cache["2025-10"].average_usage = 181.01
        sensor = make_sensor(cache, usage.MijnTedPublishedUsageSensor, last_update="2026-10-31")
        sensor.coordinator.data["daily_usage"] = {"2026-11-06": 3}
        attributes = sensor.extra_state_attributes
        assert sensor.state == 41
        assert attributes["month_id"] == "10.2026"
        assert attributes["reading_date"] == "2026-10-31"
        assert "average_monthly_usage" not in attributes
        assert "last_year_monthly_usage" not in attributes
        assert attributes["reported_daily_usage"] == 3
        assert attributes["reported_daily_date"] == "2026-11-06"
        with patch.object(base, "async_add_external_statistics", return_value=None) as external:
            await sensor._async_inject_statistics()
        imports = {call.args[1]["statistic_id"]: (call.args[1], call.args[2])
                   for call in external.call_args_list}
        expected = {
            attributes["monthly_statistic_id"]: 41,
            "mijnted:test_entry_average_monthly_usage": 139.05,
            "mijnted:test_entry_last_year_monthly_usage": 17,
            "mijnted:test_entry_last_year_average_monthly_usage": 181.01,
        }
        expected_names = {
            "mijnted:test_entry_monthly_usage": "Published usage",
            "mijnted:test_entry_average_monthly_usage": "Average monthly usage",
            "mijnted:test_entry_last_year_monthly_usage": "Last year monthly usage",
            "mijnted:test_entry_last_year_average_monthly_usage": "Last year average monthly usage",
        }
        for statistic_id, expected_value in expected.items():
            metadata, imported = imports[statistic_id]
            assert metadata["name"] == expected_names[statistic_id]
            rows = [{**row, "start": row["start"].timestamp()} for row in imported]
            same_month, period = reduce_month_ts_factory()
            reduced = _reduce_statistic(statistic_id, rows, same_month, period, {"mean"}, {statistic_id: (1, metadata)})
            october = next(row for row in reduced if row["start"] == datetime(2026, 10, 1, tzinfo=ZONE).timestamp())
            assert october["mean"] == expected_value
        assert imports[attributes["daily_statistic_id"]][1] == [
            {"start": datetime(2026, 11, 6, tzinfo=ZONE), "mean": 3},
        ]

    def test_each_view_owns_its_period_metadata_from_shared_coordinator_data(self, clock):
        """November readings and October average -> each entity identifies its own period."""
        cache = {"2026-10": month_entry(10, start=829, end=870, published=41),
                 "2026-11": month_entry(11, start=870, end=888),
                 "2025-11": month_entry(11, year=2025, start=100, end=293, published=193)}
        sensor = make_sensor(cache, usage.MijnTedPublishedUsageSensor)
        sensor.coordinator.data["reading_report"].update({
            "average_monthly_usage": 999, "last_year_month_id": "1.2000",
        })
        attributes = sensor.extra_state_attributes
        average = make_sensor(cache, usage.MijnTedAverageMonthlyUsageSensor)
        # Current provisional month does not have a published building average.
        cache["2026-11"].average_usage = None
        previous = make_sensor(cache, usage.MijnTedLastYearMonthlyUsageSensor)
        assert sensor.state == 18
        assert attributes["month_id"] == "11.2026"
        assert "average_monthly_usage" not in attributes
        assert "last_year_month_id" not in attributes
        assert not any(key.startswith(("average_", "last_year_")) for key in attributes)
        assert average.state == 139.05
        assert average.extra_state_attributes["month_id"] == "10.2026"
        assert previous.state == 193
        assert previous.extra_state_attributes["last_year_month_id"] == "11.2025"

    @pytest.mark.parametrize("sensor_class", [usage.MijnTedLastYearMonthlyUsageSensor,
                                             usage.MijnTedLastYearAverageMonthlyUsageSensor])
    def test_comparison_view_does_not_depend_on_current_meter_data(self, clock, sensor_class):
        """A historical comparison cache is valid even when current meter endpoints are empty."""
        cache = {"2025-11": month_entry(11, year=2025, start=100, end=293, published=193)}
        sensor = make_sensor(cache, sensor_class)
        sensor.coordinator.data.update({"filter_status": [], "last_update": {}})
        expected = 193 if sensor_class is usage.MijnTedLastYearMonthlyUsageSensor else 139.05
        assert sensor.state == expected
        assert sensor.extra_state_attributes["last_year_month_id"] == "11.2025"

    @pytest.mark.parametrize("sensor_class", [usage.MijnTedLastYearMonthlyUsageSensor,
                                             usage.MijnTedLastYearAverageMonthlyUsageSensor])
    def test_comparison_value_cannot_bleed_into_a_different_period(self, clock, sensor_class):
        """November's last-known comparison is not presented under December metadata."""
        cache = {"2025-11": month_entry(11, year=2025, start=100, end=293, published=193)}
        sensor = make_sensor(cache, sensor_class)
        assert sensor.state is not None
        clock.return_value = datetime(2026, 12, 1, tzinfo=ZONE)
        assert sensor.state is None
        assert sensor.extra_state_attributes["last_year_month_id"] == "12.2025"

    @pytest.mark.parametrize(("year", "month"), [(2026, 10), (2026, 3), (2028, 2), (2027, 1)])
    async def test_real_ha_reducer_keeps_corrected_month_separate_from_stale_entity(self, clock, year, month):
        """Actual HA monthly reduction -> legacy state 39 cannot hide external total 41."""
        first = datetime(year, month, 1, tzinfo=ZONE)
        last = coordinator.DateUtil.get_last_day_of_month(month, year)
        last_hour = datetime(year, month, last.day, 23, tzinfo=ZONE)
        clock.return_value = last_hour + timedelta(days=2)
        cache = {f"{year}-{month:02}": month_entry(month, year=year, start=829, end=870, published=41)}
        sensor = make_sensor(cache)
        with patch.object(base, "async_add_external_statistics", return_value=None) as external:
            await sensor._async_inject_statistics()
        metadata, imported = external.call_args.args[1:]
        statistic_id = metadata["statistic_id"]
        legacy_rows = [{"start": first.timestamp(), "state": 41},
                       {"start": last_hour.timestamp(), "state": 39}]
        same_month, period = reduce_month_ts_factory()
        legacy = _reduce_statistic(sensor.entity_id, legacy_rows, same_month, period, {"state"}, {})
        assert legacy[0]["state"] == 39  # Reproduces the old graph's failure mode.
        rows = [{**row, "start": row["start"].timestamp()} for row in imported]
        same_month, period = reduce_month_ts_factory()
        corrected = _reduce_statistic(statistic_id, rows, same_month, period, {"mean"}, {statistic_id: (1, metadata)})
        assert corrected[0]["start"] == first.timestamp()
        assert corrected[0]["mean"] == 41
