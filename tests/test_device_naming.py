"""Stable duplicate-name allocation, durable reservations, and localized entity names."""

from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mijnted import naming
import custom_components.mijnted.__init__ as init_mod
from custom_components.mijnted.localization import MijnTedTranslations
from custom_components.mijnted.sensors.button import MijnTedResetStatisticsButton
from custom_components.mijnted.sensors.device import MijnTedDeviceSensor
from custom_components.mijnted.sensors.water import MijnTedWaterMeterSensor
from tests.conftest import flattened_resources


def payload(*devices, extra=None):
    """Build primary statuses with stable device numbers and untouched room values."""
    return {
        "filter_status": [{"deviceNumber": str(number), "room": room, "currentReadingValue": 12,
                           "unitOfMeasure": "Units"} for number, room in devices],
        "delivery_types": [1], "extra_delivery_data": extra or {},
    }


def water(model, *devices):
    """Build a discoverable water delivery, including a missing-model case."""
    return {
        "active_model": model, "unit_of_measures": [{"value": "m³"}],
        "filter_status": [{"deviceNumber": str(number), "room": room, "currentReadingValue": 4,
                           "unitOfMeasure": "m³"} for number, room in devices],
    }


def coordinator(data, language="en"):
    """Use real shipped templates while leaving HA lifecycle to native checks."""
    return SimpleNamespace(data=data, mijnted_translations=MijnTedTranslations(
        flattened_resources("entity", language), flattened_resources("common", language),
    ))


async def project(tracker, data):
    """Add the coordinator's detached name projection without mutating the API fixture."""
    return {**data, "device_names": await tracker.async_update(data)}


@pytest.fixture
def stores():
    """Model entry-scoped HA Store instances with detached JSON snapshots."""
    snapshots, instances = {}, []

    def factory(hass, version, key):
        """Share durable data across independently constructed tracker instances."""
        async def load():
            return deepcopy(snapshots.get(key))

        async def save(value):
            snapshots[key] = json.loads(json.dumps(value))

        store = SimpleNamespace(
            key=key, async_load=AsyncMock(side_effect=load), async_save=AsyncMock(side_effect=save),
        )
        instances.append(store)
        return store

    with patch.object(naming, "Store", side_effect=factory):
        yield SimpleNamespace(snapshots=snapshots, instances=instances)


