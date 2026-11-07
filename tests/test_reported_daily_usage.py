"""Forward-only daily observations, restart continuity, and dated graph imports."""

from datetime import datetime
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.mijnted import daily
from custom_components.mijnted.sensors import base
from custom_components.mijnted.sensors.usage import MijnTedPublishedUsageSensor
from custom_components.mijnted.sensors.usage import MijnTedMonthlyUsageSensor
from custom_components.mijnted.sensors.models import DeviceReading, MonthCacheEntry
from custom_components.mijnted.utils.readings import build_reading_report

ZONE = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 11, 10, 12, tzinfo=ZONE)


def rows(*values):
    """Return complete readings for synthetic meter IDs."""
    return [{"deviceNumber": str(index + 1), "currentReadingValue": value}
            for index, value in enumerate(values)]


@pytest.fixture
def store():
    """Serialize snapshots like real HA storage, including stringified map keys."""
    snapshot = None
    async def save(value):
        """Capture a detached JSON snapshot instead of a mutable reference."""
        nonlocal snapshot
        snapshot = json.loads(json.dumps(value))
    async def load():
        """Return the latest persisted state on reload."""
        return snapshot
    instance = MagicMock(async_save=AsyncMock(side_effect=save), async_load=AsyncMock(side_effect=load))
    with patch.object(daily, "Store", return_value=instance):
        yield instance


