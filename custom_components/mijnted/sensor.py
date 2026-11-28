from typing import List, Set, Tuple

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_ENABLED_METERS, CONF_NAME, DEFAULT_NAME, DOMAIN, UNIT_WATER
from .localization import MijnTedTranslations, async_load_translations, async_setup_statistic_names
from .meters import meter_coordinators
from .sensors import (
    MijnTedMonthlyUsageSensor,
    MijnTedPublishedUsageSensor,
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
    MijnTedWaterMeterSensor,
)
from .sensors.base import MijnTedSensor
from .sensors.water import get_water_deliveries


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
    if not isinstance(getattr(coordinator, "mijnted_translations", None), MijnTedTranslations):
        coordinator.mijnted_translations = await async_load_translations(hass)
    await async_setup_statistic_names(hass, entry, coordinator)
    config_name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    
    primary_added = False

    def _discover_primary_sensors() -> List[SensorEntity]:
        """Restore the legacy group only once a safe delivery binding is available."""
        nonlocal primary_added
        if primary_added or coordinator.data.get("primary_unresolved"):
            return []
        primary_added = True
        classes = (
            MijnTedMonthlyUsageSensor, MijnTedPublishedUsageSensor, MijnTedLastUpdateSensor,
            MijnTedTotalUsageSensor, MijnTedActiveModelSensor, MijnTedDeliveryTypesSensor,
            MijnTedResidentialUnitDetailSensor, MijnTedUnitOfMeasuresSensor, MijnTedLastSuccessfulSyncSensor,
            MijnTedAverageMonthlyUsageSensor, MijnTedLastYearAverageMonthlyUsageSensor,
            MijnTedLastYearMonthlyUsageSensor, MijnTedLatestAvailableInsightSensor,
        )
        sensors = [cls(coordinator, entry.entry_id, config_name=config_name) for cls in classes]
        seen_devices = set()
        for device in coordinator.data.get("filter_status", []):
            if not isinstance(device, dict) or device.get("deviceNumber") is None:
                continue
            device_id = str(device["deviceNumber"])
            if device_id in seen_devices:
                continue
            seen_devices.add(device_id)
            _migrate_device_unique_id(hass, entry, device_id, str(device.get("room") or ""))
            sensors.append(MijnTedDeviceSensor(coordinator, device_id, entry.entry_id, config_name=config_name))
        return sensors

    known_water_devices: Set[Tuple[str, str]] = set()
    known_meter_groups: Set[str] = set()
    known_heat_devices: Set[Tuple[str, str]] = set()
    enabled_meters = entry.data.get(CONF_ENABLED_METERS)

    def _discover_water_sensors() -> List[SensorEntity]:
        """Create water entities only for delivery/device pairs not yet added."""
        new_sensors: List[SensorEntity] = []
        for delivery_type, device_numbers in get_water_deliveries(coordinator.data).items():
            meter_key = f"{delivery_type}_m3"
            if enabled_meters is not None and meter_key not in enabled_meters:
                continue
            meter = coordinator.data.get("meters", {}).get(meter_key)
            for device_number in device_numbers:
                key = (delivery_type, device_number)
                if key in known_water_devices:
                    continue
                known_water_devices.add(key)
                new_sensors.append(
                    MijnTedWaterMeterSensor(
                        coordinator, delivery_type, device_number, entry.entry_id,
                        config_name=config_name, meter=meter,
                    )
                )
        return new_sensors

    def _discover_reporting_sensors() -> List[SensorEntity]:
        """Register each reporting group and newly seen GJ reading exactly once."""
        new_sensors: List[SensorEntity] = []
        for key, view in meter_coordinators(coordinator).items():
            meter = view.mijnted_meter
            scope = meter.scope(entry.entry_id)
            if key not in known_meter_groups:
                known_meter_groups.add(key)
                classes = [
                    MijnTedMonthlyUsageSensor, MijnTedPublishedUsageSensor,
                    MijnTedAverageMonthlyUsageSensor, MijnTedLastYearAverageMonthlyUsageSensor,
                    MijnTedLastYearMonthlyUsageSensor,
                ]
                if meter.unit != UNIT_WATER:
                    classes += [MijnTedLastUpdateSensor, MijnTedLatestAvailableInsightSensor]
                new_sensors.extend(cls(view, scope, config_name=config_name) for cls in classes)
            for row in (view.data or {}).get("filter_status", []):
                number = row.get("deviceNumber")
                if number is not None and (key, str(number)) not in known_heat_devices:
                    known_heat_devices.add((key, str(number)))
                    new_sensors.append(MijnTedDeviceSensor(view, str(number), scope, config_name=config_name))
        return new_sensors

    def _add_new_meter_sensors() -> None:
        """Retry discovery after successful refreshes, including partial recovery."""
        if coordinator.last_update_success:
            new_sensors = _discover_primary_sensors() + _discover_water_sensors() + _discover_reporting_sensors()
            if new_sensors:
                async_add_entities(new_sensors, False)

    sensors = _discover_primary_sensors() + _discover_water_sensors()
    if sensors:
        async_add_entities(sensors, False)
    reporting = _discover_reporting_sensors()
    if reporting:
        async_add_entities(reporting, False)
    entry.async_on_unload(coordinator.async_add_listener(_add_new_meter_sensors))
