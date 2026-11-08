"""Locale completeness, dynamic naming, and external-series compatibility."""

import asyncio
from datetime import datetime, timezone
from string import Formatter
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mijnted import localization
from custom_components.mijnted.config_flow import MijnTedConfigFlow, MijnTedOptionsFlowHandler
from custom_components.mijnted.const import DEFAULT_POLLING_INTERVAL, MIN_POLLING_INTERVAL, MAX_POLLING_INTERVAL
from custom_components.mijnted.sensor import async_setup_entry
from custom_components.mijnted.sensors import base
from custom_components.mijnted.sensors.button import MijnTedResetStatisticsButton
from custom_components.mijnted.sensors.device import MijnTedDeviceSensor
from custom_components.mijnted.sensors.diagnostics import MijnTedUnitOfMeasuresSensor
from custom_components.mijnted.sensors.usage import (
    MijnTedAverageMonthlyUsageSensor,
    MijnTedLastYearAverageMonthlyUsageSensor,
    MijnTedLastYearMonthlyUsageSensor,
    MijnTedMonthlyUsageSensor,
    MijnTedPublishedUsageSensor,
)
from custom_components.mijnted.sensors.water import MijnTedWaterMeterSensor
from tests.conftest import flattened_resources, translation_resources


def labels(language):
    """Build immutable label resources without exercising native HA fallback."""
    return localization.MijnTedTranslations(
        flattened_resources("entity", language), flattened_resources("common", language),
    )


class TestTranslationResources:
    """Guard coverage and the custom-integration translation format."""

    @pytest.mark.parametrize("language", ["en", "nl", "de"])
    def test_matching_keys_and_placeholders(self, language):
        """All shipped locales -> matching, nonempty, fully resolved strings."""
        english = translation_resources("en")
        localized = translation_resources(language)
        assert set(localized) == {"config", "options", "entity", "common", "exceptions"}

        def compare(source, target):
            if isinstance(source, dict):
                assert isinstance(target, dict)
                assert source.keys() == target.keys()
                for key in source:
                    compare(source[key], target[key])
            else:
                assert isinstance(target, str) and target.strip() == target and target
                assert "[%key:" not in target
                placeholders = lambda text: {field for _, field, _, _ in Formatter().parse(text) if field}
                assert placeholders(source) == placeholders(target)

        compare(english, localized)

    async def test_every_created_entity_has_a_connected_translation(self):
        """The registered sensor/button inventory -> no unused or missing name keys."""
        coordinator = SimpleNamespace(data={
            "filter_status": [{"deviceNumber": "7", "room": "W"}],
            "extra_delivery_data": {"2": {
                "active_model": "WWZF-AP",
                "filter_status": [{"deviceNumber": "8", "room": "KA", "unitOfMeasure": "m³"}],
            }},
        }, async_add_listener=MagicMock())
        hass = MagicMock()
        hass.config.language = "en"
        hass.config.components = set()
        hass.data = {"mijnted": {"entry": coordinator}}
        entry = SimpleNamespace(entry_id="entry", data={}, async_on_unload=MagicMock())
        add = MagicMock()
        await async_setup_entry(hass, entry, add)
        sensors = add.call_args.args[0]
        keys = {sensor._attr_translation_key for sensor in sensors}
        assert keys == set(translation_resources()["entity"]["sensor"])
        assert all(sensor.name for sensor in sensors)
        button = MijnTedResetStatisticsButton(coordinator, "entry")
        assert button._attr_translation_key in translation_resources()["entity"]["button"]
        assert not hasattr(button, "_attr_name")

    async def test_loading_uses_ha_language_and_api(self):
        """An installation language -> both categories requested through HA."""
        hass = SimpleNamespace(config=SimpleNamespace(language="nl"))
        loader = AsyncMock(side_effect=[flattened_resources("entity", "nl"), flattened_resources("common", "nl")])
        with patch.object(localization, "async_get_translations", loader):
            translated = await localization.async_load_translations(hass)
        assert loader.await_args_list[0].args == (hass, "nl", "entity", {"mijnted"})
        assert loader.await_args_list[1].args == (hass, "nl", "common", {"mijnted"})
        assert translated.room_label("W") == "woonkamer"

    @pytest.mark.parametrize("language", ["en", "nl", "de"])
    def test_supported_entity_and_shared_label_structure(self, language):
        """Labels use supported schema sections and slug keys, never custom room sections."""
        resource = translation_resources(language)
        slug = re.compile(r"[a-z0-9]+(?:[_-][a-z0-9]+)*\Z")
        assert all(slug.fullmatch(key) for key in resource["common"])
        assert all(isinstance(value, str) for value in resource["common"].values())
        for platform in resource["entity"].values():
            for key, entity in platform.items():
                assert slug.fullmatch(key)
                assert set(entity) <= {"name", "state", "state_attributes", "unit_of_measurement"}
                for state_key, text in entity.get("state", {}).items():
                    assert slug.fullmatch(state_key) and "{" not in text
                for attribute_key, attribute in entity.get("state_attributes", {}).items():
                    assert slug.fullmatch(attribute_key)
                    assert set(attribute) <= {"name", "state"}
                    assert "{" not in attribute["name"]
                    for state_key, text in attribute.get("state", {}).items():
                        assert slug.fullmatch(state_key) and "{" not in text

    @pytest.mark.parametrize("language", ["en", "nl", "de"])
    async def test_flow_fields_and_polling_guidance_follow_actual_forms(self, language):
        """All actual form fields and runtime interval limits -> connected translated labels."""
        flow = MijnTedConfigFlow()
        flow.hass = MagicMock()
        flow.context = {"entry_id": "entry"}
        flow.hass.config_entries.async_get_entry.return_value = SimpleNamespace(data={})
        flow.async_show_form = MagicMock(side_effect=lambda **kwargs: kwargs)
        options = MijnTedOptionsFlowHandler(SimpleNamespace(data={}))
        options.async_show_form = MagicMock(side_effect=lambda **kwargs: kwargs)
        forms = [
            ("config", await flow.async_step_user()),
            ("config", await flow.async_step_reauth_confirm()),
            ("options", await options.async_step_init()),
        ]
        resource = translation_resources(language)
        for category, form in forms:
            text = resource[category]["step"][form["step_id"]]
            assert set(text["data"]) == {marker.schema for marker in form["data_schema"].schema}
            placeholders = form["description_placeholders"]
            assert placeholders["minimum"] == str(MIN_POLLING_INTERVAL)
            assert placeholders["maximum"] == str(MAX_POLLING_INTERVAL)
            assert placeholders["default"] == str(int(DEFAULT_POLLING_INTERVAL.total_seconds()))
            rendered = text["description"].format(**placeholders)
            assert str(MIN_POLLING_INTERVAL) in rendered and str(MAX_POLLING_INTERVAL) in rendered


