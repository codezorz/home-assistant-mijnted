"""Exercise per-meter reporting, options, and registry compatibility in real HA."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from custom_components.mijnted.const import CONF_ENABLED_METERS, CONF_PRIMARY_DELIVERY
from tests_native.helpers import DOMAIN, own_id, query, refresh, reporting_entities, settled


def add_meter_sources(api, scenario):
    """Layer synthetic warm/cold water and GJ responses over the primary fixture."""
    scenario.water_total = 3.125
    scenario.cold_total = None
    scenario.heat_failed = False
    api.get_delivery_types.return_value = [2, 1, 3]

    async def authenticate():
        api.delivery_types = await api.get_delivery_types()
        api.delivery_type = api.delivery_types[0]

    api.authenticate.side_effect = authenticate

    async def units(delivery_type=None):
        return [{"value": "m³"}] if str(delivery_type) in {"2", "3"} else [
            {"value": "eenheid"}, {"value": "GJ"},
        ]

    async def model(delivery_type=None):
        return {"value": {"2": "WWZF-AP", "3": "KWZF-AP"}.get(str(delivery_type), "F71")}

    async def latest(delivery_type=None):
        if delivery_type is None:
            delivery_type = api.delivery_type
        if str(delivery_type) in {"2", "3"}:
            return [{**scenario.rows(840.0)[0], "unitOfMeasure": "m³"}] if str(delivery_type) == "2" else []
        return await scenario.latest()

    async def heat_energy(year=None):
        if scenario.heat_failed:
            return {}
        usage = await scenario.energy(year)
        return {"monthlyEnergyUsages": [
            {**row, "unitOfMeasurement": "GJ", "totalEnergyUsage": row["totalEnergyUsage"] / 100,
             "averageEnergyUseForBillingUnit": (average / 100 if average is not None else None)}
            for row in usage["monthlyEnergyUsages"]
            for average in [row["averageEnergyUseForBillingUnit"]]
        ]}

    async def heat_readings(target=None):
        if scenario.heat_failed:
            return []
        rows = await scenario.anchor(target) if target else await scenario.latest()
        return [{**row, "currentReadingValue": row["currentReadingValue"] / 100, "unitOfMeasure": "GJ"} for row in rows]

    async def water_energy(delivery, year=None):
        total = scenario.water_total if delivery == "2" else scenario.cold_total
        if total is None or year != 2026:
            return {}
        return {"monthlyEnergyUsages": [
            {"monthYear": "10.2026", "totalEnergyUsage": total, "unitOfMeasurement": "m³",
             "averageEnergyUseForBillingUnit": 8.0},
            {"monthYear": "11.2026", "totalEnergyUsage": 0, "unitOfMeasurement": "m³",
             "averageEnergyUseForBillingUnit": None},
        ]}

    heat = AsyncMock(residential_unit=api.residential_unit)
    heat.get_energy_usage.side_effect = heat_energy
    heat.get_device_statuses_for_date.side_effect = heat_readings
    heat.get_filter_status.side_effect = heat_readings
    heat.get_last_data_update.side_effect = scenario.last_update
    heat.get_usage_insight.return_value = {"unitType": "GJ", "usage": 8.88}
    water = {key: AsyncMock() for key in ("2", "3")}

    async def warm_energy(year=None):
        return await water_energy("2", year)

    async def cold_energy(year=None):
        return await water_energy("3", year)

    water["2"].get_energy_usage.side_effect = warm_energy
    water["3"].get_energy_usage.side_effect = cold_energy
    api.for_meter = MagicMock(side_effect=lambda delivery, unit: heat if unit == "GJ" else water[delivery])
    api.get_unit_of_measures.side_effect = units
    api.get_active_model.side_effect = model
    api.get_filter_status.side_effect = latest


@pytest.mark.parametrize("prior_version", [1, 2])
async def test_upgrade_preserves_entity_ids_and_monthly_history(hass, runtime, native_api, scenario, prior_version, freezer):
    """Original and entry-scoped IDs retain the same entity, device, and recorded month."""
    registry = entity_registry.async_get(hass)
    entities = reporting_entities(hass, runtime)
    original = entities["monthly_usage"]
    original_reading = entities["device_1"]
    water = registry.async_get_or_create(
        "sensor", DOMAIN, f"{DOMAIN}_{runtime.entry_id}_water_2_device_1", config_entry=runtime,
        device_id=original.device_id, suggested_object_id="existing_water_meter",
    )
    before = await query(hass, {own_id()}, datetime(2026, 10, 1), datetime(2026, 11, 1))
    assert before[own_id()][0]["mean"] == pytest.approx(41)
    assert await hass.config_entries.async_unload(runtime.entry_id)
    # Released versions have legacy registry/cache data with no saved delivery pin.
    hass.config_entries.async_update_entry(runtime, data={
        key: value for key, value in runtime.data.items() if key != CONF_PRIMARY_DELIVERY
    })
    if prior_version == 1:
        registry.async_update_entity(original.entity_id, new_unique_id=f"{DOMAIN}_monthly_usage")
        registry.async_update_entity(original_reading.entity_id, new_unique_id=f"{DOMAIN}_device_KA_1".lower())
        hass.config_entries.async_update_entry(runtime, version=1)
    add_meter_sources(native_api, scenario)
    assert await hass.config_entries.async_setup(runtime.entry_id)
    await settled(hass)
    assert runtime.data[CONF_PRIMARY_DELIVERY] == "1"
    entities = reporting_entities(hass, runtime)
    assert entities["monthly_usage"].entity_id == original.entity_id
    assert entities["monthly_usage"].device_id == original.device_id
    assert entities["device_1"].entity_id == original_reading.entity_id
    assert entities["water_2_device_1"].entity_id == water.entity_id
    warm_device = device_registry.async_get(hass).async_get(entities["water_2_device_1"].device_id)
    assert warm_device.name == "MijnTed Warm water (m³)"
    assert hass.states.get(entities["meter_2_m3_published_usage"].entity_id).state == "3.125"
    assert hass.states.get(entities["meter_2_m3_monthly_usage"].entity_id).state == "unknown"
    assert hass.states.get(entities["meter_1_gj_device_1"].entity_id).attributes["unit_of_measurement"] == "GJ"
    insight = hass.states.get(entities["meter_1_gj_latest_available_insight"].entity_id)
    assert insight.attributes["month_id"] == "10.2026"
    assert insight.attributes["usage_unit"] == "GJ"
    assert any(row.domain == "button" and row.unique_id.endswith("_meter_1_gj_reset_statistics")
               for row in entity_registry.async_entries_for_config_entry(registry, runtime.entry_id))
    water_id = f"{DOMAIN}:{runtime.entry_id}_meter_2_m3_monthly_usage"
    heat_id = f"{DOMAIN}:{runtime.entry_id}_meter_1_gj_monthly_usage"
    start, end = datetime(2026, 10, 1), datetime(2026, 11, 1)
    rows = await query(hass, {own_id(), water_id, heat_id}, start, end)
    assert rows[own_id()] == before[own_id()]
    assert rows[water_id][0]["mean"] == pytest.approx(3.125)
    assert rows[heat_id][0]["mean"] == pytest.approx(0.41)
    # HA debounces device cleanup after moving the existing water entity, then cools down.
    for _ in range(2):
        after_cleanup = dt_util.utcnow() + timedelta(seconds=device_registry.CLEANUP_DELAY + 1)
        freezer.move_to(after_cleanup)
        async_fire_time_changed(hass, after_cleanup)
        await settled(hass)
    assert device_registry.async_get(hass).async_get(original.device_id) is not None


async def test_ambiguous_legacy_history_waits_for_user_binding(hass, runtime, native_api, scenario):
    """Colliding meter numbers without matching model evidence never write to legacy history."""
    entity = reporting_entities(hass, runtime)["monthly_usage"]
    assert await hass.config_entries.async_unload(runtime.entry_id)
    devices = device_registry.async_get(hass)
    devices.async_update_device(entity.device_id, model="Unknown")
    hass.config_entries.async_update_entry(runtime, data={
        key: value for key, value in runtime.data.items() if key != CONF_PRIMARY_DELIVERY
    })
    add_meter_sources(native_api, scenario)
    assert await hass.config_entries.async_setup(runtime.entry_id)
    await settled(hass)
    data = hass.data[DOMAIN][runtime.entry_id].data
    assert data["primary_unresolved"]
    assert CONF_PRIMARY_DELIVERY not in runtime.data
    assert "monthly_history_cache" not in data
    original = hass.states.get(entity.entity_id)
    assert original is None or original.state == "unavailable"
    warm = reporting_entities(hass, runtime)["meter_2_m3_published_usage"]
    assert hass.states.get(warm.entity_id).state == "3.125"

    flow = await hass.config_entries.options.async_init(runtime.entry_id)
    assert flow["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(flow["flow_id"], {CONF_PRIMARY_DELIVERY: "1"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await settled(hass)
    assert runtime.data[CONF_PRIMARY_DELIVERY] == "1"
    assert reporting_entities(hass, runtime)["monthly_usage"].entity_id == entity.entity_id
    rows = await query(hass, {own_id()}, datetime(2026, 10, 1), datetime(2026, 11, 1))
    assert rows[own_id()][0]["mean"] == pytest.approx(41)


async def test_meter_failure_options_and_second_entry_do_not_mix_series(hass, runtime, native_api, scenario):
    """A failed meter and an options reload leave other meters and historical IDs intact."""
    add_meter_sources(native_api, scenario)
    await refresh(hass, runtime)
    entities = reporting_entities(hass, runtime)
    warm = entities["meter_2_m3_published_usage"]
    heating = entities["meter_1_gj_published_usage"]
    cold = entities["meter_3_m3_published_usage"]
    assert hass.states.get(cold.entity_id).state == "unavailable"
    scenario.heat_failed = True
    scenario.water_total = 4.75
    scenario.cold_total = 2.25
    await refresh(hass, runtime)
    assert hass.states.get(warm.entity_id).state == "4.75"
    assert hass.states.get(cold.entity_id).state == "2.25"
    assert hass.states.get(heating.entity_id).state == "unavailable"
    scenario.heat_failed = False
    scenario.water_total = None  # partial analytics does not erase the corrected publication
    await refresh(hass, runtime)
    assert hass.states.get(warm.entity_id).state == "4.75"
    assert hass.states.get(heating.entity_id).state != "unavailable"

    async def select(keys):
        flow = await hass.config_entries.options.async_init(runtime.entry_id)
        assert flow["type"] is FlowResultType.FORM
        result = await hass.config_entries.options.async_configure(flow["flow_id"], {CONF_ENABLED_METERS: keys})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await settled(hass)

    await select(["1_gj", "3_m3"])
    disabled = hass.states.get(warm.entity_id)
    assert disabled is None or disabled.attributes.get("restored") is True
    assert "2_m3" not in hass.data[DOMAIN][runtime.entry_id].data["meter_data"]
    assert entity_registry.async_get(hass).async_get(warm.entity_id).unique_id == warm.unique_id
    await select(["1_gj", "2_m3", "3_m3"])
    assert reporting_entities(hass, runtime)["meter_2_m3_published_usage"].entity_id == warm.entity_id
    assert hass.states.get(warm.entity_id).state == "4.75"

    another = MockConfigEntry(domain=DOMAIN, entry_id="another_entry", version=2, title="Other", data={
        **runtime.data, "name": "Other",
    })
    another.add_to_hass(hass)
    try:
        scenario.water_total = 9.875
        assert await hass.config_entries.async_setup(another.entry_id)
        await settled(hass)
        other = reporting_entities(hass, another)["meter_2_m3_published_usage"]
        assert other.entity_id != warm.entity_id
        assert other.device_id != warm.device_id
        assert hass.states.get(other.entity_id).state == "9.875"
        assert hass.states.get(warm.entity_id).state == "4.75"
        start = datetime(2026, 10, 1, tzinfo=dt_util.get_default_time_zone())
        end = datetime(2026, 11, 1, tzinfo=dt_util.get_default_time_zone())
        first_stat = f"{DOMAIN}:{runtime.entry_id}_meter_2_m3_monthly_usage"
        second_stat = f"{DOMAIN}:{another.entry_id}_meter_2_m3_monthly_usage"
        rows = await query(hass, {first_stat, second_stat}, start, end)
        assert rows[first_stat][0]["mean"] == pytest.approx(4.75)
        assert rows[second_stat][0]["mean"] == pytest.approx(9.875)
    finally:
        assert await hass.config_entries.async_unload(another.entry_id)
        await settled(hass)
