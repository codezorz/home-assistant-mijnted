"""Tests for late historical-month statistics reinjection behavior.

Validates that corrected historical month values produce reinjection hints and
that statistics dedupe allows one-time reinjection for those hinted periods.
"""
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import custom_components.mijnted.__init__ as init_mod
from custom_components.mijnted.sensors.base import MijnTedSensor
from custom_components.mijnted.sensors.models import (
    DeviceReading,
    MonthCacheEntry,
    MONTH_STATE_OPEN,
    StatisticsTracking,
)
from custom_components.mijnted.sensors.usage import (
    MijnTedMonthlyUsageSensor,
)
from custom_components.mijnted.utils import DateUtil


def _make_cache_entry(month, year, *, total_usage, average_usage):
    """Build a minimal historical MonthCacheEntry for testing."""
    return MonthCacheEntry(
        month_id=DateUtil.format_month_year_key(month, year),
        year=year,
        month=month,
        start_date=DateUtil.format_date_for_api(DateUtil.get_first_day_of_month(month, year)),
        end_date=DateUtil.format_date_for_api(DateUtil.get_last_day_of_month(month, year)),
        total_usage=total_usage,
        average_usage=average_usage,
        devices=[DeviceReading(id=1, start=0.0, end=total_usage or 0.0, usage=total_usage)],
        finalized=False,
        state=MONTH_STATE_OPEN,
        start_locked=False,
    )


class TestEnsureMonthlyHistoryCacheStatisticsReinject:
    """Verify reinjection-hint detection and merge in _ensure_monthly_history_cache."""

    async def test_previous_month_total_change_sets_monthly_reinject_hint(self):
        """Historical total change -> monthly_usage hint contains corrected month."""
        api = AsyncMock()
        hass = MagicMock()
        hass.data = {}
        entry = MagicMock()
        entry.entry_id = "test_entry"
        cache = {"2026-02": _make_cache_entry(2, 2026, total_usage=245.0, average_usage=10.0)}

        async def _mutate_cache(*args, **kwargs):
            monthly_history_cache = args[1]
            monthly_history_cache["2026-02"].total_usage = 250.0
            return (True, False)

        with (
            patch.object(init_mod, "_load_cache_from_coordinator", return_value=({}, "2026-03-01")),
            patch.object(init_mod, "_load_or_build_cache", new_callable=AsyncMock, return_value=(cache, False)),
            patch.object(init_mod, "_update_and_enrich_cache", new_callable=AsyncMock, side_effect=_mutate_cache),
            patch.object(init_mod, "_save_persisted_cache", new_callable=AsyncMock),
            patch.object(init_mod, "_get_or_create_statistics_tracking", return_value=StatisticsTracking()),
        ):
            _, _, _, statistics_reinject = await init_mod._ensure_monthly_history_cache(
                api,
                hass,
                entry,
                last_update={"lastSyncDate": "2026-03-02"},
                energy_usage_data={},
                filter_status=[],
            )

        assert statistics_reinject == {"monthly_usage": ["2.2026"]}

    async def test_existing_pending_hints_are_merged_with_new_detection(self):
        """Existing pending hint + new correction -> merged hint set is returned."""
        api = AsyncMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"
        existing_coordinator = MagicMock()
        existing_coordinator.data = {
            "statistics_reinject": {
                "monthly_usage": ["1.2026"],
                "average_monthly_usage": ["1.2026"],
                "last_year_average_monthly_usage": ["1.2026"],
            }
        }
        hass = MagicMock()
        hass.data = {
            init_mod.DOMAIN: {
                entry.entry_id: existing_coordinator,
            }
        }
        cache = {"2026-02": _make_cache_entry(2, 2026, total_usage=245.0, average_usage=10.0)}

        async def _mutate_cache(*args, **kwargs):
            monthly_history_cache = args[1]
            monthly_history_cache["2026-02"].total_usage = 250.0
            return (True, False)

        with (
            patch.object(init_mod, "_load_cache_from_coordinator", return_value=({}, "2026-03-01")),
            patch.object(init_mod, "_load_or_build_cache", new_callable=AsyncMock, return_value=(cache, False)),
            patch.object(init_mod, "_update_and_enrich_cache", new_callable=AsyncMock, side_effect=_mutate_cache),
            patch.object(init_mod, "_save_persisted_cache", new_callable=AsyncMock),
            patch.object(init_mod, "_get_or_create_statistics_tracking", return_value=StatisticsTracking()),
        ):
            _, _, _, statistics_reinject = await init_mod._ensure_monthly_history_cache(
                api,
                hass,
                entry,
                last_update={"lastSyncDate": "2026-03-02"},
                energy_usage_data={},
                filter_status=[],
            )

        assert statistics_reinject == {"monthly_usage": ["1.2026", "2.2026"]}

    async def test_average_change_updates_cache_without_legacy_reinject_hint(self):
        """Late average -> updated cache, without obsolete entity-statistics hints."""
        api = AsyncMock()
        hass = MagicMock()
        hass.data = {}
        entry = MagicMock()
        entry.entry_id = "test_entry"
        cache = {"2026-02": _make_cache_entry(2, 2026, total_usage=245.0, average_usage=None)}

        async def _mutate_cache(*args, **kwargs):
            monthly_history_cache = args[1]
            monthly_history_cache["2026-02"].average_usage = 12.5
            return (True, False)

        with (
            patch.object(init_mod, "_load_cache_from_coordinator", return_value=({}, "2026-03-01")),
            patch.object(init_mod, "_load_or_build_cache", new_callable=AsyncMock, return_value=(cache, False)),
            patch.object(init_mod, "_update_and_enrich_cache", new_callable=AsyncMock, side_effect=_mutate_cache),
            patch.object(init_mod, "_save_persisted_cache", new_callable=AsyncMock),
            patch.object(init_mod, "_get_or_create_statistics_tracking", return_value=StatisticsTracking()),
        ):
            updated_cache, _, _, statistics_reinject = await init_mod._ensure_monthly_history_cache(
                api,
                hass,
                entry,
                last_update={"lastSyncDate": "2026-03-02"},
                energy_usage_data={},
                filter_status=[],
            )

        assert updated_cache["2026-02"].average_usage == 12.5
        assert statistics_reinject == {}


