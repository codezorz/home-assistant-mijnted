"""Tests for additional (water) delivery types: fetching, entity creation, and values."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import custom_components.mijnted.__init__ as init_mod
from custom_components.mijnted.api import MijntedApi
from custom_components.mijnted.const import DOMAIN
from custom_components.mijnted.sensor import async_setup_entry as async_setup_sensors
from custom_components.mijnted.sensors.water import (
    MijnTedWaterMeterSensor,
    get_water_deliveries,
    get_water_kind,
)


def _water_delivery(delivery_type, model, device_number, reading):
    """Build an extra_delivery_data entry shaped like the live API."""
    return {
        "delivery_type": delivery_type,
        "unit_of_measures": [{"value": "m³", "displayName": "m³"}],
        "active_model": model,
        "filter_status": [
            {
                "measurementDeviceId": 1,
                "room": "ALG",
                "deviceId": 1,
                "deviceNumber": device_number,
                "currentReadingValue": reading,
                "unitOfMeasure": "m³",
            }
        ],
    }


def _coordinator(extra):
    """Build a coordinator stand-in holding heat and extra delivery data."""
    return SimpleNamespace(
        data={
            "filter_status": [{"deviceNumber": "1001", "room": "W"}],
            "extra_delivery_data": extra,
            "residential_unit": "114582",
            "active_model": "F59",
        },
        last_update_success=True,
        hass=None,
    )


class TestWaterKind:
    """Warm/cold classification of water delivery types."""

    @pytest.mark.parametrize(
        "delivery_type,model,expected",
        [
            ("2", "WWZF-AP", "warm"),
            ("3", "KWZF-AP", "cold"),
            ("9", "kwzf-x", "cold"),
            ("2", None, "warm"),
            ("3", "", "cold"),
            ("7", "UNKNOWN", None),
            ("3", "WWZF-AP", "warm"),
        ],
    )
    def test_kind(self, delivery_type, model, expected):
        """Active model wins; delivery type ID is the fallback; otherwise None."""
        assert get_water_kind(delivery_type, model) == expected


class TestWaterDeliveries:
    """Selection of m³ delivery types from the extra payload."""

    def test_only_m3_deliveries_are_selected(self):
        """Non-m³ delivery types are ignored; devices are deduplicated."""
        heat_like = _water_delivery(4, "X", "5", 1.0)
        heat_like["unit_of_measures"] = [{"value": "eenheid", "displayName": "Eenheden"}]
        heat_like["filter_status"][0]["unitOfMeasure"] = "Einheiten"
        warm = _water_delivery(2, "WWZF-AP", "20808052", 376.2)
        warm["filter_status"].append(dict(warm["filter_status"][0]))
        data = {"extra_delivery_data": {"2": warm, "4": heat_like}}

        assert get_water_deliveries(data) == {"2": ["20808052"]}

    def test_missing_or_invalid_payload(self):
        """No data / malformed payload -> no water deliveries."""
        assert get_water_deliveries(None) == {}
        assert get_water_deliveries({}) == {}
        assert get_water_deliveries({"extra_delivery_data": {"2": "bad"}}) == {}

    def test_unit_detected_from_unit_of_measures_when_devices_missing(self):
        """Device list failed but unitOfMeasures says m³ -> still a water delivery, no meters."""
        delivery = _water_delivery(2, "WWZF-AP", "1", 1.0)
        delivery["filter_status"] = []
        assert get_water_deliveries({"extra_delivery_data": {"2": delivery}}) == {"2": []}


class TestWaterSensorSetup:
    """Entity creation in sensor.async_setup_entry."""

    async def test_water_entities_added_next_to_heat_entities(self):
        """Warm + cold water -> meter sensors with distinct, scoped unique IDs."""
        coordinator = _coordinator(
            {
                "2": _water_delivery(2, "WWZF-AP", "20808052", 376.2),
                "3": _water_delivery(3, "KWZF-AP", "30808052", 708.2),
            }
        )
        hass = MagicMock()
        hass.data = {DOMAIN: {"entry_one": coordinator}}
        add = MagicMock()

        await async_setup_sensors(hass, SimpleNamespace(entry_id="entry_one", data={}), add)

        unique_ids = [entity._attr_unique_id for entity in add.call_args.args[0]]
        assert len(unique_ids) == len(set(unique_ids))
        assert "mijnted_entry_one_device_1001" in unique_ids
        assert "mijnted_entry_one_monthly_usage" in unique_ids
        assert "mijnted_entry_one_water_2_device_20808052" in unique_ids
        assert "mijnted_entry_one_water_3_device_30808052" in unique_ids

    async def test_no_extra_delivery_types_keeps_entities_unchanged(self):
        """Heat-only account -> no water entities."""
        coordinator = _coordinator({})
        hass = MagicMock()
        hass.data = {DOMAIN: {"entry_one": coordinator}}
        add = MagicMock()

        await async_setup_sensors(hass, SimpleNamespace(entry_id="entry_one", data={}), add)

        unique_ids = [entity._attr_unique_id for entity in add.call_args.args[0]]
        assert not any("water" in unique_id for unique_id in unique_ids)


class TestWaterMeterSensor:
    """Meter-reading sensor values and naming."""

    def _sensor(self, extra, delivery_type="2", device_number="20808052"):
        return MijnTedWaterMeterSensor(
            _coordinator(extra), delivery_type, device_number, "entry_one"
        )

    def test_reading_unit_and_classes(self):
        """Reading -> float m³ with water device class and total_increasing."""
        sensor = self._sensor({"2": _water_delivery(2, "WWZF-AP", "20808052", 376.2)})

        assert sensor.native_value == 376.2
        assert sensor._attr_native_unit_of_measurement == "m³"
        assert sensor._attr_device_class == init_mod_sensor_class("WATER")
        assert sensor._attr_state_class == init_mod_sensor_class("TOTAL_INCREASING", state=True)

    def test_name_uses_kind_and_room(self):
        """Known model -> '<Warm|Cold> water meter <room>'."""
        warm = self._sensor({"2": _water_delivery(2, "WWZF-AP", "1", 1.0)}, device_number="1")
        cold = self._sensor({"3": _water_delivery(3, "KWZF-AP", "1", 1.0)}, "3", "1")

        assert warm.name == "Warm water meter ALG"
        assert cold.name == "Cold water meter ALG"

    def test_name_generic_fallback(self):
        """Unknown kind and no room -> 'Water meter <deviceNumber>'."""
        delivery = _water_delivery(7, "MYSTERY", "555", 1.0)
        delivery["filter_status"][0]["room"] = ""
        assert self._sensor({"7": delivery}, "7", "555").name == "Water meter 555"

    def test_last_known_value_when_device_disappears(self):
        """Device missing in a later refresh -> keep last reading, no zero."""
        sensor = self._sensor({"2": _water_delivery(2, "WWZF-AP", "20808052", 376.2)})
        assert sensor.native_value == 376.2

        sensor.coordinator.data["extra_delivery_data"]["2"]["filter_status"] = []
        assert sensor.native_value == 376.2

    def test_unknown_when_never_available(self):
        """Failed extra fetch from the start -> state is None, not 0."""
        sensor = self._sensor({"2": {"delivery_type": 2, "filter_status": []}})
        assert sensor.native_value is None

    @pytest.mark.parametrize("bad_reading", [0.0, -1.0, None])
    def test_non_positive_reading_keeps_last_known_value(self, bad_reading):
        """0/negative/missing reading after a valid one -> last value, so no false meter reset."""
        sensor = self._sensor({"2": _water_delivery(2, "WWZF-AP", "20808052", 376.2)})
        assert sensor.native_value == 376.2

        sensor.coordinator.data["extra_delivery_data"]["2"]["filter_status"][0]["currentReadingValue"] = bad_reading
        assert sensor.native_value == 376.2

    def test_zero_reading_without_history_is_unknown(self):
        """A first reading of 0 -> unknown, not 0."""
        sensor = self._sensor({"2": _water_delivery(2, "WWZF-AP", "20808052", 0.0)})
        assert sensor.native_value is None


def init_mod_sensor_class(member, state=False):
    """Resolve the HA enum member the sensor module sees (mocked in tests)."""
    from custom_components.mijnted.sensors import water

    enum = water.SensorStateClass if state else water.SensorDeviceClass
    return getattr(enum, member)


class TestApiDeliveryTypeParameter:
    """MijntedApi methods honor an explicit delivery type."""

    def _api(self):
        api = MijntedApi(MagicMock(), "client", residential_unit="114582")
        api.base_url = "https://example.invalid/api"
        api.delivery_type = 1
        api._make_request = AsyncMock(return_value=[])
        return api

    async def test_default_uses_primary_delivery_type(self):
        """No argument -> URLs use the primary delivery type (unchanged behavior)."""
        api = self._api()
        await api.get_unit_of_measures()
        await api.get_filter_status()
        await api.get_active_model()

        urls = [call.args[1] for call in api._make_request.await_args_list]
        assert urls[0].endswith("/unitOfMeasures/114582/1/" + str(date.today().year))
        assert urls[1].endswith("/deviceStatuses/114582/1/" + str(date.today().year))
        assert urls[2].endswith("/activeModel/114582/1")

    async def test_explicit_delivery_type_overrides_primary(self):
        """Explicit argument -> that type is in the URL, primary type is untouched."""
        api = self._api()
        await api.get_unit_of_measures(delivery_type=2)
        await api.get_filter_status(delivery_type=2)
        await api.get_active_model(delivery_type=2)

        urls = [call.args[1] for call in api._make_request.await_args_list]
        assert all("/114582/2" in url for url in urls)
        assert api.delivery_type == 1


class TestExtraDeliveryTypeFetch:
    """Coordinator-side fetching of additional delivery types."""

    def _api(self):
        api = MagicMock()
        api.delivery_type = 1
        api.residential_unit = "114582"
        api.get_unit_of_measures = AsyncMock(return_value=[{"value": "m³", "displayName": "m³"}])
        api.get_active_model = AsyncMock(return_value="WWZF-AP")
        api.get_filter_status = AsyncMock(return_value=[{"deviceNumber": "1"}])
        return api

    async def test_primary_type_is_skipped(self):
        """[1, 2, 3] with primary 1 -> only 2 and 3 are fetched."""
        api = self._api()

        result = await init_mod._fetch_extra_delivery_types(api, [1, 2, 3])

        assert set(result) == {"2", "3"}
        assert result["2"]["active_model"] == "WWZF-AP"
        fetched = {call.kwargs["delivery_type"] for call in api.get_filter_status.await_args_list}
        assert fetched == {2, 3}

    async def test_duplicate_types_are_fetched_once(self):
        """[1, 2, "2"] -> type 2 fetched once."""
        api = self._api()

        result = await init_mod._fetch_extra_delivery_types(api, [1, 2, "2"])

        assert set(result) == {"2"}
        assert api.get_filter_status.await_count == 1

    async def test_heat_only_account_fetches_nothing(self):
        """[1] -> no extra calls, empty result."""
        api = self._api()

        assert await init_mod._fetch_extra_delivery_types(api, [1]) == {}
        api.get_filter_status.assert_not_awaited()

    async def test_endpoint_failure_degrades_to_defaults(self):
        """One failing endpoint -> empty default for it, others kept."""
        api = self._api()
        api.get_filter_status = AsyncMock(side_effect=RuntimeError("boom"))

        result = await init_mod._fetch_extra_delivery_types(api, [1, 2])

        assert result["2"]["filter_status"] == []
        assert result["2"]["active_model"] == "WWZF-AP"

    async def test_failed_delivery_type_does_not_affect_others(self):
        """A delivery type whose fetch raises is skipped; the other one survives."""
        api = self._api()
        original = init_mod._fetch_extra_delivery_type

        async def flaky(api_arg, delivery_type):
            if delivery_type == 2:
                raise RuntimeError("boom")
            return await original(api_arg, delivery_type)

        with patch.object(init_mod, "_fetch_extra_delivery_type", flaky):
            result = await init_mod._fetch_extra_delivery_types(api, [1, 2, 3])

        assert set(result) == {"3"}

    async def test_fetch_and_normalize_keeps_heat_data_when_extras_fail(self):
        """Extra-type failure never changes the heat payload."""
        api = MagicMock()
        api.residential_unit = "114582"
        api.delivery_type = 1
        for name in (
            "get_energy_usage", "get_last_data_update", "get_usage_insight",
            "get_residential_unit_detail", "get_usage_per_room",
        ):
            setattr(api, name, AsyncMock(return_value={"x": 1}))
        api.get_filter_status = AsyncMock(return_value=[{"deviceNumber": "1001"}])
        api.get_active_model = AsyncMock(return_value="F59")
        api.get_unit_of_measures = AsyncMock(return_value=[{"value": "eenheid"}])
        api.get_delivery_types = AsyncMock(return_value=[1, 2])

        with patch.object(init_mod, "_fetch_extra_delivery_type", AsyncMock(side_effect=RuntimeError("boom"))):
            data = await init_mod._fetch_and_normalize_api_data(api)

        assert data["filter_status_data"] == [{"deviceNumber": "1001"}]
        assert data["delivery_types"] == [1, 2]
        assert data["extra_delivery_data"] == {}

    async def test_coordinator_dict_includes_extra_data(self):
        """_build_coordinator_return_dict exposes extra data; omitted -> empty dict."""
        kwargs = dict.fromkeys(
            [
                "energy_usage_data", "energy_usage_total", "last_update", "filter_status",
                "usage_insight_data", "usage_insight_last_year_data", "active_model",
                "delivery_types", "residential_unit_detail_data", "usage_this_year",
                "usage_last_year", "room_usage", "unit_of_measures_data",
                "last_successful_sync", "calculated_history", "current_month_calculated",
                "monthly_history_cache", "current_last_update_date", "statistics_tracking",
                "statistics_reinject",
            ]
        )
        api = SimpleNamespace(residential_unit="114582")

        assert init_mod._build_coordinator_return_dict(api, **kwargs)["extra_delivery_data"] == {}
        extra = {"2": {"delivery_type": 2}}
        built = init_mod._build_coordinator_return_dict(api, extra_delivery_data=extra, **kwargs)
        assert built["extra_delivery_data"] == extra