class TestForwardDailyTracking:
    """Compute a day only from consecutive, compatible newly received dates."""

    async def test_first_observation_only_seeds_then_next_day_is_recorded(self, store):
        """November 6 baseline, November 7 readings -> only November 7 consumption."""
        tracker = daily.DailyUsageTracker(MagicMock(), "test_entry")
        assert await tracker.async_update("2026-11-06", rows(100, 200), NOW, {1, 2}) == {}
        values = await tracker.async_update("2026-11-07", rows(102, 201), NOW, {1, 2})
        assert values == {"2026-11-07": 3}
        assert "2026-11-06" not in values

    async def test_repeated_latest_date_corrects_the_same_day_after_restart(self, store):
        """Restart then revised November 7 reading -> replace November 7 total, not today."""
        tracker = daily.DailyUsageTracker(MagicMock(), "test_entry")
        await tracker.async_update("2026-11-06", rows(100), NOW, {1})
        await tracker.async_update("2026-11-07", rows(103), NOW, {1})
        tracker = daily.DailyUsageTracker(MagicMock(), "test_entry")
        values = await tracker.async_update("2026-11-07", rows(102), NOW, {1})
        assert values == {"2026-11-07": 2}
        store.async_save.reset_mock()
        assert await tracker.async_update("2026-11-07", rows(102), NOW, {1}) == values
        store.async_save.assert_not_awaited()

    async def test_failed_save_is_retried_for_an_unchanged_reading(self, store):
        """Transient write failure -> unchanged next poll persists the checkpoint for restart."""
        save = store.async_save.side_effect
        attempts = 0
        async def flaky_save(value):
            """Fail the first write and allow subsequent persistence."""
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise OSError("temporary storage error")
            await save(value)
        store.async_save.side_effect = flaky_save
        tracker = daily.DailyUsageTracker(MagicMock(), "test_entry")
        await tracker.async_update("2026-11-06", rows(100), NOW, {1})
        await tracker.async_update("2026-11-06", rows(100), NOW, {1})
        restored = daily.DailyUsageTracker(MagicMock(), "test_entry")
        assert await restored.async_update("2026-11-07", rows(103), NOW, {1}) == {"2026-11-07": 3}

    async def test_failed_load_is_retried_without_overwriting_saved_results(self, store):
        """Transient restore failure -> defer observations until saved history can be loaded."""
        stored = {"checkpoints": {"2026-11-06": {"1": 100}}, "results": {"2026-11-05": 2}}
        store.async_load.side_effect = [OSError("temporary storage error"), stored]
        tracker = daily.DailyUsageTracker(MagicMock(), "test_entry")
        assert await tracker.async_update("2026-11-07", rows(103), NOW, {1}) == {}
        store.async_save.assert_not_awaited()
        assert await tracker.async_update("2026-11-07", rows(103), NOW, {1}) == {
            "2026-11-05": 2, "2026-11-07": 3,
        }
        assert store.async_load.await_count == 2

    async def test_gap_seeds_a_new_baseline_without_inventing_daily_usage(self, store):
        """A two-day jump -> unknown gap, followed by normal consecutive-day recovery."""
        tracker = daily.DailyUsageTracker(MagicMock(), "test_entry")
        await tracker.async_update("2026-11-06", rows(100), NOW, {1})
        await tracker.async_update("2026-11-07", rows(102), NOW, {1})
        values = await tracker.async_update("2026-11-09", rows(110), NOW, {1})
        assert values == {"2026-11-07": 2}
        values = await tracker.async_update("2026-11-10", rows(113), NOW, {1})
        assert values == {"2026-11-07": 2, "2026-11-10": 3}

    @pytest.mark.parametrize("bad_rows", [[], rows(102), rows(float("nan"), 200), rows(102, None)])
    async def test_partial_or_invalid_response_does_not_advance_checkpoint(self, store, bad_rows):
        """A failed/partial reading -> retain baseline for a complete same-date retry."""
        tracker = daily.DailyUsageTracker(MagicMock(), "test_entry")
        await tracker.async_update("2026-11-06", rows(100, 200), NOW, {1, 2})
        assert await tracker.async_update("2026-11-07", bad_rows, NOW, {1, 2}) == {}
        assert await tracker.async_update("2026-11-07", rows(102, 201), NOW, {1, 2}) == {"2026-11-07": 3}

    async def test_changed_device_set_requires_a_new_matching_baseline(self, store):
        """New meter -> no fictitious delta from its cumulative counter."""
        tracker = daily.DailyUsageTracker(MagicMock(), "test_entry")
        await tracker.async_update("2026-11-06", rows(100), NOW, {1})
        assert await tracker.async_update("2026-11-07", rows(102, 500), NOW, {1, 2}) == {}
        assert await tracker.async_update("2026-11-08", rows(103, 502), NOW, {1, 2}) == {"2026-11-08": 3}

    async def test_known_device_cannot_disappear_when_monthly_context_is_missing(self, store):
        """Several partial dates without monthly cache -> no partial-consumption result."""
        tracker = daily.DailyUsageTracker(MagicMock(), "test_entry")
        await tracker.async_update("2026-11-06", rows(100, 200), NOW, {1, 2})
        assert await tracker.async_update("2026-11-07", rows(102), NOW, set()) == {}
        assert await tracker.async_update("2026-11-08", rows(103), NOW, set()) == {}
        assert await tracker.async_update("2026-11-08", rows(103, 201), NOW, {1, 2}) == {}
        assert await tracker.async_update("2026-11-09", rows(105, 202), NOW, {1, 2}) == {"2026-11-09": 3}

    async def test_january_zero_is_valid_and_annual_counter_reset_is_not_negative(self, store):
        """December cumulative counter -> January annual-zero daily baseline."""
        tracker = daily.DailyUsageTracker(MagicMock(), "test_entry")
        now = datetime(2027, 1, 3, tzinfo=ZONE)
        await tracker.async_update("2026-12-31", rows(1000), now, {1})
        assert await tracker.async_update("2027-01-01", rows(0), now, {1}) == {"2027-01-01": 0}
        assert await tracker.async_update("2027-01-02", rows(2), now, {1}) == {"2027-01-01": 0, "2027-01-02": 2}

    async def test_backward_or_future_date_does_not_replace_latest_observation(self, store):
        """Regressing/future source date -> ignore it and retain the last correct result."""
        tracker = daily.DailyUsageTracker(MagicMock(), "test_entry")
        await tracker.async_update("2026-11-06", rows(100), NOW, {1})
        await tracker.async_update("2026-11-07", rows(102), NOW, {1})
        for day in ("2026-11-05", "2026-11-11", "invalid"):
            assert await tracker.async_update(day, rows(200), NOW, {1}) == {"2026-11-07": 2}


