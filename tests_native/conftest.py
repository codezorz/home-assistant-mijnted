"""Real HA registries, file storage, SQLite recorder, and synthetic API responses."""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import bootstrap, loader
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import (
    area_registry, category_registry, device_registry, entity_registry,
    floor_registry, issue_registry, label_registry, restore_state,
)
from homeassistant.util import dt as dt_util
from homeassistant.helpers.storage import Store
from pytest_homeassistant.common import MockConfigEntry
from tests_native.helpers import DOMAIN, ENTRY_ID, settled


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir):
    """Use an isolated writable configuration directory."""
    return hass_tmp_config_dir


@pytest.fixture
def hass_storage():
    """Leave production Store file I/O active; the suite uses temporary paths."""
    return {}


@pytest.fixture
def load_registries():
    """Load production registry stores explicitly after HA fixture creation."""
    return False


@pytest.fixture
def mock_recorder_before_hass(recorder_db_url):
    """Prepare recorder settings before the HA fixture initializes."""
    return None


async def load_native_registries(hass):
    """Initialize real HA registry objects with file-backed Store implementations."""
    hass.data.pop(loader.DATA_CUSTOM_COMPONENTS, None)
    device_registry.async_setup(hass)
    for module in (area_registry, category_registry, device_registry, entity_registry,
                   floor_registry, issue_registry, label_registry, restore_state):
        await module.async_load(hass)
    hass.data[bootstrap.DATA_REGISTRIES_LOADED] = None
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    hass.config.language = "en"


@dataclass
class ApiScenario:
    """Synthetic dated observations and published monthly source data."""

    reading_date: date = date(2026, 11, 6)
    reading: float = 888.0
    october_usage: float = 41.0
    october_average: float | None = 139.05
    partial: bool = False
    fail_october_anchor: bool = False
    extra_readings: dict[int, float] = field(default_factory=dict)
    omitted_devices: set[int] = field(default_factory=set)

    def rows(self, value):
        """Return a complete synthetic primary-meter response."""
        values = {1: value, **self.extra_readings}
        return [{"deviceNumber": str(key), "deviceId": key, "measurementDeviceId": key,
                 "currentReadingValue": number, "unitOfMeasure": "Eenheden", "room": "W"}
                for key, number in values.items()]

    def counter(self, target):
        """Resolve source-year cumulative anchors for the retained reporting horizon."""
        if target >= self.reading_date:
            return self.reading
        if target.year <= 2025:
            if target.month <= 9:
                return 100.0
            if target.month == 10:
                return 117.0
            return 310.0
        if target.year == 2026:
            if target.month <= 9:
                return 829.0
            if target.month == 10:
                if target.day == 31:
                    return 829.0 + self.october_usage
                return 868.0 if target.day == 30 else 829.0
            if target.month == 11:
                return {1: 873.0, 2: 875.0, 3: 878.0, 4: 882.0, 5: 885.0, 6: 888.0}.get(target.day, 900.0)
            return 1000.0
        return 2.0 if target.month == 1 else 5.0

    async def anchor(self, target):
        """Provide dated API anchors without a network service."""
        if self.fail_october_anchor and target == date(2026, 10, 31):
            return []
        return self.rows(self.counter(target))

    async def energy(self, year=None):
        """Provide historical publications and current-period placeholders."""
        year = year or dt_util.now().year
        months = []
        for month in range(1, 13):
            average = 1.0
            if year == 2025:
                total = 100.0 if month == 1 else 17.0 if month == 10 else 193.0 if month == 11 else 0.0
                average = 181.01 if month == 10 else 437.14 if month == 11 else 1.0
            elif year == 2026:
                total = 829.0 if month == 1 else self.october_usage if month == 10 else 0.0
                average = 4.91 if month == 9 else self.october_average if month == 10 else 1.0
                if month >= 11:
                    average = None
                if year == self.reading_date.year and month >= self.reading_date.month and month != 10:
                    average = None
            else:
                total, average = 0.0, None
            months.append({"monthYear": f"{month}.{year}", "totalEnergyUsage": total,
                           "averageEnergyUseForBillingUnit": average, "unitOfMeasurement": "Eenheden"})
        return {"monthlyEnergyUsages": months}

    async def latest(self, **kwargs):
        """Deliver complete observations or a failed/empty primary response."""
        return [] if self.partial else [row for row in self.rows(self.reading)
                                      if row["deviceId"] not in self.omitted_devices]

    async def last_update(self):
        """Expose the API's reading date independently of receipt time."""
        return {"value": self.reading_date.isoformat()}


