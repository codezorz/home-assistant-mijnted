"""Tests for multi-delivery-type meter wiring (issue #50, step 2)."""
import pytest

from custom_components.mijnted import (
    MeterContext,
    _meters_from_detail,
)
from custom_components.mijnted.api import MijntedApi
from custom_components.mijnted.sensors import base


_DETAIL = [
    {"id": 1, "model": "F59", "label": "Heating",
     "units": [{"value": "eenheid", "displayName": "Eenheden"}, {"value": "GJ", "displayName": "GJ"}]},
    {"id": 2, "model": "WWZ", "label": "Warm water", "units": [{"value": "m³", "displayName": "m³"}]},
    {"id": 3, "model": "KWZ", "label": "Cold water", "units": [{"value": "m³", "displayName": "m³"}]},
]


class TestUnitSlug:
    @pytest.mark.parametrize("unit,slug", [
        ("m³", "m3"), ("GJ", "gj"), ("eenheid", "eenheid"), ("Eenheden", "eenheden"),
        (None, "default"), ("", "default"),
    ])
    def test_slug(self, unit, slug):
        assert base.unit_slug(unit) == slug


class TestUnitMapping:
    def test_water_maps_to_volume_and_device_class(self):
        assert base.native_unit_for("m³") is base.UnitOfVolume.CUBIC_METERS
        assert base.device_class_for("m³") is base.SensorDeviceClass.WATER

    def test_gj_passthrough(self):
        assert base.native_unit_for("GJ") == "GJ"
        assert base.device_class_for("GJ") is None

    def test_default_is_units(self):
        assert base.native_unit_for(None) == base.UNIT_MIJNTED
        assert base.device_class_for("eenheid") is None


class TestMeterContext:
    def test_key_and_cache_id(self):
        meter = MeterContext(delivery_type=2, unit="m³", label="Warm water")
        assert meter.key == "2_m3"
        assert meter.cache_id("abc") == "abc_2_m3"

    def test_unit_slug_property(self):
        assert MeterContext(1, "GJ", "Heating").unit_slug == "gj"


class TestMetersFromDetail:
    def test_all_meters(self):
        meters = _meters_from_detail(_DETAIL)
        assert [m.key for m in meters] == ["1_eenheid", "1_gj", "2_m3", "3_m3"]
        assert meters[0].label == "Heating"
        assert meters[2].label == "Warm water"

    def test_enabled_filter(self):
        meters = _meters_from_detail(_DETAIL, enabled_keys={"2_m3", "3_m3"})
        assert [m.key for m in meters] == ["2_m3", "3_m3"]

    def test_type_without_units_gets_default(self):
        meters = _meters_from_detail([{"id": 9, "label": "X", "units": []}])
        assert [m.key for m in meters] == ["9_default"]


class TestApiUnitThreading:
    def test_gj_unit_appends_param(self):
        api = MijntedApi(hass=object(), client_id="c", residential_unit="1", unit="GJ")
        assert api._with_unit("http://x/api/foo/1/1") == "http://x/api/foo/1/1?unitOfMeasure=GJ"

    def test_gj_preserves_existing_query(self):
        api = MijntedApi(hass=object(), client_id="c", residential_unit="1", unit="GJ")
        out = api._with_unit("http://x/api/foo?fromDate=2026-01-01")
        assert out == "http://x/api/foo?fromDate=2026-01-01&unitOfMeasure=GJ"

    def test_water_unit_no_param(self):
        api = MijntedApi(hass=object(), client_id="c", residential_unit="1", unit="m³")
        assert api._with_unit("http://x/api/foo") == "http://x/api/foo"

    @pytest.mark.asyncio
    async def test_pinned_delivery_type_not_overwritten(self, monkeypatch):
        api = MijntedApi(hass=object(), client_id="c", residential_unit="1", delivery_type=2)

        async def fake(method, url, **kwargs):
            return [1, 2, 3]

        monkeypatch.setattr(api, "_make_request", fake)
        await api.get_delivery_types()
        assert api.delivery_type == 2


class TestSupersededMeter:
    def test_old_non_radio_in_radio_room_is_superseded(self):
        fs = [
            {"room": "ALG", "deviceNumber": "0465748", "radiographicMeter": False},
            {"room": "ALG", "deviceNumber": "86066883", "radiographicMeter": True},
        ]
        rooms = base.radiographic_rooms(fs)
        assert base.is_superseded_meter(fs[0], rooms) is True
        assert base.is_superseded_meter(fs[1], rooms) is False

    def test_standalone_non_radio_is_kept(self):
        fs = [{"room": "KEU", "deviceNumber": "1", "radiographicMeter": False}]
        rooms = base.radiographic_rooms(fs)
        assert base.is_superseded_meter(fs[0], rooms) is False


class TestBaseUniqueIdNamespacing:
    def test_namespaced_unique_id(self):
        assert base.MijnTedSensor._namespaced_unique_id(
            "monthly_usage", delivery_type=2, unit="m³"
        ) == "mijnted_2_m3_monthly_usage"

    def test_legacy_unique_id_when_no_delivery_type(self):
        assert base.MijnTedSensor._namespaced_unique_id(
            "monthly_usage"
        ) == "mijnted_monthly_usage"

    def test_name_uses_label(self):
        sensor = object.__new__(base.MijnTedSensor)
        sensor._name = "monthly usage"
        sensor.meter_label = "Warm water"
        assert sensor.name == "MijnTed Warm water monthly usage"
