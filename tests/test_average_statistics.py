"""Regression coverage for import-only, consumption-month building averages."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.recorder.models import StatisticMeanType

import custom_components.mijnted.__init__ as init_mod
from custom_components.mijnted.sensors import base
from custom_components.mijnted.sensors.models import StatisticsTracking
from custom_components.mijnted.sensors.usage import (
    MijnTedAverageMonthlyUsageSensor,
    MijnTedLastYearAverageMonthlyUsageSensor,
    MijnTedLastYearMonthlyUsageSensor,
    MijnTedMonthlyUsageSensor,
)
from custom_components.mijnted.utils import DateUtil


def _cache_entry(month_key, average):
    """Build a cache period usable by both the live sensor and recorder imports."""
    year, month = DateUtil.parse_month_key(month_key)
    return {
        "month_id": f"{month}.{year}",
        "year": year,
        "month": month,
        "start_date": f"{month_key}-01",
        "end_date": DateUtil.get_last_day_of_month(month, year).isoformat(),
        "average_usage": average,
        "total_usage": 0.0,
        "devices": [],
    }


def _sensor(cache, sensor_class=MijnTedAverageMonthlyUsageSensor, entry_id="test_entry"):
    """Create a sensor with recorder loaded and no live meter response."""
    coordinator = SimpleNamespace(data={
        "monthly_history_cache": cache,
        "statistics_tracking": StatisticsTracking(),
    })
    sensor = sensor_class(coordinator, entry_id, config_name="Home")
    sensor.entity_id = f"sensor.home_{sensor.sensor_type}"
    sensor.hass = MagicMock()
    sensor.hass.config.components = {"recorder"}
    return sensor


@pytest.fixture
def recorder():
    """Capture actual import payloads while freezing HA's local calendar."""
    with (
        patch.object(base, "StatisticData", side_effect=lambda **kwargs: kwargs),
        patch.object(base, "StatisticMetaData", side_effect=lambda **kwargs: kwargs),
        patch.object(base, "async_add_external_statistics", return_value=None) as external,
        patch.object(base, "async_import_statistics", return_value=None) as internal,
        patch.object(base, "date", wraps=date) as local_date,
        patch.object(base, "dt_util") as dt_util,
    ):
        local_date.today.return_value = date(2026, 4, 6)
        dt_util.now.return_value = datetime(2026, 4, 6, tzinfo=timezone.utc)
        dt_util.get_default_time_zone.return_value = timezone.utc
        yield SimpleNamespace(external=external, internal=internal, dt_util=dt_util)