@pytest.fixture
def scenario(request):
    """Supply mutable responses for refresh and lifecycle tests."""
    return ApiScenario(**getattr(request, "param", {}))


@pytest.fixture
def start_at(request):
    """Select a controlled receipt time before integration setup."""
    return getattr(request, "param", datetime(2026, 11, 7, 12, tzinfo=timezone.utc))


@pytest.fixture
def language(request):
    """Select the system language used by native entity translation."""
    return getattr(request, "param", "en")


@pytest.fixture
def initial_months(request):
    """Optionally seed serialized monthly state in the real native Store."""
    return getattr(request, "param", None)


@pytest.fixture
def native_api(scenario):
    """Replace only the external API boundary; all HA/integration layers stay real."""
    import custom_components.mijnted as integration
    api = AsyncMock()
    api.__aenter__.return_value = api
    api.__aexit__.return_value = False
    api.residential_unit = "native-unit"
    api.access_token = "test"
    api.refresh_token = "test"
    api.delivery_type = 1
    api.get_energy_usage.side_effect = scenario.energy
    api.get_last_data_update.side_effect = scenario.last_update
    api.get_filter_status.side_effect = scenario.latest
    api.get_device_statuses_for_date.side_effect = scenario.anchor
    api.get_delivery_types.return_value = [1]
    api.get_usage_insight.return_value = {"usage": 870.0}
    api.get_active_model.return_value = {"value": "F71"}
    api.get_residential_unit_detail.return_value = {}
    api.get_usage_per_room.return_value = {"rooms": [], "currentYear": {"values": []}}
    api.get_unit_of_measures.return_value = [{"displayName": "Eenheden"}]
    with patch.object(integration, "MijntedApi", return_value=api):
        yield api


def config_entry():
    """Create a credential-free native entry using synthetic values."""
    return MockConfigEntry(domain=DOMAIN, entry_id=ENTRY_ID, title="MijnTed", version=2, data={
        "name": "MijnTed", "client_id": "native-client", "username": "native@example.invalid",
        "password": "test", "refresh_token": "test", "access_token": "test",
        "residential_unit": "native-unit", "polling_interval": 3600,
    })


@pytest.fixture
async def runtime(async_setup_recorder_instance, hass, native_api, freezer, start_at, language, initial_months):
    """Set up the integration through HA with real writable stores and SQLite."""
    freezer.move_to(start_at)
    await load_native_registries(hass)
    hass.config.language = language
    await async_setup_recorder_instance(hass, {
        "db_url": "sqlite:///" + str(Path(hass.config.config_dir) / "native-reporting.db"),
        "commit_interval": 0,
    })
    entry = config_entry()
    entry.add_to_hass(hass)
    area = area_registry.async_get(hass).async_create("Native area")
    devices = device_registry.async_get(hass)
    device = devices.async_get_or_create(config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "native-unit")}, name="MijnTed")
    devices.async_update_device(device.id, area_id=area.id)
    if initial_months:
        await Store(hass, 1, f"mijnted_monthly_cache_{entry.entry_id}").async_save({
            "monthly_history_cache": initial_months,
        })
    assert await hass.config_entries.async_setup(entry.entry_id)
    await settled(hass)
    try:
        yield entry
    finally:
        if entry.state is ConfigEntryState.LOADED:
            assert await hass.config_entries.async_unload(entry.entry_id)
            await settled(hass)
