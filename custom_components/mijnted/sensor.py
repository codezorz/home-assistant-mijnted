"""Sensor platform setup for MijnTed integration."""
from typing import List
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN
from .sensors import (
    MijnTedThisMonthUsageSensor,
    MijnTedLastUpdateSensor,
    MijnTedTotalUsageSensor,
    MijnTedActiveModelSensor,
    MijnTedDeliveryTypesSensor,
    MijnTedResidentialUnitDetailSensor,
    MijnTedUnitOfMeasuresSensor,
    MijnTedThisYearUsageSensor,
    MijnTedLastYearUsageSensor,
    MijnTedLastSuccessfulSyncSensor,
    MijnTedDeviceSensor,
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
    
    sensors: List[SensorEntity] = [
        MijnTedThisMonthUsageSensor(coordinator),
        MijnTedLastUpdateSensor(coordinator),
        MijnTedTotalUsageSensor(coordinator),
        MijnTedActiveModelSensor(coordinator),
        MijnTedDeliveryTypesSensor(coordinator),
        MijnTedResidentialUnitDetailSensor(coordinator),
        MijnTedUnitOfMeasuresSensor(coordinator),
        MijnTedThisYearUsageSensor(coordinator),
        MijnTedLastYearUsageSensor(coordinator),
        MijnTedLastSuccessfulSyncSensor(coordinator),
    ]
    
    # Add individual device sensors dynamically
    # Note: Room usage sensors are not created here as device sensors already include room information
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
                        sensors.append(MijnTedDeviceSensor(coordinator, device_id))
    
    async_add_entities(sensors, True)
