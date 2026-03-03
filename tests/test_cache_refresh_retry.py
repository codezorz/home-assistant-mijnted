"""Tests for current-month cache refresh retry behavior.

Verifies that a skipped or failed _update_current_month_cache does not
advance cached_last_update_date, preserving the retry window for the
next poll cycle.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mijnted.sensors.models import (
    DeviceReading,
    MonthCacheEntry,
    MONTH_STATE_OPEN,
)

import custom_components.mijnted.__init__ as init_mod


def _make_cache_entry(month, year, *, devices=None, total_usage=100.0):
    """Build a minimal MonthCacheEntry for testing."""
    if devices is None:
        devices = [DeviceReading(id=1, start=0.0, end=50.0, usage=50.0)]
    from custom_components.mijnted.utils import DateUtil
    return MonthCacheEntry(
        month_id=DateUtil.format_month_year_key(month, year),
        year=year,
        month=month,
        start_date=DateUtil.format_date_for_api(
            DateUtil.get_first_day_of_month(month, year)
        ),
        end_date=f"{year}-{month:02d}-15",
        total_usage=total_usage,
        average_usage=3.0,
        devices=devices,
        finalized=False,
        state=MONTH_STATE_OPEN,
        start_locked=False,
    )


# ---------------------------------------------------------------------------
# _update_current_month_cache return value contract
# ---------------------------------------------------------------------------

class TestUpdateCurrentMonthCacheReturnValue:
    """Verify the bool return from _update_current_month_cache."""

    @pytest.fixture
    def api(self):
        api = AsyncMock()
        api.get_device_statuses_for_date = AsyncMock(return_value=[])
        return api

    @pytest.fixture
    def now(self):
        return datetime(2026, 3, 3, 12, 0, 0)

    async def test_returns_false_when_filter_status_empty_and_cache_usable(
        self, api, now
    ):
        """Empty filter_status + usable cache -> skip (False)."""
        from custom_components.mijnted.utils import DateUtil
        month_key = DateUtil.format_month_key(now.year, now.month)
        cache = {month_key: _make_cache_entry(now.month, now.year)}

        result = await init_mod._update_current_month_cache(
            api, cache, [], "2026-03-03", {}, now
        )

        assert result is False

    async def test_returns_true_when_filter_status_has_data(self, api, now):
        """Valid filter_status -> update succeeds (True)."""
        from custom_components.mijnted.utils import DateUtil
        month_key = DateUtil.format_month_key(now.year, now.month)
        cache = {month_key: _make_cache_entry(now.month, now.year)}
        filter_status = [
            {"deviceNumber": "A1", "currentReadingValue": 200},
        ]

        with patch.object(
            init_mod, "_resolve_current_month_devices",
            new_callable=AsyncMock,
            return_value=(
                [{"id": "A1", "start": 0, "end": 200}],
                0.0,
            ),
        ):
            result = await init_mod._update_current_month_cache(
                api, cache, filter_status, "2026-03-03", {}, now
            )

        assert result is True

    async def test_returns_true_when_no_existing_cache(self, api, now):
        """Empty filter_status + no existing cache -> skip guard does not apply (True)."""
        filter_status = [
            {"deviceNumber": "A1", "currentReadingValue": 100},
        ]

        with patch.object(
            init_mod, "_resolve_current_month_devices",
            new_callable=AsyncMock,
            return_value=(
                [{"id": "A1", "start": 0, "end": 100}],
                0.0,
            ),
        ):
            result = await init_mod._update_current_month_cache(
                api, {}, filter_status, "2026-03-03", {}, now
            )

        assert result is True


# ---------------------------------------------------------------------------
# _update_and_enrich_cache tuple return
# ---------------------------------------------------------------------------

class TestUpdateAndEnrichCacheSkipSignal:
    """Verify skip/exception signal propagation from _update_and_enrich_cache."""

    @pytest.fixture
    def api(self):
        return AsyncMock()

    @pytest.fixture
    def now(self):
        return datetime(2026, 3, 3, 12, 0, 0)

    async def test_skip_signal_when_refresh_skipped(self, api, now):
        """When _update_current_month_cache returns False, skip signal is True."""
        with patch.object(
            init_mod, "_update_current_month_cache",
            new_callable=AsyncMock, return_value=False,
        ), patch.object(
            init_mod, "_lock_current_month_starts_when_previous_complete",
            new_callable=AsyncMock, return_value=False,
        ), patch.object(
            init_mod, "_enrich_cache_with_api_data", new_callable=AsyncMock,
        ), patch.object(
            init_mod, "_snapshot_cache_averages", return_value={},
        ), patch.object(
            init_mod, "_recalculate_current_month_starts_if_previous_finalized",
            new_callable=AsyncMock, return_value=False,
        ):
            modified, skipped = await init_mod._update_and_enrich_cache(
                api, {}, [], "2026-03-03", {},
                last_update_date_changed=True, now=now,
            )

        assert modified is False
        assert skipped is True

    async def test_skip_signal_when_refresh_raises(self, api, now):
        """When _update_current_month_cache raises, skip signal is True."""
        with patch.object(
            init_mod, "_update_current_month_cache",
            new_callable=AsyncMock, side_effect=RuntimeError("API down"),
        ), patch.object(
            init_mod, "_lock_current_month_starts_when_previous_complete",
            new_callable=AsyncMock, return_value=False,
        ), patch.object(
            init_mod, "_enrich_cache_with_api_data", new_callable=AsyncMock,
        ), patch.object(
            init_mod, "_snapshot_cache_averages", return_value={},
        ), patch.object(
            init_mod, "_recalculate_current_month_starts_if_previous_finalized",
            new_callable=AsyncMock, return_value=False,
        ):
            modified, skipped = await init_mod._update_and_enrich_cache(
                api, {}, [], "2026-03-03", {},
                last_update_date_changed=True, now=now,
            )

        assert modified is False
        assert skipped is True

    async def test_no_skip_signal_on_success(self, api, now):
        """When _update_current_month_cache returns True, skip signal is False."""
        with patch.object(
            init_mod, "_update_current_month_cache",
            new_callable=AsyncMock, return_value=True,
        ), patch.object(
            init_mod, "_lock_current_month_starts_when_previous_complete",
            new_callable=AsyncMock, return_value=False,
        ), patch.object(
            init_mod, "_enrich_cache_with_api_data", new_callable=AsyncMock,
        ), patch.object(
            init_mod, "_snapshot_cache_averages", return_value={},
        ), patch.object(
            init_mod, "_recalculate_current_month_starts_if_previous_finalized",
            new_callable=AsyncMock, return_value=False,
        ):
            modified, skipped = await init_mod._update_and_enrich_cache(
                api, {}, [], "2026-03-03", {},
                last_update_date_changed=True, now=now,
            )

        assert modified is True
        assert skipped is False

    async def test_no_skip_signal_when_date_unchanged(self, api, now):
        """When last_update_date_changed is False, no refresh attempted -> no skip."""
        with patch.object(
            init_mod, "_lock_current_month_starts_when_previous_complete",
            new_callable=AsyncMock, return_value=False,
        ), patch.object(
            init_mod, "_enrich_cache_with_api_data", new_callable=AsyncMock,
        ), patch.object(
            init_mod, "_snapshot_cache_averages", return_value={},
        ), patch.object(
            init_mod, "_recalculate_current_month_starts_if_previous_finalized",
            new_callable=AsyncMock, return_value=False,
        ):
            modified, skipped = await init_mod._update_and_enrich_cache(
                api, {}, [], "2026-03-03", {},
                last_update_date_changed=False, now=now,
            )

        assert skipped is False


# ---------------------------------------------------------------------------
# Orchestration: _ensure_monthly_history_cache retry suppression fix
# ---------------------------------------------------------------------------

class TestEnsureMonthlyHistoryCacheRetryBehavior:
    """Prove that cached_last_update_date is NOT advanced when refresh is
    skipped or fails, preserving the retry window for the next poll."""

    OLD_DATE = "2026-03-02"
    NEW_DATE = "2026-03-03"

    @pytest.fixture
    def api(self):
        return AsyncMock()

    @pytest.fixture
    def hass(self):
        hass = MagicMock()
        hass.data = {}
        return hass

    @pytest.fixture
    def entry(self):
        entry = MagicMock()
        entry.entry_id = "test_entry"
        return entry

    def _patch_load_cache(self, cached_date):
        """Patch _load_cache_from_coordinator to return a given cached date."""
        return patch.object(
            init_mod, "_load_cache_from_coordinator",
            return_value=({}, cached_date),
        )

    def _patch_load_or_build(self):
        return patch.object(
            init_mod, "_load_or_build_cache",
            new_callable=AsyncMock,
            return_value=({}, False),
        )

    def _patch_save(self):
        return patch.object(
            init_mod, "_save_persisted_cache", new_callable=AsyncMock,
        )

    def _patch_stats(self):
        return patch.object(
            init_mod, "_get_or_create_statistics_tracking",
            return_value=MagicMock(),
        )

    async def test_skip_holds_old_date(self, api, hass, entry):
        """Poll 1: empty filter_status skips refresh -> date stays old."""
        with (
            self._patch_load_cache(self.OLD_DATE),
            self._patch_load_or_build(),
            self._patch_save(),
            self._patch_stats(),
            patch.object(
                init_mod, "_update_and_enrich_cache",
                new_callable=AsyncMock,
                return_value=(False, True),
            ),
        ):
            _, returned_date, _ = await init_mod._ensure_monthly_history_cache(
                api, hass, entry,
                last_update={"lastSyncDate": self.NEW_DATE},
                energy_usage_data={},
                filter_status=[],
            )

        assert returned_date == self.OLD_DATE, (
            "cached_last_update_date must stay old when refresh was skipped"
        )

    async def test_failure_mapped_to_skipped_signal_holds_old_date(self, api, hass, entry):
        """Poll 1: refresh failure mapped to skipped signal -> date stays old."""
        with (
            self._patch_load_cache(self.OLD_DATE),
            self._patch_load_or_build(),
            self._patch_save(),
            self._patch_stats(),
            patch.object(
                init_mod, "_update_and_enrich_cache",
                new_callable=AsyncMock,
                return_value=(False, True),
            ),
        ):
            _, returned_date, _ = await init_mod._ensure_monthly_history_cache(
                api, hass, entry,
                last_update={"lastSyncDate": self.NEW_DATE},
                energy_usage_data={},
                filter_status=[],
            )

        assert returned_date == self.OLD_DATE, (
            "cached_last_update_date must stay old when refresh failure maps to skipped signal"
        )

    async def test_success_advances_date(self, api, hass, entry):
        """Poll 2: valid data succeeds -> date advances to new."""
        with (
            self._patch_load_cache(self.OLD_DATE),
            self._patch_load_or_build(),
            self._patch_save(),
            self._patch_stats(),
            patch.object(
                init_mod, "_update_and_enrich_cache",
                new_callable=AsyncMock,
                return_value=(True, False),
            ),
        ):
            _, returned_date, _ = await init_mod._ensure_monthly_history_cache(
                api, hass, entry,
                last_update={"lastSyncDate": self.NEW_DATE},
                energy_usage_data={},
                filter_status=[
                    {"deviceNumber": "A1", "currentReadingValue": 200},
                ],
            )

        assert returned_date == self.NEW_DATE, (
            "cached_last_update_date must advance when refresh succeeded"
        )

    async def test_retry_window_preserved_across_polls(self, api, hass, entry):
        """Two-poll scenario: skip on poll 1, success on poll 2 (same date).

        Proves the reported bug is fixed: the retry window is preserved
        because cached_last_update_date is not advanced on skip, so poll 2
        still sees last_update_date_changed=True and retries the refresh.
        """
        update_and_enrich = AsyncMock()
        update_and_enrich.side_effect = [
            (False, True),
            (True, False),
        ]

        with (
            self._patch_load_or_build(),
            self._patch_save(),
            self._patch_stats(),
            patch.object(init_mod, "_update_and_enrich_cache", update_and_enrich),
        ):
            # Poll 1: date rollover, filter_status empty -> skip
            with self._patch_load_cache(self.OLD_DATE):
                _, date_after_poll1, _ = await init_mod._ensure_monthly_history_cache(
                    api, hass, entry,
                    last_update={"lastSyncDate": self.NEW_DATE},
                    energy_usage_data={},
                    filter_status=[],
                )

            assert date_after_poll1 == self.OLD_DATE, "Poll 1 must hold old date"

            # Poll 2: same new date, but now coordinator has the held old date
            with self._patch_load_cache(date_after_poll1):
                _, date_after_poll2, _ = await init_mod._ensure_monthly_history_cache(
                    api, hass, entry,
                    last_update={"lastSyncDate": self.NEW_DATE},
                    energy_usage_data={},
                    filter_status=[
                        {"deviceNumber": "A1", "currentReadingValue": 200},
                    ],
                )

            assert date_after_poll2 == self.NEW_DATE, "Poll 2 must advance date"

            # Verify the refresh path was called with last_update_date_changed=True
            # on both polls (the retry actually happened).
            assert update_and_enrich.call_count == 2
            for call in update_and_enrich.call_args_list:
                last_update_date_changed_arg = call.kwargs.get(
                    "last_update_date_changed",
                    call.args[5] if len(call.args) > 5 else None,
                )
                assert last_update_date_changed_arg is True, (
                    "Both polls must see last_update_date_changed=True"
                )