class TestDynamicNames:
    """Keep dynamic presentation separate from stable device and entity identity."""

    @pytest.mark.parametrize(("language", "expected"), [
        ("en", "Device bedroom"), ("nl", "Apparaat slaapkamer"), ("de", "Gerät Schlafzimmer"),
    ])
    def test_known_room_names_and_runtime_changes(self, language, expected):
        """Known room followed by user room/missing room -> names change, IDs do not."""
        row = {"deviceNumber": "42", "room": "KA", "currentReadingValue": 12, "unitOfMeasure": "Eenheden"}
        coordinator = SimpleNamespace(data={"filter_status": [row]}, mijnted_translations=labels(language))
        sensor = MijnTedDeviceSensor(coordinator, "42", "entry", config_name="MijnHOME")
        assert sensor.name == expected
        identity = sensor.unique_id
        assert identity == "mijnted_entry_device_42"
        assert sensor.state == 12
        assert sensor.unit_of_measurement == "Units"
        assert sensor.extra_state_attributes["room"] == "KA"
        sensor.async_write_ha_state = MagicMock()
        for room, context in [("My HVAC Room", "My HVAC Room"), ("NEW", "NEW"), (None, "42")]:
            row["room"] = room
            sensor._handle_coordinator_update()
            assert sensor._attr_translation_placeholders == {"context": context}
            assert sensor.name.endswith(context)
            assert sensor.unique_id == identity
        sensor.coordinator.data["filter_status"] = []
        sensor._handle_coordinator_update()
        assert sensor.name.endswith("42")

    @pytest.mark.parametrize(("language", "expected"), [
        ("en", "Warm water meter living room"),
        ("nl", "Warmwatermeter woonkamer"),
        ("de", "Warmwasserzähler Wohnzimmer"),
    ])
    def test_water_kind_room_and_unknown_kind(self, language, expected):
        """A water meter -> translated context and recovered kind without identity changes."""
        row = {"deviceNumber": "7", "room": "W", "currentReadingValue": 4}
        delivery = {"active_model": "WWZF-AP", "filter_status": [row]}
        coordinator = SimpleNamespace(data={"extra_delivery_data": {"7": delivery}}, mijnted_translations=labels(language))
        sensor = MijnTedWaterMeterSensor(coordinator, "7", "7", "entry")
        assert sensor.name == expected
        identity = sensor._attr_unique_id
        assert sensor.native_value == 4
        assert sensor._attr_native_unit_of_measurement == "m³"
        sensor.async_write_ha_state = MagicMock()
        delivery["active_model"] = "MYSTERY"
        row["room"] = "Hall HVAC"
        sensor._handle_coordinator_update()
        assert sensor.name == labels(language).common_label("water_meter_generic") + " Hall HVAC"
        assert sensor._attr_unique_id == identity


