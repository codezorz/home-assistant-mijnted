from typing import List

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_NAME, DEFAULT_NAME, DOMAIN
from .sensors import (
    MijnTedMonthlyUsageSensor,
    MijnTedLastUpdateSensor,
    MijnTedTotalUsageSensor,
    MijnTedActiveModelSensor,
    MijnTedDeliveryTypesSensor,
    MijnTedResidentialUnitDetailSensor,
    MijnTedUnitOfMeasuresSensor,
    MijnTedLastSuccessfulSyncSensor,
    MijnTedDeviceSensor,
    MijnTedAverageMonthlyUsageSensor,
    MijnTedLastYearAverageMonthlyUsageSensor,
    MijnTedLastYearMonthlyUsageSensor,
    MijnTedLatestAvailableInsightSensor,
)
from .sensors.base import MijnTedSensor


def _sanitize_room_for_unique_id(room: str) -> str:
    """Convert a room value to the legacy unique-ID component."""
    sanitized = room.lower().replace(" ", "_")
    return "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in sanitized
    )


def _migrate_device_unique_id(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device_number: str,
    room: str,
) -> None:
    """Migrate the currently active legacy room-based device entity."""
    registry = er.async_get(hass)
    desired_unique_id = MijnTedSensor._build_unique_id(
        entry.entry_id, f"device_{device_number}"
    )
    entry_entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    unique_id_entities = {
        entity.unique_id: entity
        for entity in entry_entities
        if entity.platform == DOMAIN and entity.entity_id.startswith("sensor.")
    }
    if desired_unique_id in unique_id_entities:
        return

    legacy_unique_ids = []
    if room:
        legacy_unique_ids.append(
            f"{DOMAIN}_device_{_sanitize_room_for_unique_id(room)}_{device_number}"
        )
    legacy_unique_ids.append(f"{DOMAIN}_device_{device_number}")

    for legacy_unique_id in legacy_unique_ids:
        entity = unique_id_entities.get(legacy_unique_id)
        if entity:
            registry.async_update_entity(
                entity.entity_id, new_unique_id=desired_unique_id
            )
            return

    matching_number_entities = [
        entity
        for unique_id, entity in unique_id_entities.items()
        if unique_id.startswith(f"{DOMAIN}_device_")
        and unique_id.endswith(f"_{device_number}")
    ]
    if len(matching_number_entities) == 1:
        registry.async_update_entity(
            matching_number_entities[0].entity_id,
            new_unique_id=desired_unique_id,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up the Mijnted sensors.
    
    Args:
        hass: Home Assistant instance
        entry: Configuration entry
        async_add_entities: Callback to add entities
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    config_name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    
    sensors: List[SensorEntity] = [
        MijnTedMonthlyUsageSensor(coordinator, entry.entry_id, config_name=config_name),
        MijnTedLastUpdateSensor(coordinator, entry.entry_id, config_name=config_name),
        MijnTedTotalUsageSensor(coordinator, entry.entry_id, config_name=config_name),
        MijnTedActiveModelSensor(coordinator, entry.entry_id, config_name=config_name),
        MijnTedDeliveryTypesSensor(coordinator, entry.entry_id, config_name=config_name),
        MijnTedResidentialUnitDetailSensor(coordinator, entry.entry_id, config_name=config_name),
        MijnTedUnitOfMeasuresSensor(coordinator, entry.entry_id, config_name=config_name),
        MijnTedLastSuccessfulSyncSensor(coordinator, entry.entry_id, config_name=config_name),
        MijnTedAverageMonthlyUsageSensor(coordinator, entry.entry_id, config_name=config_name),
        MijnTedLastYearAverageMonthlyUsageSensor(coordinator, entry.entry_id, config_name=config_name),
        MijnTedLastYearMonthlyUsageSensor(coordinator, entry.entry_id, config_name=config_name),
        MijnTedLatestAvailableInsightSensor(coordinator, entry.entry_id, config_name=config_name),
    ]
    
    filter_status = coordinator.data.get("filter_status", [])
    if isinstance(filter_status, list):
        seen_devices = set()
        for device in filter_status:
            if isinstance(device, dict):
                device_number = device.get("deviceNumber")
                if device_number is not None:
                    device_id = str(device_number)
                    if device_id not in seen_devices:
                        seen_devices.add(device_id)
                        _migrate_device_unique_id(
                            hass,
                            entry,
                            device_id,
                            str(device.get("room") or ""),
                        )
                        sensors.append(MijnTedDeviceSensor(coordinator, device_id, entry.entry_id, config_name=config_name))
    
    async_add_entities(sensors, True)