class TestReportedDailyReport:
    """Expose dated daily attributes and statistics without a separate daily entity."""

    async def test_daily_graph_uses_reading_date_and_stable_external_identity(self):
        """A lagging November 7 result received on November 10 -> November 7 graph point."""
        sensor = MijnTedPublishedUsageSensor(SimpleNamespace(data={
            "daily_usage": {"2026-11-07": 3.0},
        }), "Test_Entry")
        sensor.entity_id = "sensor.renamed_daily_usage"
        sensor._translated_name = "Published usage"
        sensor.hass = MagicMock()
        sensor.hass.config.components = {"recorder"}
        with patch.object(base.dt_util, "now", return_value=NOW), patch.object(base.dt_util, "get_default_time_zone", return_value=ZONE), patch.object(base, "async_add_external_statistics", return_value=None) as external, patch.object(base, "async_import_statistics") as internal:
            assert sensor.state is None  # No published month in this daily-only fixture.
            assert sensor.state_class is None
            assert sensor.extra_state_attributes["reported_daily_usage"] == 3
            assert sensor.extra_state_attributes["reported_daily_date"] == "2026-11-07"
            await sensor._async_inject_statistics()
            metadata, imported = external.call_args.args[1:]
            assert metadata["statistic_id"] == "mijnted:test_entry_reported_daily_usage"
            assert metadata["name"] == "Reported daily usage"
            assert imported == [{"start": datetime(2026, 11, 7, tzinfo=ZONE), "mean": 3.0}]
            internal.assert_not_called()


