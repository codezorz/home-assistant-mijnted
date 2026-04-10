from typing import List

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

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
        MijnTedMonthlyUsageSensor(coordinator, config_name=config_name),
        MijnTedLastUpdateSensor(coordinator, config_name=config_name),
        MijnTedTotalUsageSensor(coordinator, config_name=config_name),
        MijnTedActiveModelSensor(coordinator, config_name=config_name),
        MijnTedDeliveryTypesSensor(coordinator, config_name=config_name),
        MijnTedResidentialUnitDetailSensor(coordinator, config_name=config_name),
        MijnTedUnitOfMeasuresSensor(coordinator, config_name=config_name),
        MijnTedLastSuccessfulSyncSensor(coordinator, config_name=config_name),
        MijnTedAverageMonthlyUsageSensor(coordinator, config_name=config_name),
        MijnTedLastYearAverageMonthlyUsageSensor(coordinator, config_name=config_name),
        MijnTedLastYearMonthlyUsageSensor(coordinator, config_name=config_name),
        MijnTedLatestAvailableInsightSensor(coordinator, config_name=config_name),
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
                        sensors.append(MijnTedDeviceSensor(coordinator, device_id, config_name=config_name))
    
    async_add_entities(sensors, True)