class TestAverageMonthlyStatistics:
    """Keep late-published monthly values separate from collection-time states."""

    async def test_late_publication_keeps_march_average_in_march(self, recorder):
        """April publication -> March mean, even while the April live state changes."""
        cache = {
            "2026-02": _cache_entry("2026-02", 629.46),
            "2026-03": _cache_entry("2026-03", None),
            "2026-04": _cache_entry("2026-04", None),
        }
        sensor = _sensor(cache)
        assert sensor.state == 629.46
        await sensor._async_inject_statistics()

        cache["2026-03"]["average_usage"] = 306.25
        await sensor._async_inject_statistics()

        metadata, statistics = recorder.external.call_args.args[1:]
        assert metadata["statistic_id"] == sensor.extra_state_attributes["monthly_statistic_id"]
        assert metadata["statistic_id"] == "mijnted:test_entry_average_monthly_usage"
        assert metadata["source"] == "mijnted"
        assert metadata["mean_type"] == StatisticMeanType.ARITHMETIC
        assert metadata["has_sum"] is False
        assert metadata["unit_of_measurement"] == "Units"
        assert [(row["start"].month, row["mean"]) for row in statistics] == [
            (2, 629.46), (3, 306.25),
        ]
        assert all(row["start"].day == 1 for row in statistics)
        assert all(set(row) == {"start", "mean"} for row in statistics)
        assert sensor.state == 306.25
        assert sensor.extra_state_attributes["month_id"] == "3.2026"

        assert sensor.state_class is None
        recorder.internal.assert_not_called()

    async def test_historical_api_readings_are_backfilled_into_external_statistics(self, recorder):
        """API history -> monthly cache -> correctly dated external means."""
        api = AsyncMock()
        api.get_device_statuses_for_date.return_value = [
            {"deviceNumber": "1", "currentReadingValue": 100.0},
        ]
        api.get_energy_usage.return_value = {"monthlyEnergyUsages": [
            {"monthYear": "2.2026", "averageEnergyUseForBillingUnit": 629.46},
            {"monthYear": "3.2026", "averageEnergyUseForBillingUnit": 306.25},
        ]}
        with (
            patch.object(init_mod, "CACHE_HISTORY_MONTHS", 2),
            patch.object(DateUtil, "is_current_month", return_value=False),
        ):
            cache = await init_mod._build_initial_monthly_history_cache(
                api, {"lastSyncDate": "2026-04-06"}, {}, datetime(2026, 4, 6),
            )

        assert set(cache) == {"2026-02", "2026-03"}
        assert api.get_energy_usage.await_count == 2
        assert all(call.args == (2026,) for call in api.get_energy_usage.await_args_list)
        sensor = _sensor(cache)
        await sensor._async_inject_statistics()
        statistics = recorder.external.call_args.args[2]
        assert [(row["start"].month, row["mean"]) for row in statistics] == [
            (2, 629.46), (3, 306.25),
        ]
        recorder.internal.assert_not_called()

    async def test_upgrade_and_corrections_ignore_legacy_injection_tracking(self, recorder):
        """Already tracked month with no hint -> new series still backfills and corrects."""
        cache = {"2026-02": _cache_entry("2026-02", 12.5)}
        sensor = _sensor(cache)
        sensor.coordinator.data["statistics_tracking"] = {"average_monthly_usage": "4.2026"}

        await sensor._async_inject_statistics()
        assert recorder.external.call_args.args[2][0]["mean"] == 12.5
        cache["2026-02"]["average_usage"] = 13.0
        await sensor._async_inject_statistics()

        assert recorder.external.call_args.args[2][0]["mean"] == 13.0
        assert recorder.external.call_count == 2
        recorder.internal.assert_not_called()

    async def test_restart_and_entity_rename_reuse_external_id(self, recorder):
        """Recreated renamed entity -> same external series and refreshed cached value."""
        cache = {"2026-03": _cache_entry("2026-03", 306.25)}
        sensor = _sensor(cache, entry_id="01ABCDEF")
        await sensor._async_inject_statistics()
        original_id = recorder.external.call_args.args[1]["statistic_id"]

        restarted = _sensor(cache, entry_id="01ABCDEF")
        restarted.entity_id = "sensor.renamed_building_average"
        await restarted._async_inject_statistics()

        assert original_id == "mijnted:01abcdef_average_monthly_usage"
        assert recorder.external.call_args.args[1]["statistic_id"] == original_id
        assert recorder.external.call_args.args[2][0]["mean"] == 306.25

    async def test_config_entries_have_independent_series(self, recorder):
        """Same device name in two entries -> different IDs and average values."""
        first = _sensor({"2026-03": _cache_entry("2026-03", 10.0)}, entry_id="first")
        second = _sensor({"2026-03": _cache_entry("2026-03", 20.0)}, entry_id="second")
        await first._async_inject_average_statistics()
        await second._async_inject_average_statistics()

        calls = recorder.external.call_args_list
        assert {call.args[1]["statistic_id"] for call in calls} == {
            "mijnted:first_average_monthly_usage", "mijnted:second_average_monthly_usage",
        }
        assert [call.args[2][0]["mean"] for call in calls] == [10.0, 20.0]

    @pytest.mark.parametrize("missing", [None, "invalid", float("nan"), float("inf")])
    async def test_zero_is_imported_but_missing_and_invalid_values_are_not(self, recorder, missing):
        """Valid zero -> a monthly point; invalid average -> no fabricated point."""
        sensor = _sensor({
            "2026-01": _cache_entry("2026-01", 0),
            "2026-02": _cache_entry("2026-02", missing),
            "2026-04": _cache_entry("2026-04", 123),
            "2026-05": _cache_entry("2026-05", 456),
            "invalid": {"average_usage": 100},
            "2026-00": {"average_usage": 100},
        })
        await sensor._async_inject_average_statistics()

        statistics = recorder.external.call_args.args[2]
        assert len(statistics) == 1
        assert statistics[0]["mean"] == 0.0
        assert statistics[0]["start"] == datetime(2026, 1, 1, tzinfo=timezone.utc)

    async def test_import_failure_retries_on_next_refresh(self, recorder, caplog):
        """Recorder rejects first import -> warning and another attempt on refresh."""
        sensor = _sensor({"2026-03": _cache_entry("2026-03", 306.25)})
        recorder.external.side_effect = [RuntimeError("recorder not ready"), None]
        await sensor._async_inject_average_statistics()
        await sensor._async_inject_average_statistics()

        assert recorder.external.call_count == 2
        assert "recorder not ready" in caplog.text
        assert "mijnted:test_entry_average_monthly_usage" in caplog.text

    async def test_month_start_uses_ha_local_time_zone(self, recorder):
        """UTC-negative local month start -> point stays in its intended local month."""
        local_zone = timezone(timedelta(hours=-7))
        recorder.dt_util.get_default_time_zone.return_value = local_zone
        sensor = _sensor({"2026-03": _cache_entry("2026-03", 306.25)})
        await sensor._async_inject_average_statistics()

        start = recorder.external.call_args.args[2][0]["start"]
        assert start == datetime(2026, 3, 1, 7, tzinfo=timezone.utc)
        assert start.astimezone(local_zone).day == 1

    @pytest.mark.parametrize("cache", [{}, None])
    async def test_no_cache_still_exposes_id_without_importing(self, recorder, cache):
        """No monthly data -> discoverable graph ID, without placeholder statistics."""
        sensor = _sensor(cache)
        await sensor._async_inject_average_statistics()

        assert sensor.extra_state_attributes == {
            "monthly_statistic_id": "mijnted:test_entry_average_monthly_usage",
        }
        recorder.external.assert_not_called()

    async def test_recorder_not_loaded_skips_external_import(self, recorder):
        """Recorder missing -> no import is queued."""
        sensor = _sensor({"2026-03": _cache_entry("2026-03", 306.25)})
        sensor.hass.config.components = set()
        await sensor._async_inject_average_statistics()
        recorder.external.assert_not_called()


