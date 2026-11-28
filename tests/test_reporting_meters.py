"""Meter-scoped cloud request routing and publication validation."""

import asyncio
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlsplit

import aiohttp

from custom_components import mijnted as integration
from custom_components.mijnted import _discover_reporting_meters
from custom_components.mijnted.api import MijntedApi


async def test_meter_requests_use_the_same_auth_and_only_gj_selects_a_unit():
    """A dated GJ request keeps its date and water never receives the GJ parameter."""
    api = MijntedApi(None, "client", residential_unit="home")
    api.delivery_type = "1"
    api.auth = SimpleNamespace(residential_unit="home", access_token="example")
    api._make_request = AsyncMock(return_value=[{"unitOfMeasure": "GJ", "currentReadingValue": 1.2345}])
    heat = api.for_meter("1", "GJ")
    water = api.for_meter("2", "m³")
    assert heat.auth is water.auth is api.auth
    rows = await heat.get_device_statuses_for_date(date(2026, 10, 31))
    url = urlsplit(api._make_request.call_args.args[1])
    assert url.path.endswith("/home/1/2026")
    assert parse_qs(url.query) == {"fromDate": ["2026-10-31"], "unitOfMeasure": ["GJ"]}
    assert rows[0]["currentReadingValue"] == 1.2345
    assert await water.get_filter_status() == []  # a response carrying GJ must not become m³
    url = urlsplit(api._make_request.call_args.args[1])
    assert "/home/2/" in url.path
    assert not url.query
    assert api.delivery_type == "1"


async def test_water_monthly_api_ignores_rows_with_wrong_or_missing_units():
    """An API fallback to count units must not become a water statistic."""
    api = MijntedApi(None, "client", residential_unit="home").for_meter("2", "m³")
    valid = {"monthYear": "10.2026", "unitOfMeasurement": "m³", "totalEnergyUsage": 1.23}
    api._make_request = AsyncMock(return_value={"monthlyEnergyUsages": [
        {"monthYear": "8.2026"}, {"monthYear": "9.2026", "unitOfMeasurement": "Eenheden"}, valid,
    ]})
    assert await api.get_energy_usage(2026) == {"monthlyEnergyUsages": [valid]}
    assert await api.get_energy_usage(2026) == {"monthlyEnergyUsages": [valid]}
    api._make_request.assert_awaited_once()


def test_water_first_discovery_keeps_both_heating_units():
    """A water-first account can discover heating Units and GJ at the same time."""
    payload = {
        "primary_delivery_type": "2", "unit_of_measures": [{"value": "m3"}], "active_model": "WWZF-AP",
        "extra_delivery_data": {"1": {"unit_of_measures": [{"value": "eenheid"}, {"value": "GJ"}]}},
    }
    meters = _discover_reporting_meters(payload, {})
    assert set(meters) == {"2_m3", "1_units", "1_gj"}
    assert meters["2_m3"].kind == "warm"
    assert _discover_reporting_meters({}, meters) == meters


def _water_sources(*deliveries):
    """Advertise water groups without needing readings from the meter endpoint."""
    return {"primary_delivery_type": "1", "extra_delivery_data": {
        delivery: {"unit_of_measures": [{"value": "m³"}]} for delivery in deliveries
    }}


def _water_usage(value):
    """A completed month with a usable billing-unit average."""
    return {"monthlyEnergyUsages": [{"monthYear": "10.2026", "totalEnergyUsage": value,
                                    "averageEnergyUseForBillingUnit": 8.0}]}


async def test_optional_meter_has_bounded_wait_and_does_not_delay_peer(monkeypatch):
    """One stalled meter is canceled while a sibling still publishes its report."""
    monkeypatch.setattr(integration, "ADDITIONAL_METER_REFRESH_TIMEOUT", 0.05)
    cancelled = asyncio.Event()

    async def stall(year):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    warm = SimpleNamespace(get_energy_usage=AsyncMock(side_effect=stall))
    cold = SimpleNamespace(get_energy_usage=AsyncMock(return_value=_water_usage(2.5)))
    api = SimpleNamespace(for_meter=lambda delivery, unit: warm if delivery == "2" else cold)
    store = SimpleNamespace(async_load=AsyncMock(return_value=None), async_save=AsyncMock())
    monkeypatch.setattr(integration, "Store", MagicMock(return_value=store))
    monkeypatch.setattr(integration, "dt_util", SimpleNamespace(now=lambda: datetime(2026, 11, 7, tzinfo=timezone.utc)))
    payload = _water_sources("2", "3")
    async with asyncio.timeout(2):
        await integration._fetch_reporting_meters(api, SimpleNamespace(data={}),
                                                  SimpleNamespace(entry_id="test", data={}), payload, {})
    assert cancelled.is_set()
    assert payload["meter_data"]["2_m3"]["meter_available"] is False
    assert payload["meter_data"]["3_m3"]["reading_report"]["value"] == 2.5


async def test_water_cache_retries_unchanged_publication_after_failed_write(monkeypatch):
    """Once disk recovers, an identical refresh makes the corrected reading durable."""
    disk = None

    async def read():
        return disk

    async def write(snapshot):
        nonlocal disk
        # Home Assistant Store may report failure only in its logs.
        if store.async_save.await_count > 1:
            disk = snapshot

    store = SimpleNamespace(async_load=AsyncMock(side_effect=read), async_save=AsyncMock(side_effect=write))
    monkeypatch.setattr(integration, "Store", MagicMock(return_value=store))
    monkeypatch.setattr(integration, "dt_util", SimpleNamespace(now=lambda: datetime(2026, 11, 7, tzinfo=timezone.utc)))
    source = SimpleNamespace(get_energy_usage=AsyncMock(return_value=_water_usage(3.125)))
    api = SimpleNamespace(for_meter=lambda delivery, unit: source)
    entry = SimpleNamespace(entry_id="test", data={})
    coordinator = SimpleNamespace(data={})
    hass = SimpleNamespace(data={"mijnted": {entry.entry_id: coordinator}})

    for pending in (True, False, False):
        payload = _water_sources("2")
        await integration._fetch_reporting_meters(api, hass, entry, payload, {})
        coordinator.data = payload
        warm = payload["meter_data"]["2_m3"]
        assert warm["reading_report"]["value"] == 3.125
        assert warm["water_cache_dirty"] is pending
    assert store.async_save.await_count == 2
    assert store.async_save.call_args.args[0]["monthly_history_cache"]["2026-10"]["published_usage"] == 3.125


async def test_meter_views_share_one_token_refresh_after_concurrent_unauthorized():
    """Parallel reporting must not rotate the same refresh token twice."""
    api = MijntedApi(None, "client", residential_unit="home")
    api.auth = SimpleNamespace(residential_unit="home", access_token="old")

    async def rotate():
        await asyncio.sleep(0)
        api.auth.access_token = "new"

    api.auth.refresh_access_token = AsyncMock(side_effect=rotate)
    api.session = MagicMock()
    api.session.request.return_value.__aenter__.return_value = SimpleNamespace(status=200)
    api._parse_response = AsyncMock(return_value={"ok": True})
    rejected = api._headers()["Authorization"]
    views = [api.for_meter("1", "GJ"), api.for_meter("2", "m³")]
    assert await asyncio.gather(*(view._retry_after_unauthorized(
        "GET", "https://example.invalid", aiohttp.ClientTimeout(total=1), rejected,
    ) for view in views)) == [{"ok": True}, {"ok": True}]
    api.auth.refresh_access_token.assert_awaited_once()
