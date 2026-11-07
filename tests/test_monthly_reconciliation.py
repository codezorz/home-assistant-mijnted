"""Published totals, pending boundary repair, and adjacent baseline persistence."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import custom_components.mijnted.__init__ as coordinator
from custom_components.mijnted.reconciliation import async_reconcile_boundaries
from custom_components.mijnted.sensors.models import DeviceReading, MonthCacheEntry

ZONE = timezone.utc


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

@pytest.fixture
def clock():
    """Provide a stable aware reference date for cache operations."""
    return SimpleNamespace(return_value=datetime(2026, 11, 7, 12, tzinfo=ZONE))

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
        assert cache["2026-11"].total_usage == 18
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
        assert cache["2026-11"].total_usage == expected_current

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