class TestStableDeviceNames:
    """New duplicates acquire ordinals without disturbing established assignments."""

    async def test_first_batch_is_naturally_sorted_and_singletons_unchanged(self, stores):
        """Reversed device order -> numeric ordering for duplicates, no singleton suffix."""
        tracker = naming.DeviceNameTracker(MagicMock(), "entry")
        data = payload((22, "W"), (9, "KA"), (3, "W"))
        original = deepcopy(data)
        result = await project(tracker, data)
        hub = coordinator(result)
        first = MijnTedDeviceSensor(hub, "3", "entry")
        second = MijnTedDeviceSensor(hub, "22", "entry")
        singleton = MijnTedDeviceSensor(hub, "9", "entry")
        assert first.name == "Device living room 1"
        assert second.name == "Device living room 2"
        assert singleton.name == "Device bedroom"
        assert first.unique_id == "mijnted_entry_device_3"
        assert second.unique_id == "mijnted_entry_device_22"
        assert first.state == 12 and first.unit_of_measurement == "Units"
        assert first.extra_state_attributes["room"] == "W"
        assert data == original

    async def test_new_lower_number_does_not_displace_existing_member(self, stores):
        """A singleton followed by a lower-ID duplicate -> the established device stays first."""
        tracker = naming.DeviceNameTracker(MagicMock(), "entry")
        first = await project(tracker, payload((22, "W")))
        assert MijnTedDeviceSensor(coordinator(first), "22", "entry").name == "Device living room"
        result = await project(tracker, payload((3, "W"), (22, "W")))
        assert result["device_names"]["device_22"]["number"] == 1
        assert result["device_names"]["device_3"]["number"] == 2

    async def test_reordering_partial_payloads_and_restart_keep_assignments(self, stores):
        """Missing peers/readings and a fresh tracker -> preserve numbers and known room context."""
        tracker = naming.DeviceNameTracker(MagicMock(), "entry")
        initial = await project(tracker, payload((22, "W"), (3, "W")))
        hub = coordinator(initial)
        sensor = MijnTedDeviceSensor(hub, "3", "entry")
        assert sensor.state == 12
        sensor.async_write_ha_state = MagicMock()
        original_projection = initial["device_names"]
        store = stores.instances[0]
        for data in (payload((3, "W"), (22, "W")), payload((22, "W")), {}):
            hub.data = await project(tracker, data)
            sensor._handle_coordinator_update()
            assert sensor.name == "Device living room 1"
            assert sensor.state == 12
            assert hub.data["device_names"] == original_projection
        store.async_save.assert_awaited_once()
        restored = naming.DeviceNameTracker(MagicMock(), "entry")
        assert await restored.async_update(payload((22, "W"))) == original_projection

    async def test_absent_slots_are_reserved_for_returning_devices(self, stores):
        """A missing first meter and new lower-ID meter -> allocate 3, not a reused 1."""
        tracker = naming.DeviceNameTracker(MagicMock(), "entry")
        await tracker.async_update(payload((3, "W"), (22, "W")))
        later = await tracker.async_update(payload((22, "W"), (1, "W")))
        assert later["device_3"]["number"] == 1
        assert later["device_22"]["number"] == 2
        assert later["device_1"]["number"] == 3
        restored = naming.DeviceNameTracker(MagicMock(), "entry")
        assert await restored.async_update(payload((1, "W"), (3, "W"), (22, "W"))) == later

    async def test_room_change_and_return_do_not_reclaim_old_slots(self, stores):
        """A meter moves between rooms -> each room retains its own historical reservations."""
        tracker = naming.DeviceNameTracker(MagicMock(), "entry")
        await tracker.async_update(payload((3, "W"), (22, "W"), (9, "KA")))
        moved = await tracker.async_update(payload((3, "W"), (22, "KA"), (9, "KA")))
        assert moved["device_3"]["number"] == 1
        assert moved["device_22"]["number"] == 2
        assert moved["device_9"]["number"] == 1
        returned = await tracker.async_update(payload((3, "W"), (22, "W"), (9, "KA")))
        assert returned["device_22"] == {"room": "W", "kind": None, "number": 2}
        assert returned["device_9"]["number"] == 1

    @pytest.mark.parametrize(("language", "expected"), [
        ("en", "Device bedroom 2"), ("nl", "Apparaat slaapkamer 2"), ("de", "Gerät Schlafzimmer 2"),
    ])
    async def test_reload_in_another_language_retains_numbers(self, stores, language, expected):
        """Persisted numbering -> localized names without language-dependent reassignment."""
        tracker = naming.DeviceNameTracker(MagicMock(), "entry")
        await tracker.async_update(payload((2, "KA"), (10, "KA")))
        restored = naming.DeviceNameTracker(MagicMock(), "entry")
        result = await project(restored, payload((10, "KA"), (2, "KA")))
        assert MijnTedDeviceSensor(coordinator(result, language), "10", "entry").name == expected

    @pytest.mark.parametrize("room", ["NEW", "My HVAC Room"])
    async def test_unknown_codes_and_user_room_names_remain_verbatim(self, stores, room):
        """Duplicate arbitrary contexts -> translated template but unchanged room text/attributes."""
        tracker = naming.DeviceNameTracker(MagicMock(), "entry")
        result = await project(tracker, payload((2, room), (10, room)))
        sensor = MijnTedDeviceSensor(coordinator(result, "de"), "2", "entry")
        assert sensor.name == f"Gerät {room} 1"
        assert sensor.extra_state_attributes["room"] == room

    async def test_missing_room_uses_the_device_number_without_extra_suffix(self, stores):
        """Number-only contexts are already distinct -> preserve the existing fallback names."""
        tracker = naming.DeviceNameTracker(MagicMock(), "entry")
        result = await project(tracker, payload((2, None), (10, "")))
        assert MijnTedDeviceSensor(coordinator(result), "2", "entry").name == "Device 2"
        assert MijnTedDeviceSensor(coordinator(result), "10", "entry").name == "Device 10"

    async def test_config_entries_have_independent_durable_reservations(self, stores):
        """Two installations observing the same meters in different batches -> isolated numbering."""
        first = naming.DeviceNameTracker(MagicMock(), "first")
        second = naming.DeviceNameTracker(MagicMock(), "second")
        await first.async_update(payload((10, "W")))
        await second.async_update(payload((2, "W")))
        data = payload((2, "W"), (10, "W"))
        assert (await first.async_update(data))["device_10"]["number"] == 1
        assert (await second.async_update(data))["device_10"]["number"] == 2
        assert len(stores.snapshots) == 2