class TestDiagnosticUnitValues:
    """Translate known descriptions without localizing recorder units or API payloads."""

    @pytest.mark.parametrize("unit", [
        {"value": "eenheid", "displayName": "Eenheden"},
        {"value": "eenheid"},
        {"value": "EENHEID", "displayName": "Einheiten"},
        {"displayName": "Eenheden"},
        {"displayName": "Einheiten"},
        {"displayName": "Units"},
        {"value": "new-api-code", "displayName": "  eEnHeDeN  "},
    ])
    def test_known_values_use_a_language_independent_state(self, unit):
        """Known identifier or label -> stable units state, retaining the original payload."""
        coordinator = SimpleNamespace(data={"unit_of_measures": [unit]})
        sensor = MijnTedUnitOfMeasuresSensor(coordinator, "entry")
        assert sensor.native_value == "units"
        assert sensor.options == ["units"]
        assert sensor.extra_state_attributes == {"unit_of_measures": [unit]}
        assert sensor._attr_unique_id == "mijnted_entry_unit_of_measures"

    @pytest.mark.parametrize("description", ["m3", "m³", "kWh", "Future API Unit", "  Custom Units  "])
    def test_unknown_descriptions_remain_verbatim(self, description):
        """Unrecognized descriptions and unit symbols -> valid raw enum state, never guessed."""
        unit = {"value": "unrecognized", "displayName": description}
        sensor = MijnTedUnitOfMeasuresSensor(SimpleNamespace(data={"unit_of_measures": [unit]}), "entry")
        assert sensor.native_value == description
        assert description in sensor.options
        assert sensor.extra_state_attributes["unit_of_measures"] == [unit]

    @pytest.mark.parametrize("initial", ["Eenheden", "m³"])
    def test_partial_failures_keep_known_or_raw_last_value(self, initial):
        """Empty/malformed/missing unit data -> retain the last state and valid enum options."""
        coordinator = SimpleNamespace(data={"unit_of_measures": [{"displayName": initial}]})
        sensor = MijnTedUnitOfMeasuresSensor(coordinator, "entry")
        expected = "units" if initial == "Eenheden" else initial
        assert sensor.native_value == expected
        for data in ({"unit_of_measures": []}, {"unit_of_measures": [{}]},
                     {"unit_of_measures": [{"displayName": None}]}, {}):
            coordinator.data = data
            assert sensor.native_value == expected
            assert expected in sensor.options

    def test_unknown_until_a_description_or_known_identifier_exists(self):
        """No usable value -> unknown, then later known data is resolved normally."""
        coordinator = SimpleNamespace(data={"unit_of_measures": [{"value": "new-api-code"}]})
        sensor = MijnTedUnitOfMeasuresSensor(coordinator, "entry")
        assert sensor.native_value is None
        coordinator.data["unit_of_measures"] = [{"displayName": "Einheiten"}]
        assert sensor.native_value == "units"