class TestLastYearAverageStatistics:
    """Align previous-year averages to the comparison month without live fallbacks."""

    async def test_previous_year_values_shift_to_current_comparison_periods(self, recorder):
        """March/April last year -> March/April this year; May is not imported early."""
        sensor = _sensor({
            "2025-03": _cache_entry("2025-03", 700.0),
            "2025-04": _cache_entry("2025-04", 500.0),
            "2025-05": _cache_entry("2025-05", 400.0),
        }, MijnTedLastYearAverageMonthlyUsageSensor)
        await sensor._async_inject_statistics()

        metadata, statistics = recorder.external.call_args.args[1:]
        assert metadata["statistic_id"] == "mijnted:test_entry_last_year_average_monthly_usage"
        assert [(row["start"].year, row["start"].month, row["mean"]) for row in statistics] == [
            (2026, 3, 700.0), (2026, 4, 500.0),
        ]
        assert sensor.extra_state_attributes["monthly_statistic_id"] == metadata["statistic_id"]
        assert sensor.state_class is None
        recorder.internal.assert_not_called()

    async def test_january_rollover_keeps_last_year_january_in_january(self, recorder):
        """January comparison -> last January's average, not last December's."""
        recorder.dt_util.now.return_value = datetime(2026, 1, 2, tzinfo=timezone.utc)
        sensor = _sensor({
            "2025-01": _cache_entry("2025-01", 800.0),
            "2025-12": _cache_entry("2025-12", 900.0),
        }, MijnTedLastYearAverageMonthlyUsageSensor)
        await sensor._async_inject_average_statistics(year_offset=1)

        statistics = recorder.external.call_args.args[2]
        assert len(statistics) == 1
        assert statistics[0]["start"] == datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert statistics[0]["mean"] == 800.0

    async def test_missing_average_does_not_import_stale_live_fallback(self, recorder):
        """Live fallback retained -> no copied previous-period value in monthly series."""
        sensor = _sensor({
            "2025-04": _cache_entry("2025-04", None),
        }, MijnTedLastYearAverageMonthlyUsageSensor)
        sensor._last_known_value = 700.0
        assert sensor.state == 700.0
        await sensor._async_inject_average_statistics(year_offset=1)
        recorder.external.assert_not_called()