class TestWaterMeterNames:
    """Group water labels by semantic kind/context, including across delivery types."""

    @pytest.mark.parametrize(("language", "expected"), [
        ("en", "Warm water meter living room 2"),
        ("nl", "Warmwatermeter woonkamer 2"),
        ("de", "Warmwasserzähler Wohnzimmer 2"),
    ])
    async def test_water_duplicates_cross_deliveries_but_not_kinds(self, stores, language, expected):
        """Two warm meters and a cold meter in one room -> number only matching warm labels."""
        tracker = naming.DeviceNameTracker(MagicMock(), "entry")
        data = payload(extra={"7": water("WWZF-AP", (12, "W")),
                              "2": water("WWZF-AP", (12, "W")),
                              "3": water("KWZF-AP", (12, "W"))})
        result = await project(tracker, data)
        sensor = MijnTedWaterMeterSensor(coordinator(result, language), "7", "12", "entry")
        assert sensor.name == expected
        assert result["device_names"]["water_2_device_12"]["number"] == 1
        assert result["device_names"]["water_3_device_12"]["number"] is None
        assert sensor._attr_unique_id == "mijnted_entry_water_7_device_12"
        assert sensor.native_value == 4 and sensor._attr_native_unit_of_measurement == "m³"

    async def test_missing_water_delivery_or_model_retains_known_name(self, stores):
        """A partial refresh/restart -> keep numbered room and warm-water context."""
        tracker = naming.DeviceNameTracker(MagicMock(), "entry")
        initial = await project(tracker, payload(extra={"7": water("WWZF-AP", (2, "W"), (10, "W"))}))
        hub = coordinator(initial)
        sensor = MijnTedWaterMeterSensor(hub, "7", "10", "entry")
        sensor.async_write_ha_state = MagicMock()
        assert sensor.native_value == 4
        for data in (payload(extra={"7": water(None, (10, "W"))}), payload()):
            hub.data = await project(tracker, data)
            sensor._handle_coordinator_update()
            assert sensor.name == "Warm water meter living room 2"
            assert sensor.native_value == 4
        restored = naming.DeviceNameTracker(MagicMock(), "entry")
        hub.data = await project(restored, payload())
        sensor._handle_coordinator_update()
        assert sensor.name == "Warm water meter living room 2"

    async def test_first_batch_orders_device_numbers_across_delivery_types(self, stores):
        """A lower meter number in a later delivery -> first ordinal follows the meter number."""
        tracker = naming.DeviceNameTracker(MagicMock(), "entry")
        result = await tracker.async_update(payload(extra={
            "2": water("WWZF-AP", (10, "W")), "7": water("WWZF-AP", (2, "W")),
        }))
        assert result["water_7_device_2"]["number"] == 1
        assert result["water_2_device_10"]["number"] == 2


class TestCoordinatorNameProjection:
    """The real setup/update closure must prepare naming before forwarding platforms."""

    async def test_first_refresh_prepares_persisted_names_before_platform_setup(self, stores):
        """A successful cloud payload -> numbered coordinator data is ready when platforms load."""
        raw = payload((10, "W"), (2, "W"))
        fetched = {key: {} for key in (
            "energy_usage_data", "last_update_data", "active_model_data", "usage_per_room_data",
            "usage_insight_data", "usage_insight_last_year_data", "residential_unit_detail_data",
            "unit_of_measures_data",
        )}
        fetched.update(filter_status_data=raw["filter_status"], delivery_types=[1], extra_delivery_data={})
        api = MagicMock()
        api.authenticate = AsyncMock()
        api.__aenter__.return_value = api
        hass = MagicMock()
        hass.data = {}
        entry = SimpleNamespace(entry_id="entry", data={"client_id": "test-client", "refresh_token": "test-refresh"})

        class Coordinator:
            """Run the actual update closure while keeping HA scheduling out of this test."""
            def __init__(self, hass, logger, *, name, update_method, update_interval):
                self.update = update_method

            async def async_config_entry_first_refresh(self):
                """Deliver the first payload before platform registration."""
                self.data = await self.update()

        async def platforms(current_entry, names):
            """Assert the contract at the actual platform-forwarding boundary."""
            data = hass.data["mijnted"]["entry"].data
            assert data["device_names"]["device_2"]["number"] == 1
            assert data["device_names"]["device_10"]["number"] == 2
            assert data["filter_status"] == raw["filter_status"]

        hass.config_entries.async_forward_entry_setups = AsyncMock(side_effect=platforms)
        with (
            patch.object(init_mod, "DataUpdateCoordinator", Coordinator),
            patch.object(init_mod, "MijntedApi", return_value=api),
            patch.object(init_mod, "_sync_tokens_to_config"),
            patch.object(init_mod, "_fetch_and_normalize_api_data", AsyncMock(return_value=fetched)),
            patch.object(init_mod, "_compute_anchor_calculations", AsyncMock(return_value=([], None))),
            patch.object(init_mod, "_ensure_monthly_history_cache", AsyncMock(return_value=({}, None, None, {}))),
            patch.object(init_mod, "_build_coordinator_return_dict", return_value=deepcopy(raw)),
            patch.object(init_mod, "DailyUsageTracker", return_value=SimpleNamespace(
                async_update=AsyncMock(return_value={}), reading_snapshot={},
            )),
        ):
            assert await init_mod.async_setup_entry(hass, entry)
        hass.config_entries.async_forward_entry_setups.assert_awaited_once()
        stores.instances[0].async_save.assert_awaited_once()