class TestStatisticsReinjectDedupBypass:
    """Verify dedupe bypass and one-time reinjection consumption in sensor base."""

    @staticmethod
    def _make_sensor(sensor_type: str = "monthly_usage") -> MijnTedSensor:
        """Build a MijnTedSensor instance without running the full HA entity init."""
        sensor = object.__new__(MijnTedSensor)
        sensor.sensor_type = sensor_type
        sensor._name = "monthly usage"
        sensor._attr_unique_id = "mijnted_monthly_usage"
        sensor._last_known_value = None
        sensor.coordinator = MagicMock()
        sensor.coordinator.data = {}
        return sensor

    async def test_reinject_hint_bypasses_already_injected_guard(self):
        """Reinject hint for a period -> _has_already_injected_period returns False."""
        sensor = self._make_sensor()
        sensor.coordinator.data = {
            "statistics_tracking": StatisticsTracking(monthly_usage="3.2026"),
            "statistics_reinject": {"monthly_usage": ["2.2026"]},
        }

        result = await sensor._has_already_injected_period(datetime(2026, 2, 1))

        assert result is False

    async def test_without_reinject_hint_period_is_still_considered_injected(self):
        """No reinject hint and period <= last_injected -> _has_already_injected_period is True."""
        sensor = self._make_sensor()
        sensor.coordinator.data = {
            "statistics_tracking": StatisticsTracking(monthly_usage="3.2026"),
        }

        result = await sensor._has_already_injected_period(datetime(2026, 2, 1))

        assert result is True

    @patch("custom_components.mijnted.sensors.base.datetime")
    async def test_current_month_always_bypasses_injection_guard(self, mock_dt):
        """Current calendar month -> _has_already_injected_period returns False."""
        mock_dt.now.return_value = datetime(2026, 4, 7)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        sensor = self._make_sensor()
        sensor.coordinator.data = {
            "statistics_tracking": StatisticsTracking(monthly_usage="4.2026"),
        }

        result = await sensor._has_already_injected_period(datetime(2026, 4, 1))

        assert result is False, (
            "Current month must always allow re-injection to keep charts up-to-date"
        )

    async def test_successful_finalize_consumes_reinjected_months(self):
        """Successful import with reinjected month -> consumed hint is removed."""
        sensor = self._make_sensor()
        tracking = StatisticsTracking(monthly_usage="2.2026")
        sensor.coordinator.data = {
            "statistics_tracking": tracking,
            "statistics_reinject": {"monthly_usage": ["1.2026", "2.2026"]},
        }
        consumed_reinject_months = {"2.2026"}

        with (
            patch.object(sensor, "_create_statistics_metadata", return_value=MagicMock()),
            patch.object(sensor, "_async_safe_import_statistics", new_callable=AsyncMock, return_value=True),
        ):
            await sensor._finalize_statistics_injection(
                statistics=[MagicMock()],
                mean_type=MagicMock(),
                max_month_key="3.2026",
                consumed_reinject_months=consumed_reinject_months,
            )

        assert sensor.coordinator.data["statistics_reinject"] == {"monthly_usage": ["1.2026"]}
        assert tracking.monthly_usage == "3.2026"

    async def test_consumption_is_scoped_to_sensor_type(self):
        """Monthly finalize consumes its own hints and keeps last-year hints."""
        sensor = self._make_sensor()
        tracking = StatisticsTracking(monthly_usage="2.2026")
        sensor.coordinator.data = {
            "statistics_tracking": tracking,
            "statistics_reinject": {
                "last_year_monthly_usage": ["1.2026"],
                "monthly_usage": ["1.2026", "2.2026"],
            },
        }
        consumed_reinject_months = {"2.2026"}

        with (
            patch.object(sensor, "_create_statistics_metadata", return_value=MagicMock()),
            patch.object(sensor, "_async_safe_import_statistics", new_callable=AsyncMock, return_value=True),
        ):
            await sensor._finalize_statistics_injection(
                statistics=[MagicMock()],
                mean_type=MagicMock(),
                max_month_key="3.2026",
                consumed_reinject_months=consumed_reinject_months,
            )

        assert sensor.coordinator.data["statistics_reinject"] == {
            "last_year_monthly_usage": ["1.2026"],
            "monthly_usage": ["1.2026"],
        }
        assert tracking.monthly_usage == "3.2026"