class TestReadingMonthReport:
    """Switch the lagging month when dated readings arrive, not on receipt month."""

    @pytest.mark.parametrize("november_total", [870, 873])
    async def test_late_month_switch_uses_november_first_even_when_received_on_third(self, store, november_total):
        """October 41 then November 0/3 -> true dated switch and matching monthly/daily imports."""
        cache = {
            "2026-10": MonthCacheEntry(
                month_id="10.2026", year=2026, month=10, start_date="2026-10-01", end_date="2026-10-31",
                total_usage=39, average_usage=None, devices=[DeviceReading(id=1, start=829, end=868)],
                start_locked=True,
            ),
            "2026-11": MonthCacheEntry(
                month_id="11.2026", year=2026, month=11, start_date="2026-11-01", end_date="2026-11-01",
                total_usage=november_total-870, average_usage=None,
                devices=[DeviceReading(id=1, start=870, end=november_total)], start_locked=True,
            ),
        }
        data = {"monthly_history_cache": cache}
        hub = SimpleNamespace(data=data)
        calendar = MijnTedMonthlyUsageSensor(hub, "test_entry")
        published = MijnTedPublishedUsageSensor(hub, "test_entry")
        published.entity_id = "sensor.published_usage"
        published.hass = MagicMock()
        published.hass.config.components = {"recorder"}
        tracker = daily.DailyUsageTracker(MagicMock(), "test_entry")
        frames = [
            (datetime(2026, 11, 1, tzinfo=ZONE), "2026-10-30", 868, 39, 0),
            (datetime(2026, 11, 2, tzinfo=ZONE), "2026-10-31", 870, 41, 0),
            (datetime(2026, 11, 3, tzinfo=ZONE), "2026-11-01", november_total, november_total-870, november_total-870),
        ]
        with patch.object(base.dt_util, "now") as clock, patch.object(base.dt_util, "get_default_time_zone", return_value=ZONE):
            for received_at, reading_date, counter, report_value, calendar_value in frames:
                clock.return_value = received_at
                if reading_date == "2026-10-31":
                    cache["2026-10"].published_usage = cache["2026-10"].total_usage = 41
                data.update({"last_update": reading_date, "filter_status": rows(counter)})
                data["daily_usage"] = await tracker.async_update(reading_date, rows(counter), received_at, {1})
                report_key = reading_date[:7]
                data["reading_report"] = build_reading_report(tracker.reading_snapshot, cache[report_key].to_dict())
                assert published.state == report_value
                assert published.extra_state_attributes["reading_date"] == reading_date
                assert calendar.state == calendar_value
                if reading_date == "2026-10-30":
                    with patch.object(base, "async_add_external_statistics", return_value=None) as early_import:
                        await published._async_inject_statistics()
                    own = next(call.args[2] for call in early_import.call_args_list
                               if call.args[1]["statistic_id"] == "mijnted:test_entry_monthly_usage")
                    assert not any(row["start"].month == 11 for row in own)
            assert published.extra_state_attributes["month_id"] == "11.2026"
            with patch.object(base, "async_add_external_statistics", return_value=None) as external:
                await published._async_inject_statistics()
            imports = {call.args[1]["statistic_id"]: call.args[2] for call in external.call_args_list}
            november_first = datetime(2026, 11, 1, tzinfo=ZONE)
            assert {"start": november_first, "mean": november_total-870} in imports["mijnted:test_entry_monthly_usage"]
            assert {"start": november_first, "mean": november_total-870} in imports["mijnted:test_entry_reported_daily_usage"]

    async def test_partial_new_date_keeps_the_last_complete_report_and_graph_value(self, store):
        """November 7 partial response -> report and canonical graph retain complete November 6 usage."""
        tracker = daily.DailyUsageTracker(MagicMock(), "test_entry")
        await tracker.async_update("2026-11-06", rows(888, 0), NOW, {1, 2})
        await tracker.async_update("2026-11-07", rows(890), NOW, {1, 2})
        month = MonthCacheEntry(
            month_id="11.2026", year=2026, month=11, start_date="2026-11-01", end_date="2026-11-07",
            total_usage=20, average_usage=None,
            devices=[DeviceReading(id=1, start=870, end=890), DeviceReading(id=2, start=0, end=0)],
        )
        report = build_reading_report(tracker.reading_snapshot, month.to_dict())
        assert report["value"] == 18
        assert report["reading_date"] == "2026-11-06"
        data = {"reading_report": report, "monthly_history_cache": {"2026-11": month},
                "last_update": "2026-11-07", "filter_status": rows(890)}
        sensor = MijnTedPublishedUsageSensor(SimpleNamespace(data=data), "test_entry")
        sensor.entity_id = "sensor.published_usage"
        sensor.hass = MagicMock()
        sensor.hass.config.components = {"recorder"}
        with patch.object(base.dt_util, "now", return_value=NOW), patch.object(base.dt_util, "get_default_time_zone", return_value=ZONE), patch.object(base, "async_add_external_statistics", return_value=None) as external:
            await sensor._async_inject_statistics()
        own = next(call.args[2] for call in external.call_args_list if call.args[1]["statistic_id"] == "mijnted:test_entry_monthly_usage")
        assert own == [{"start": datetime(2026, 11, 1, tzinfo=ZONE), "mean": 18}]
    def test_unknown_until_first_computable_day_and_valid_zero_is_reported(self):
        """No daily result -> unknown; observed zero -> dated zero."""
        sensor = MijnTedPublishedUsageSensor(SimpleNamespace(data={"daily_usage": {}}), "test_entry")
        with patch.object(base.dt_util, "now", return_value=NOW):
            assert sensor.state is None
            assert "reported_daily_date" not in sensor.extra_state_attributes
            sensor.coordinator.data["daily_usage"]["2026-11-07"] = 0
            assert sensor.extra_state_attributes["reported_daily_usage"] == 0
            assert sensor.extra_state_attributes["reported_daily_date"] == "2026-11-07"