class TestNumberingPersistence:
    """Storage failures cannot overwrite established assignments or block readings."""

    async def test_failed_save_retries_even_when_readings_are_unchanged(self, stores):
        """A transient write error -> retain in-memory suffixes and persist on the next poll."""
        tracker = naming.DeviceNameTracker(MagicMock(), "entry")
        store = stores.instances[-1]
        save = store.async_save.side_effect
        store.async_save.side_effect = OSError("temporary error")
        first = await tracker.async_update(payload((2, "W"), (10, "W")))
        assert stores.snapshots == {}
        store.async_save.side_effect = save
        assert await tracker.async_update(payload((2, "W"), (10, "W"))) == first
        restored = naming.DeviceNameTracker(MagicMock(), "entry")
        assert await restored.async_update(payload((10, "W"), (2, "W"))) == first

    async def test_failed_load_does_not_overwrite_reserved_numbers(self, stores):
        """A read error before restore -> defer allocation until the durable state is readable."""
        tracker = naming.DeviceNameTracker(MagicMock(), "entry")
        await tracker.async_update(payload((10, "W")))
        expected = await tracker.async_update(payload((2, "W"), (10, "W")))
        snapshot = deepcopy(next(iter(stores.snapshots.values())))
        restored = naming.DeviceNameTracker(MagicMock(), "entry")
        store = stores.instances[-1]
        store.async_load.side_effect = [OSError("temporary error"), snapshot]
        assert await restored.async_update(payload((2, "W"), (10, "W"))) == {}
        store.async_save.assert_not_awaited()
        assert await restored.async_update(payload((2, "W"), (10, "W"))) == expected

    @pytest.mark.parametrize("stored", [
        [], {}, {"groups": [], "devices": {}},
        {"groups": {"group": {"device_2": True}}, "devices": {}},
        {"groups": {"group": {"device_2": 1, "device_10": 1}}, "devices": {}},
        {"groups": {"group": {"device_2": 1}}, "devices": {"device_2": {"group": "group"}}},
        {"groups": {}, "devices": {"device_2": {"group": "absent", "room": "W", "kind": None}}},
    ])
    async def test_invalid_saved_state_is_not_overwritten(self, stores, stored):
        """Inconsistent storage -> preserve it for recovery instead of inventing/reusing suffixes."""
        tracker = naming.DeviceNameTracker(MagicMock(), "entry")
        store = stores.instances[-1]
        stores.snapshots[store.key] = deepcopy(stored)
        assert await tracker.async_update(payload((2, "W"), (10, "W"))) == {}
        store.async_save.assert_not_awaited()
        assert stores.snapshots[store.key] == stored

    async def test_monthly_reset_does_not_clear_name_assignments(self, stores):
        """Reset statistics -> the separate durable numbering store is retained across reload."""
        hub = coordinator(payload((2, "W"), (10, "W")))
        hub.async_request_refresh = AsyncMock()
        tracker = naming.DeviceNameTracker(MagicMock(), "entry")
        expected = await tracker.async_update(hub.data)
        reset_store = SimpleNamespace(async_save=AsyncMock())
        with patch("custom_components.mijnted.sensors.button.Store", return_value=reset_store):
            button = MijnTedResetStatisticsButton(hub, "entry", hass=MagicMock())
            await button.async_press()
        restored = naming.DeviceNameTracker(MagicMock(), "entry")
        assert await restored.async_update(hub.data) == expected