class TestStatisticNames:
    """External-series labels stay consistent regardless of their exporter."""

    @pytest.mark.parametrize(("language", "expected"), [
        ("en", ["Published usage", "Last year monthly usage", "Average monthly usage", "Last year average monthly usage", "Reported daily usage"]),
        ("nl", ["Gepubliceerd verbruik", "Maandverbruik vorig jaar", "Gemiddeld maandverbruik", "Gemiddeld maandverbruik vorig jaar", "Gerapporteerd dagverbruik"]),
        ("de", ["Veröffentlichter Verbrauch", "Monatsverbrauch im Vorjahr", "Durchschnittlicher Monatsverbrauch", "Durchschnittlicher Monatsverbrauch im Vorjahr", "Gemeldeter Tagesverbrauch"]),
    ])
    async def test_report_and_standalone_exporters_agree(self, language, expected):
        """Five report series and standalone views -> identical localized metadata and samples."""
        coordinator = SimpleNamespace(data={
            "monthly_history_cache": {
                "2026-10": {"month_id": "10.2026", "month": 10, "year": 2026,
                            "start_date": "2026-10-01", "end_date": "2026-10-31",
                            "total_usage": 41, "average_usage": 139.05, "devices": []},
                "2025-10": {"month_id": "10.2025", "month": 10, "year": 2025,
                            "start_date": "2025-10-01", "end_date": "2025-10-31",
                            "total_usage": 17, "average_usage": 181.01, "devices": []},
            },
            "daily_usage": {"2026-11-06": 3},
        }, mijnted_translations=labels(language))
        hass = SimpleNamespace(config=SimpleNamespace(components={"recorder"}))
        now = datetime(2026, 11, 7, tzinfo=timezone.utc)
        with (
            patch.object(base.dt_util, "now", return_value=now),
            patch.object(base.dt_util, "get_default_time_zone", return_value=timezone.utc),
            patch.object(base, "async_add_external_statistics", return_value=None) as external,
            patch.object(base, "async_import_statistics", return_value=None),
        ):
            report = MijnTedPublishedUsageSensor(coordinator, "Entry")
            report.hass, report.entity_id = hass, "sensor.custom_report"
            await report._async_inject_statistics()
            imports = {call.args[1]["statistic_id"]: call.args[1:] for call in external.call_args_list}
            assert [imports[f"mijnted:entry_{key}"][0]["name"] for key in localization.STATISTIC_TRANSLATION_KEYS] == expected
            for cls in (MijnTedMonthlyUsageSensor, MijnTedLastYearMonthlyUsageSensor,
                        MijnTedAverageMonthlyUsageSensor, MijnTedLastYearAverageMonthlyUsageSensor):
                external.reset_mock()
                sensor = cls(coordinator, "Entry")
                sensor.hass, sensor.entity_id = hass, "sensor.user_renamed"
                await sensor._async_inject_statistics()
                metadata = external.call_args.args[1]
                assert metadata == imports[metadata["statistic_id"]][0]
            daily_rows = imports["mijnted:entry_reported_daily_usage"][1]
            assert daily_rows == [{"start": datetime(2026, 11, 6, tzinfo=timezone.utc), "mean": 3}]

    async def test_existing_metadata_renamed_without_samples(self):
        """Existing empty-cache series -> names only change; other entries and fields survive."""
        existing = {
            f"mijnted:entry_{key}": (index, {
                "statistic_id": f"mijnted:entry_{key}", "source": "mijnted", "name": "Old default",
                "unit_of_measurement": "Units", "unit_class": None, "has_sum": False, "mean_type": 1,
            }) for index, key in enumerate(localization.STATISTIC_TRANSLATION_KEYS)
        }
        hass = SimpleNamespace(config=SimpleNamespace(components={"recorder"}))
        recorder = SimpleNamespace(async_add_executor_job=AsyncMock(return_value=existing))
        with (
            patch.object(localization, "get_instance", return_value=recorder),
            patch.object(localization, "async_add_external_statistics") as external,
        ):
            await localization.async_refresh_statistic_names(hass, "Entry", labels("nl"))
        requested = recorder.async_add_executor_job.await_args.args[0]
        assert requested.keywords["statistic_ids"] == set(existing)
        assert external.call_count == 5
        for call in external.call_args_list:
            _, metadata, samples = call.args
            assert samples == []
            original = existing[metadata["statistic_id"]][1]
            assert {**metadata, "name": original["name"]} == original
            assert original["name"] == "Old default"

    async def test_no_recorder_means_no_metadata_access(self):
        """Recorder disabled -> no database query or statistic creation."""
        with patch.object(localization, "get_instance") as recorder:
            await localization.async_refresh_statistic_names(
                SimpleNamespace(config=SimpleNamespace(components=set())), "entry", labels("en"),
            )
        recorder.assert_not_called()

    async def test_recorder_name_refresh_failure_does_not_block_sensor_setup(self):
        """A recorder read failure -> sensors still register and naming can retry later."""
        coordinator = SimpleNamespace(
            data={"filter_status": []}, last_update_success=True, async_add_listener=MagicMock(),
        )
        hass = MagicMock()
        hass.config.language = "nl"
        hass.config.components = {"recorder"}
        hass.data = {"mijnted": {"entry": coordinator}}
        entry = SimpleNamespace(entry_id="entry", data={}, async_on_unload=MagicMock())
        recorder = SimpleNamespace(async_add_executor_job=AsyncMock(side_effect=RuntimeError("recorder unavailable")))
        add = MagicMock()
        with patch.object(localization, "get_instance", return_value=recorder):
            await async_setup_entry(hass, entry, add)
        assert add.called
        assert any(sensor._attr_translation_key == "published_usage" for sensor in add.call_args.args[0])


