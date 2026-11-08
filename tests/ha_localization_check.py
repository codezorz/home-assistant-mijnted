"""Native HA localization checks, run directly outside pytest's global HA stubs.

Run with the Home Assistant 2026.11.0 environment documented in DEVELOPMENT.md:
    python tests/ha_localization_check.py
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import partial
import json
import logging
from pathlib import Path
import sys
import tempfile
from types import MappingProxyType
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from homeassistant import config_entries, loader
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_metadata,
    statistics_during_period,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers import frame
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.recorder import async_initialize_recorder
from homeassistant.helpers.translation import async_get_translations, async_translate_state
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.setup import async_setup_component

from custom_components.mijnted import localization
from custom_components.mijnted.naming import DeviceNameTracker
from custom_components.mijnted.localization import (
    async_load_translations,
    async_refresh_statistic_names,
    async_setup_statistic_names,
)
from custom_components.mijnted.sensors.button import MijnTedResetStatisticsButton
from custom_components.mijnted.sensors.device import MijnTedDeviceSensor
from custom_components.mijnted.sensors.diagnostics import MijnTedLastUpdateSensor, MijnTedUnitOfMeasuresSensor
from custom_components.mijnted.sensors.usage import MijnTedMonthlyUsageSensor
from custom_components.mijnted.sensors.water import MijnTedWaterMeterSensor

LOGGER = logging.getLogger(__name__)


class NativeLocalizationChecks(unittest.IsolatedAsyncioTestCase):
    """Exercise real translation loading, entity registry, and SQLite recorder."""

    async def asyncSetUp(self):
        """Create an isolated HA instance without cloud API access."""
        self.directory = tempfile.TemporaryDirectory()
        self.hass = HomeAssistant(self.directory.name)
        self.hass.config.language = "en"
        self.hass.config.skip_pip = True
        self.hass.config_entries = config_entries.ConfigEntries(self.hass, {})
        loader.async_setup(self.hass)
        frame.async_setup(self.hass)
        await self.hass.config_entries.async_initialize()
        dr.async_setup(self.hass)
        await dr.async_load(self.hass)
        await er.async_load(self.hass)
        self.entry = config_entries.ConfigEntry(
            entry_id="entry", domain="mijnted", title="MijnTed", version=2, minor_version=1,
            source=config_entries.SOURCE_USER, data={}, options={}, unique_id=None,
            discovery_keys=MappingProxyType({}), subentries_data=[],
            state=config_entries.ConfigEntryState.LOADED,
        )
        with patch.object(self.hass.config_entries, "async_setup", AsyncMock(return_value=True)):
            await self.hass.config_entries.async_add(self.entry)
        self.platforms = []

    async def asyncTearDown(self):
        """Stop listeners, worker threads, and delayed registry writes."""
        for platform in self.platforms:
            await platform.async_reset()
        await self.hass.async_stop(force=True)
        self.directory.cleanup()

    async def platform(self, domain="sensor"):
        """Build a real entity platform with native naming resources."""
        platform = EntityPlatform(
            hass=self.hass, logger=LOGGER, domain=domain, platform_name="mijnted",
            platform=None, scan_interval=timedelta(hours=1), entity_namespace=None,
        )
        platform.config_entry = self.entry
        await platform.platform_data.async_load_translations()
        self.platforms.append(platform)
        return platform

    async def test_existing_names_overrides_and_dynamic_placeholders(self):
        """Upgrade/reload in three languages -> stable IDs and preserved user overrides."""
        registry = er.async_get(self.hass)
        initial = registry.async_get_or_create(
            "sensor", "mijnted", "mijnted_entry_monthly_usage",
            suggested_object_id="legacy_usage", original_name="Monthly usage", config_entry=self.entry,
        )
        overridden = registry.async_get_or_create(
            "sensor", "mijnted", "mijnted_entry_device_42",
            suggested_object_id="legacy_room", original_name="Device bedroom", config_entry=self.entry,
        )
        registry.async_update_entity(overridden.entity_id, name="My HVAC Room")
        matching_override = registry.async_get_or_create(
            "sensor", "mijnted", "mijnted_entry_last_update",
            suggested_object_id="legacy_update", original_name="Last update", config_entry=self.entry,
        )
        registry.async_update_entity(matching_override.entity_id, name="Last update")
        for language, monthly, device, water, reset in [
            ("en", "Monthly usage", "Device bedroom", "Warm water meter living room", "Reset statistics"),
            ("nl", "Maandverbruik", "Apparaat slaapkamer", "Warmwatermeter woonkamer", "Statistieken opnieuw opbouwen"),
            ("de", "Monatsverbrauch", "Gerät Schlafzimmer", "Warmwasserzähler Wohnzimmer", "Statistiken neu aufbauen"),
        ]:
            self.hass.config.language = language
            coordinator = DataUpdateCoordinator(self.hass, LOGGER, name="mijnted", update_interval=None, config_entry=self.entry)
            coordinator.mijnted_translations = await async_load_translations(self.hass)
            row = {"deviceNumber": "42", "room": "KA", "currentReadingValue": 10, "unitOfMeasure": "Units"}
            coordinator.async_set_updated_data({
                "filter_status": [row],
                "extra_delivery_data": {"2": {
                    "active_model": "WWZF-AP", "filter_status": [
                        {"deviceNumber": "7", "room": "W", "currentReadingValue": 4},
                    ],
                }},
            })
            sensors = [MijnTedMonthlyUsageSensor(coordinator, "entry"),
                       MijnTedDeviceSensor(coordinator, "42", "entry"),
                       MijnTedWaterMeterSensor(coordinator, "2", "7", "entry"),
                       MijnTedLastUpdateSensor(coordinator, "entry")]
            platform = await self.platform()
            await platform.async_add_entities(sensors)
            await self.hass.async_block_till_done()
            self.assertEqual(sensors[0].entity_id, initial.entity_id)
            self.assertEqual(registry.async_get(initial.entity_id).original_name, monthly)
            self.assertEqual(sensors[1].entity_id, overridden.entity_id)
            self.assertEqual(sensors[1].name, device)
            self.assertEqual(registry.async_get(overridden.entity_id).name, "My HVAC Room")
            self.assertEqual(self.hass.states.get(overridden.entity_id).name, "MijnTed My HVAC Room")
            self.assertEqual(sensors[2].name, water)
            self.assertEqual(sensors[3].entity_id, matching_override.entity_id)
            self.assertEqual(registry.async_get(matching_override.entity_id).name, "Last update")
            row["room"] = "Study HVAC"
            coordinator.async_set_updated_data({**coordinator.data})
            await self.hass.async_block_till_done()
            self.assertTrue(sensors[1].name.endswith("Study HVAC"))
            self.assertEqual(registry.async_get(overridden.entity_id).name, "My HVAC Room")
            button_platform = await self.platform("button")
            button = MijnTedResetStatisticsButton(coordinator, "entry")
            await button_platform.async_add_entities([button])
            self.assertEqual(button.translation_key, "reset_statistics")
            self.assertEqual(button.name, reset)
            await button_platform.async_reset()
            await platform.async_reset()

    async def test_stable_duplicate_names_registry_and_cold_storage_restore(self):
        """Numbered defaults -> retained IDs/overrides, native translations, and durable cold restart."""
        registry = er.async_get(self.hass)
        first = registry.async_get_or_create(
            "sensor", "mijnted", "mijnted_entry_device_2", config_entry=self.entry,
            suggested_object_id="legacy_living_room", original_name="Device living room",
        )
        second = registry.async_get_or_create(
            "sensor", "mijnted", "mijnted_entry_device_10", config_entry=self.entry,
            suggested_object_id="legacy_living_room_2", original_name="Device living room",
        )
        registry.async_update_entity(second.entity_id, name="Radiator by TV")

        def row(number, room, unit="Units"):
            """Build deterministic primary/water reading fixtures."""
            return {"deviceNumber": str(number), "room": room, "currentReadingValue": 12, "unitOfMeasure": unit}

        base_data = {
            "delivery_types": [1], "filter_status": [row(10, "W"), row(9, "KA"), row(2, "W")],
            "extra_delivery_data": {
                "7": {"active_model": "WWZF-AP", "unit_of_measures": [{"value": "m³"}],
                      "filter_status": [row(21, "KA", "m³"), row(20, "KA", "m³")]},
                "3": {"active_model": "KWZF-AP", "unit_of_measures": [{"value": "m³"}],
                      "filter_status": [row(30, "KA", "m³")]},
            },
        }
        new_water_id = None
        for language, device, bedroom, warm, cold in [
            ("en", "Device living room", "Device bedroom", "Warm water meter bedroom", "Cold water meter bedroom"),
            ("nl", "Apparaat woonkamer", "Apparaat slaapkamer", "Warmwatermeter slaapkamer", "Koudwatermeter slaapkamer"),
            ("de", "Gerät Wohnzimmer", "Gerät Schlafzimmer", "Warmwasserzähler Schlafzimmer", "Kaltwasserzähler Schlafzimmer"),
        ]:
            self.hass.config.language = language
            tracker = DeviceNameTracker(self.hass, self.entry.entry_id)
            coordinator = DataUpdateCoordinator(
                self.hass, LOGGER, name="mijnted", update_interval=None, config_entry=self.entry,
            )
            coordinator.mijnted_translations = await async_load_translations(self.hass)
            data = deepcopy(base_data)
            if language != "en":
                data["filter_status"].reverse()
                data["extra_delivery_data"]["7"]["filter_status"].reverse()
            data["device_names"] = await tracker.async_update(data)
            coordinator.async_set_updated_data(data)
            sensors = [
                MijnTedDeviceSensor(coordinator, "2", "entry"),
                MijnTedDeviceSensor(coordinator, "10", "entry"),
                MijnTedDeviceSensor(coordinator, "9", "entry"),
                MijnTedWaterMeterSensor(coordinator, "7", "20", "entry"),
                MijnTedWaterMeterSensor(coordinator, "7", "21", "entry"),
                MijnTedWaterMeterSensor(coordinator, "3", "30", "entry"),
            ]
            platform = await self.platform()
            await platform.async_add_entities(sensors)
            await self.hass.async_block_till_done()
            self.assertEqual(sensors[0].name, device + " 1")
            self.assertEqual(sensors[1].name, device + " 2")
            self.assertEqual(sensors[2].name, bedroom)
            self.assertEqual(sensors[3].name, warm + " 1")
            self.assertEqual(sensors[4].name, warm + " 2")
            self.assertEqual(sensors[5].name, cold)
            self.assertEqual(sensors[0].entity_id, first.entity_id)
            self.assertEqual(sensors[1].entity_id, second.entity_id)
            self.assertEqual(registry.async_get(second.entity_id).name, "Radiator by TV")
            self.assertEqual(self.hass.states.get(second.entity_id).name, "MijnTed Radiator by TV")
            self.assertEqual(self.hass.states.get(first.entity_id).name, "MijnTed " + device + " 1")
            self.assertEqual(sensors[0].extra_state_attributes["room"], "W")

            partial = {"filter_status": [row(10, "W")]}
            partial["device_names"] = await tracker.async_update(partial)
            coordinator.async_set_updated_data(partial)
            await self.hass.async_block_till_done()
            self.assertEqual(sensors[0].name, device + " 1")
            self.assertEqual(sensors[3].name, warm + " 1")
            self.assertEqual(self.hass.states.get(first.entity_id).name, "MijnTed " + device + " 1")

            expanded = deepcopy(base_data)
            expanded["extra_delivery_data"]["7"]["filter_status"].append(row(18, "KA", "m³"))
            expanded["device_names"] = await tracker.async_update(expanded)
            coordinator.async_set_updated_data(expanded)
            added = MijnTedWaterMeterSensor(coordinator, "7", "18", "entry")
            await platform.async_add_entities([added])
            await self.hass.async_block_till_done()
            self.assertEqual(added.name, warm + " 3")
            if new_water_id is None:
                new_water_id = added.entity_id
            self.assertEqual(added.entity_id, new_water_id)
            self.assertEqual(sensors[3].name, warm + " 1")
            await platform.async_reset()

        expected = await tracker.async_update({})
        self.platforms.clear()
        await self.hass.async_stop(force=True)
        self.hass = HomeAssistant(self.directory.name)
        restored = DeviceNameTracker(self.hass, "entry")
        self.assertEqual(await restored.async_update({"filter_status": [row(10, "W")]}), expected)

    async def test_diagnostic_unit_state_translation_and_passthrough(self):
        """Known text -> native translated enum; unknown symbols/text remain valid raw states."""
        self.hass.config.components.add("mijnted")
        legacy = er.async_get(self.hass).async_get_or_create(
            "sensor", "mijnted", "mijnted_entry_unit_of_measures",
            suggested_object_id="legacy_units", original_name="Unit of measures", config_entry=self.entry,
        )
        for language, expected in [("en", "Units"), ("nl", "Eenheden"), ("de", "Einheiten"), ("fr", "Units")]:
            self.hass.config.language = language
            coordinator = DataUpdateCoordinator(
                self.hass, LOGGER, name="mijnted", update_interval=None, config_entry=self.entry,
            )
            raw = [{"value": "eenheid", "displayName": "Eenheden"}]
            coordinator.async_set_updated_data({"unit_of_measures": raw})
            sensor = MijnTedUnitOfMeasuresSensor(coordinator, "entry")
            platform = await self.platform()
            await platform.async_add_entities([sensor])
            await self.hass.async_block_till_done()
            identity = sensor.entity_id
            self.assertEqual(identity, legacy.entity_id)
            self.assertEqual(self.hass.states.get(identity).state, "units")
            self.assertEqual(async_translate_state(
                self.hass, sensor.state, "sensor", "mijnted", sensor.translation_key, sensor.device_class,
            ), expected)
            self.assertEqual(sensor.extra_state_attributes["unit_of_measures"], raw)
            self.assertIsNone(sensor.unit_of_measurement)
            for text in ("m3", "m³", "Custom API Unit"):
                raw = [{"value": "unrecognized", "displayName": text}]
                coordinator.async_set_updated_data({"unit_of_measures": raw})
                await self.hass.async_block_till_done()
                self.assertEqual(self.hass.states.get(identity).state, text)
                self.assertEqual(async_translate_state(
                    self.hass, sensor.state, "sensor", "mijnted", sensor.translation_key, sensor.device_class,
                ), text)
                self.assertEqual(sensor.extra_state_attributes["unit_of_measures"], raw)
                self.assertIn(text, sensor.options)
                self.assertEqual(sensor.entity_id, identity)
            coordinator.async_set_updated_data({"unit_of_measures": []})
            await self.hass.async_block_till_done()
            self.assertEqual(self.hass.states.get(identity).state, "Custom API Unit")
            await platform.async_reset()

    async def test_native_english_fallback(self):
        """Missing labels, unknown languages, and invalid placeholders -> HA's English fallback."""
        directory = Path(self.directory.name) / "fixture"
        translations = directory / "translations"
        translations.mkdir(parents=True)
        english = {"common": {"room_bedroom": "bedroom"},
                   "entity": {"sensor": {"device": {"name": "Device {context}"}}}}
        dutch = {"entity": {"sensor": {"device": {"name": "Apparaat {wrong}"}}}}
        (translations / "en.json").write_text(json.dumps(english), encoding="utf-8")
        (translations / "nl.json").write_text(json.dumps(dutch), encoding="utf-8")
        integration = loader.Integration(
            self.hass, "custom_components.localization_fixture", directory,
            {"domain": "localization_fixture", "name": "Localization fixture", "version": "1.0.0"},
            {"translations"},
        )
        custom = await loader.async_get_custom_components(self.hass)
        custom["localization_fixture"] = integration
        with self.assertLogs("homeassistant.helpers.translation", level="ERROR") as errors:
            common = await async_get_translations(self.hass, "nl", "common", {"localization_fixture"})
        self.assertIn("placeholders", errors.output[0])
        entity = await async_get_translations(self.hass, "nl", "entity", {"localization_fixture"})
        self.assertEqual(common["component.localization_fixture.common.room_bedroom"], "bedroom")
        self.assertEqual(entity["component.localization_fixture.entity.sensor.device.name"], "Device {context}")
        unknown = await async_get_translations(self.hass, "xx", "entity", {"localization_fixture"})
        self.assertEqual(unknown, entity)

    async def test_empty_import_updates_names_without_changing_history(self):
        """A real recorder -> metadata-only localization preserves existing samples and IDs."""
        async_initialize_recorder(self.hass)
        self.assertTrue(await async_setup_component(self.hass, "recorder", {
            "recorder": {"db_url": f"sqlite:///{self.directory.name}/recorder.db", "auto_purge": False, "auto_repack": False},
        }))
        await self.hass.async_start()
        recorder = get_instance(self.hass)
        await self.hass.async_add_executor_job(recorder.block_till_done)
        statistic_id = "mijnted:entry_monthly_usage"
        start = datetime(2026, 10, 1, tzinfo=timezone.utc)
        metadata = {
            "statistic_id": statistic_id, "source": "mijnted", "name": "Published usage",
            "unit_of_measurement": "Units", "unit_class": None,
            "mean_type": StatisticMeanType.ARITHMETIC, "has_sum": False,
        }
        async_add_external_statistics(self.hass, metadata, [{"start": start, "mean": 41}])
        await self.hass.async_add_executor_job(recorder.block_till_done)
        async def read():
            """Read the imported rows through recorder's supported query API."""
            return await recorder.async_add_executor_job(partial(
                statistics_during_period, self.hass, start, start + timedelta(days=1),
                {statistic_id}, "hour", None, {"mean"},
            ))
        before = await read()
        self.assertEqual(before[statistic_id][0]["mean"], 41)
        self.hass.config.language = "nl"
        translated = await async_load_translations(self.hass)
        self.assertEqual(translated.statistic_name("monthly_usage"), "Gepubliceerd verbruik")
        self.assertIn("recorder", self.hass.config.components)
        await async_refresh_statistic_names(self.hass, "entry", translated)
        await self.hass.async_add_executor_job(recorder.block_till_done)
        names = await recorder.async_add_executor_job(partial(get_metadata, self.hass, statistic_ids={statistic_id}))
        self.assertEqual(names[statistic_id][1]["name"], "Gepubliceerd verbruik")
        self.assertEqual(await read(), before)

        self.hass.config.language = "de"
        coordinator = DataUpdateCoordinator(
            self.hass, LOGGER, name="mijnted", update_interval=None, config_entry=self.entry,
        )
        coordinator.mijnted_translations = await async_load_translations(self.hass)
        with (
            patch.object(localization, "get_metadata", side_effect=RuntimeError("recorder read failed")),
            self.assertLogs("custom_components.mijnted.localization", level="WARNING"),
        ):
            await async_setup_statistic_names(self.hass, self.entry, coordinator)
        coordinator.async_set_updated_data({})
        await self.hass.async_block_till_done()
        await self.hass.async_add_executor_job(recorder.block_till_done)
        names = await recorder.async_add_executor_job(partial(get_metadata, self.hass, statistic_ids={statistic_id}))
        self.assertEqual(names[statistic_id][1]["name"], "Veröffentlichter Verbrauch")
        self.assertEqual(await read(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