class TestMonthlyUsagePartialResponse:
    """Verify live values and recorder imports retain unobserved device usage."""

    async def test_partial_response_and_recovery_use_matching_totals(self):
        """Partial then complete response -> cache, live state, and recorder agree."""
        now = datetime(2026, 4, 3, 12)
        previous = _make_cache_entry(3, 2026, total_usage=22.0, average_usage=10.0)
        current = _make_cache_entry(4, 2026, total_usage=13.0, average_usage=None)
        current.devices = [
            DeviceReading(id=1001, start=698.0, end=707.0),
            DeviceReading(id=1002, start=116.0, end=120.0),
        ]
        current.start_locked = True
        cache = {"2026-03": previous, "2026-04": current}
        partial_status = [{"deviceNumber": "1001", "currentReadingValue": 710.0}]
        await init_mod._update_current_month_cache(
            AsyncMock(), cache, partial_status, {"lastSyncDate": "2026-04-03"}, {}, now
        )
        assert cache["2026-04"].total_usage == 16.0

        coordinator = SimpleNamespace(data={
            "filter_status": partial_status,
            "last_update": {"lastSyncDate": "2026-04-03"},
            "monthly_history_cache": cache,
            "statistics_tracking": StatisticsTracking(monthly_usage="4.2026"),
        })
        sensor = MijnTedMonthlyUsageSensor(coordinator, "test_entry")
        sensor.entity_id = "sensor.home_monthly_usage"
        sensor.hass = MagicMock()
        sensor.hass.config.components = {"recorder"}

        with (
            patch("custom_components.mijnted.sensors.base.date") as mock_date,
            patch("custom_components.mijnted.sensors.base.datetime", wraps=datetime) as mock_datetime,
            patch("custom_components.mijnted.sensors.base.StatisticData", side_effect=lambda **kwargs: kwargs),
            patch("custom_components.mijnted.sensors.base.async_import_statistics", return_value=None) as import_statistics,
        ):
            mock_date.today.return_value = date(2026, 4, 3)
            mock_date.side_effect = date
            mock_datetime.now.return_value = now

            assert sensor.state == 16.0
            current_data = sensor._build_current_data()
            assert current_data.total_usage_start == 814.0
            assert current_data.total_usage_end == 830.0
            await sensor._async_inject_statistics()
            statistics = import_statistics.call_args.args[2]
            assert [stat["state"] for stat in statistics] == [16.0]

            coordinator.data["filter_status"] = [
                {"deviceNumber": "1001", "currentReadingValue": 710.0},
                {"deviceNumber": "1002", "currentReadingValue": 122.0},
            ]
            assert sensor.state == 18.0
            await sensor._async_inject_statistics()
            statistics = import_statistics.call_args.args[2]
            assert [stat["state"] for stat in statistics] == [18.0]

            coordinator.data["filter_status"] = []
            assert sensor.state == 18.0