class TestMixedMonthlyGraph:
    """Keep both usage states and imported averages available to one graph."""

    async def test_four_series_advertise_state_and_mean_after_import(self, recorder):
        """Completed month -> two queryable usage states and two average means."""
        cache = {
            "2025-03": _cache_entry("2025-03", 181.0),
            "2026-03": _cache_entry("2026-03", 306.25),
        }
        cache["2025-03"]["total_usage"] = 17.0
        cache["2026-03"]["total_usage"] = 39.0
        for sensor_class in (
            MijnTedMonthlyUsageSensor,
            MijnTedLastYearMonthlyUsageSensor,
            MijnTedAverageMonthlyUsageSensor,
            MijnTedLastYearAverageMonthlyUsageSensor,
        ):
            await _sensor(cache, sensor_class)._async_inject_statistics()

        imports = {
            call.args[1]["statistic_id"]: (call.args[1], call.args[2])
            for call in recorder.internal.call_args_list + recorder.external.call_args_list
        }
        expected = {
            "sensor.home_monthly_usage": ("state", 39.0),
            "sensor.home_last_year_monthly_usage": ("state", 17.0),
            "mijnted:test_entry_average_monthly_usage": ("mean", 306.25),
            "mijnted:test_entry_last_year_average_monthly_usage": ("mean", 181.0),
        }
        assert set(imports) == set(expected)
        for statistic_id, (stat_type, value) in expected.items():
            metadata, statistics = imports[statistic_id]
            if stat_type == "state":
                # HA gates state queries on has_sum, even for state-only imports.
                assert metadata["has_sum"] is True
                assert metadata["mean_type"] == StatisticMeanType.NONE
            else:
                assert metadata["has_sum"] is False
                assert metadata["mean_type"] == StatisticMeanType.ARITHMETIC
            march = next(
                row for row in statistics
                if row["start"] == datetime(2026, 3, 1, tzinfo=timezone.utc)
            )
            assert march[stat_type] == value


class TestAverageStatisticDisplayNames:
    """Match statistic labels to the existing sentence-cased sensor names."""

    @pytest.mark.parametrize(("sensor_class", "expected_name", "statistic_id"), [
        (
            MijnTedAverageMonthlyUsageSensor,
            "Average monthly usage",
            "mijnted:test_entry_average_monthly_usage",
        ),
        (
            MijnTedLastYearAverageMonthlyUsageSensor,
            "Last year average monthly usage",
            "mijnted:test_entry_last_year_average_monthly_usage",
        ),
    ])
    async def test_names_match_sensors_without_changing_series_on_rename(
        self, recorder, sensor_class, expected_name, statistic_id,
    ):
        """Initial import and device rename -> same sentence-cased label, ID and data."""
        sensor = _sensor({"2025-03": _cache_entry("2025-03", 181.0)}, sensor_class)
        unique_id = sensor._attr_unique_id
        await sensor._async_inject_statistics()

        metadata, statistics = recorder.external.call_args.args[1:]
        assert metadata["name"] == expected_name == sensor.name
        assert metadata["statistic_id"] == statistic_id

        sensor._config_name = "Office"
        sensor.entity_id = f"sensor.renamed_{sensor.sensor_type}"
        await sensor._async_inject_statistics()

        renamed_metadata, reimported_statistics = recorder.external.call_args.args[1:]
        assert renamed_metadata["name"] == expected_name
        assert renamed_metadata["statistic_id"] == statistic_id
        assert sensor._attr_unique_id == unique_id
        assert reimported_statistics == statistics