@pytest.fixture
def statistic_name_runtime():
    """Model entry-scoped subscriptions and real asynchronous task cancellation."""
    listeners, unload_callbacks, tasks = [], [], []

    def subscribe(listener):
        """Record an independently removable coordinator subscription."""
        listeners.append(listener)
        return lambda: listeners.remove(listener)

    def create_task(coroutine):
        """Keep real tasks available for deterministic completion/cancellation checks."""
        task = asyncio.create_task(coroutine)
        tasks.append(task)
        return task

    return SimpleNamespace(
        hass=SimpleNamespace(async_create_task=create_task),
        entry=SimpleNamespace(entry_id="entry", async_on_unload=unload_callbacks.append),
        coordinator=SimpleNamespace(
            mijnted_translations=labels("nl"), last_update_success=True, async_add_listener=subscribe,
        ),
        listeners=listeners, unload_callbacks=unload_callbacks, tasks=tasks,
    )


class TestStatisticNameRetry:
    """Metadata failures must not take down sensors or outlive entry unload."""

    async def test_success_needs_no_retry_subscription(self, statistic_name_runtime):
        """Successful metadata refresh -> no ongoing listener or background job."""
        runtime = statistic_name_runtime
        with patch.object(localization, "async_refresh_statistic_names", AsyncMock()):
            await localization.async_setup_statistic_names(runtime.hass, runtime.entry, runtime.coordinator)
        assert runtime.listeners == runtime.unload_callbacks == runtime.tasks == []

    async def test_failed_refresh_retries_after_successful_updates(self, statistic_name_runtime):
        """Repeated recorder failures -> retry on good coordinator updates, then unsubscribe."""
        runtime = statistic_name_runtime
        refresh = AsyncMock(side_effect=[RuntimeError("database unavailable"), RuntimeError("still unavailable"), None])
        with patch.object(localization, "async_refresh_statistic_names", refresh):
            await localization.async_setup_statistic_names(runtime.hass, runtime.entry, runtime.coordinator)
            listener = runtime.listeners[0]
            runtime.coordinator.last_update_success = False
            listener()
            assert runtime.tasks == []
            runtime.coordinator.last_update_success = True
            listener()
            await runtime.tasks[-1]
            assert runtime.listeners == [listener]
            listener()
            await runtime.tasks[-1]
        assert refresh.await_count == 3
        assert runtime.listeners == []
        for unload in runtime.unload_callbacks:
            unload()
        listener()
        assert len(runtime.tasks) == 2

    async def test_unload_cancels_single_inflight_retry(self, statistic_name_runtime):
        """Overlapping updates/unload during a recorder read -> one task, cancelled and detached."""
        runtime = statistic_name_runtime
        entered = asyncio.Event()

        async def refresh(*args):
            """Fail setup, then hold the retried read until cancellation."""
            if not runtime.tasks:
                raise RuntimeError("database unavailable")
            entered.set()
            await asyncio.Event().wait()

        with patch.object(localization, "async_refresh_statistic_names", side_effect=refresh):
            await localization.async_setup_statistic_names(runtime.hass, runtime.entry, runtime.coordinator)
            listener = runtime.listeners[0]
            listener()
            listener()
            assert len(runtime.tasks) == 1
            await entered.wait()
            for unload in runtime.unload_callbacks:
                unload()
            with pytest.raises(asyncio.CancelledError):
                await runtime.tasks[0]
            listener()
        assert runtime.listeners == []
        assert len(runtime.tasks) == 1
