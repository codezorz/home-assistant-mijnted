"""Tests for config-entry-scoped entity identity and migration."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import custom_components.mijnted.__init__ as init_mod
from custom_components.mijnted.const import DOMAIN
from custom_components.mijnted.sensor import (
    _migrate_device_unique_id,
    async_setup_entry as async_setup_sensors,
)
from custom_components.mijnted.sensors.base import MijnTedSensor


class TestEntityUniqueId:
    """Verify entity unique IDs are isolated by config entry."""

    def test_unique_ids_differ_between_config_entries(self):
        """Matching sensor keys in different entries -> distinct unique IDs."""
        first = MijnTedSensor._build_unique_id("entry_one", "monthly_usage")
        second = MijnTedSensor._build_unique_id("entry_two", "monthly_usage")

        assert first == "mijnted_entry_one_monthly_usage"
        assert second == "mijnted_entry_two_monthly_usage"
        assert first != second

    async def test_sensor_setup_isolates_two_config_entries(self):
        """Two config entries with matching sensors -> disjoint unique IDs."""
        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "entry_one": SimpleNamespace(
                    data={
                        "filter_status": [
                            {"deviceNumber": "1001", "room": "W"}
                        ]
                    }
                ),
                "entry_two": SimpleNamespace(
                    data={
                        "filter_status": [
                            {"deviceNumber": "1001", "room": "KA"}
                        ]
                    }
                ),
            }
        }
        first_entry = SimpleNamespace(
            entry_id="entry_one", data={"name": "Home"}
        )
        second_entry = SimpleNamespace(
            entry_id="entry_two", data={"name": "Office"}
        )
        first_add = MagicMock()
        second_add = MagicMock()

        await async_setup_sensors(hass, first_entry, first_add)
        await async_setup_sensors(hass, second_entry, second_add)

        first_entities = first_add.call_args.args[0]
        second_entities = second_add.call_args.args[0]
        first_unique_ids = {entity._attr_unique_id for entity in first_entities}
        second_unique_ids = {entity._attr_unique_id for entity in second_entities}
        assert first_unique_ids.isdisjoint(second_unique_ids)
        assert "mijnted_entry_one_device_1001" in first_unique_ids
        assert "mijnted_entry_two_device_1001" in second_unique_ids


class TestEntityUniqueIdMigration:
    """Verify existing registry entities retain their entity IDs during migration."""

    async def test_version_one_entity_gets_scoped_unique_id(self):
        """Version 1 registry entity -> unique ID gains config-entry scope."""
        hass = MagicMock()
        entry = MagicMock()
        entry.version = 1
        entry.entry_id = "entry_one"
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        entity = SimpleNamespace(
            entity_id="sensor.mijnted_monthly_usage",
            platform=DOMAIN,
            unique_id="mijnted_monthly_usage",
        )

        with (
            patch.object(init_mod.er, "async_get", return_value=registry),
            patch.object(
                init_mod.er,
                "async_entries_for_config_entry",
                return_value=[entity],
            ),
        ):
            result = await init_mod.async_migrate_entry(hass, entry)

        assert result is True
        registry.async_update_entity.assert_called_once_with(
            "sensor.mijnted_monthly_usage",
            new_unique_id="mijnted_entry_one_monthly_usage",
        )
        hass.config_entries.async_update_entry.assert_called_once_with(
            entry, version=2
        )

    async def test_room_based_device_id_is_deferred_until_sensor_setup(self):
        """Room-based device unique ID -> config migration leaves it for setup."""
        hass = MagicMock()
        entry = MagicMock()
        entry.version = 1
        entry.entry_id = "entry_one"
        registry = MagicMock()
        entity = SimpleNamespace(
            entity_id="sensor.mijnted_device_living_room_1001",
            platform=DOMAIN,
            unique_id="mijnted_device_living_room_1001",
        )

        with (
            patch.object(init_mod.er, "async_get", return_value=registry),
            patch.object(
                init_mod.er,
                "async_entries_for_config_entry",
                return_value=[entity],
            ),
        ):
            result = await init_mod.async_migrate_entry(hass, entry)

        assert result is True
        registry.async_update_entity.assert_not_called()
        hass.config_entries.async_update_entry.assert_called_once_with(
            entry, version=2
        )

    def test_sensor_setup_migrates_entity_matching_current_room(self):
        """Current room among legacy duplicates -> matching entity is retained."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "entry_one"
        registry = MagicMock()
        entities = [
            SimpleNamespace(
                entity_id="sensor.mijnted_device_living_room_1001",
                platform=DOMAIN,
                unique_id="mijnted_device_living_room_1001",
            ),
            SimpleNamespace(
                entity_id="sensor.mijnted_device_bedroom_1001",
                platform=DOMAIN,
                unique_id="mijnted_device_bedroom_1001",
            ),
        ]

        with (
            patch("custom_components.mijnted.sensor.er.async_get", return_value=registry),
            patch(
                "custom_components.mijnted.sensor.er.async_entries_for_config_entry",
                return_value=entities,
            ),
        ):
            _migrate_device_unique_id(
                hass, entry, device_number="1001", room="bedroom"
            )

        registry.async_update_entity.assert_called_once_with(
            "sensor.mijnted_device_bedroom_1001",
            new_unique_id="mijnted_entry_one_device_1001",
        )

    def test_sensor_setup_migrates_legacy_id_without_room(self):
        """Device without room metadata -> legacy number-only entity is retained."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "entry_one"
        registry = MagicMock()
        entity = SimpleNamespace(
            entity_id="sensor.mijnted_device_1001",
            platform=DOMAIN,
            unique_id="mijnted_device_1001",
        )

        with (
            patch("custom_components.mijnted.sensor.er.async_get", return_value=registry),
            patch(
                "custom_components.mijnted.sensor.er.async_entries_for_config_entry",
                return_value=[entity],
            ),
        ):
            _migrate_device_unique_id(
                hass, entry, device_number="1001", room=""
            )

        registry.async_update_entity.assert_called_once_with(
            "sensor.mijnted_device_1001",
            new_unique_id="mijnted_entry_one_device_1001",
        )

    def test_sensor_setup_migrates_only_room_candidate_after_rename(self):
        """One old-room candidate after rename -> existing entity is retained."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "entry_one"
        registry = MagicMock()
        entity = SimpleNamespace(
            entity_id="sensor.mijnted_device_old_room_1001",
            platform=DOMAIN,
            unique_id="mijnted_device_old_room_1001",
        )

        with (
            patch("custom_components.mijnted.sensor.er.async_get", return_value=registry),
            patch(
                "custom_components.mijnted.sensor.er.async_entries_for_config_entry",
                return_value=[entity],
            ),
        ):
            _migrate_device_unique_id(
                hass, entry, device_number="1001", room="new room"
            )

        registry.async_update_entity.assert_called_once_with(
            "sensor.mijnted_device_old_room_1001",
            new_unique_id="mijnted_entry_one_device_1001",
        )
