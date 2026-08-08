from typing import List

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .sensors.base import is_superseded_meter, radiographic_rooms
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
    store = hass.data[DOMAIN][entry.entry_id]
    coordinators = store["coordinators"]
    meters = store["meters"]

    sensors: List[SensorEntity] = []
    for meter in meters:
        coordinator = coordinators.get(meter.key)
        if coordinator is None:
            continue
        sensors.extend(_build_meter_sensors(coordinator))

    async_add_entities(sensors, True)


def _build_meter_sensors(coordinator) -> List[SensorEntity]:
    """Build the full sensor set for a single meter's coordinator.

    Meter identity (delivery type / unit / label) is derived by each sensor from
    the per-meter coordinator data, so unique_ids and devices are namespaced.
    """
    sensors: List[SensorEntity] = [
        MijnTedMonthlyUsageSensor(coordinator),
        MijnTedLastUpdateSensor(coordinator),
        MijnTedTotalUsageSensor(coordinator),
        MijnTedActiveModelSensor(coordinator),
        MijnTedDeliveryTypesSensor(coordinator),
        MijnTedResidentialUnitDetailSensor(coordinator),
        MijnTedUnitOfMeasuresSensor(coordinator),
        MijnTedLastSuccessfulSyncSensor(coordinator),
        MijnTedAverageMonthlyUsageSensor(coordinator),
        MijnTedLastYearAverageMonthlyUsageSensor(coordinator),
        MijnTedLastYearMonthlyUsageSensor(coordinator),
        MijnTedLatestAvailableInsightSensor(coordinator)
    ]

    data = coordinator.data or {}
    filter_status = data.get("filter_status", [])
    if isinstance(filter_status, list):
        radio_rooms = radiographic_rooms(filter_status)
        seen_devices = set()
        for device in filter_status:
            if isinstance(device, dict):
                if is_superseded_meter(device, radio_rooms):
                    continue
                device_number = device.get("deviceNumber")
                if device_number is not None:
                    device_id = str(device_number)
                    if device_id not in seen_devices:
                        seen_devices.add(device_id)
                        sensors.append(MijnTedDeviceSensor(coordinator, device_id))

    return sensors
