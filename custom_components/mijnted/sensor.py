from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN, UNIT_MIJNTED

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    sensors = [
        MijnTedEnergySensor(coordinator),
        MijnTedLastUpdateSensor(coordinator),
        MijnTedFilterSensor(coordinator),
        MijnTedActiveModelSensor(coordinator),
        MijnTedDeliveryTypesSensor(coordinator),
        MijnTedResidentialUnitDetailSensor(coordinator),
        MijnTedUsageLastYearSensor(coordinator),
        MijnTedUsageThisYearSensor(coordinator),
    ]
    
    # Add room usage sensors
    for room in coordinator.data.get("room_usage", {}):
        sensors.append(MijnTedRoomUsageSensor(coordinator, room))
    
    async_add_entities(sensors, True)

class MijnTedSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, sensor_type, name):
        super().__init__(coordinator)
        self.sensor_type = sensor_type
        self._name = name

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.sensor_type}"

    @property
    def name(self):
        return f"MijnTed {self._name}"

class MijnTedDeviceSensor(MijnTedSensor):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, f"device_{device['deviceNumber']}", f"Device {device['deviceNumber']} ({device['room']})")
        self.device = device

    @property
    def unique_id(self):
        return f"{DOMAIN}_device_{self.device['deviceNumber']}"

    @property
    def state(self):
        return self.device['currentReadingValue']

    @property
    def unit_of_measurement(self):
        return self.device['unitOfMeasure']

    @property
    def extra_state_attributes(self):
        return {
            "room": self.device['room'],
            "device_id": self.device['deviceId'],
            "measurement_device_id": self.device['measurementDeviceId'],
        }

class MijnTedSyncDateSensor(MijnTedSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator, "sync_date", "Last synchronization")
        
    @property
    def device_class(self):
        return SensorDeviceClass.TIMESTAMP

    @property
    def state(self):
        return self.coordinator.data.get("sync_date")

class MijnTedResidentialUnitSensor(MijnTedSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator, "residential_unit", "Residential unit")
        
    @property
    def state(self):
        return self.coordinator.data.get("residential_unit")

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

class MijnTedUsageSensor(MijnTedSensor):
    def __init__(self, coordinator, period, name):
        super().__init__(coordinator, f"usage_{period}", name)
        self.period = period

    @property
    def state(self):
        return self.coordinator.data.get("usage", {}).get(self.period)

    @property
    def state_class(self):
        return SensorStateClass.TOTAL

    @property
    def unit_of_measurement(self):
        return UNIT_MIJNTED

class MijnTedRoomUsageSensor(MijnTedSensor):
    def __init__(self, coordinator, room):
        super().__init__(coordinator, f"usage_room_{room}", f"Usage {room}")
        self.room = room

    @property
    def state(self):
        return self.coordinator.data.get("room_usage", {}).get(self.room)

    @property
    def state_class(self):
        return SensorStateClass.TOTAL

    @property
    def unit_of_measurement(self):
        return UNIT_MIJNTED

class MijnTedInsightSensor(MijnTedSensor):
    def __init__(self, coordinator, insight_type, name):
        super().__init__(coordinator, f"insight_{insight_type}", name)
        self.insight_type = insight_type

    @property
    def state(self):
        return self.coordinator.data.get("insights", {}).get(self.insight_type)

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def unit_of_measurement(self):
        return UNIT_MIJNTED

class MijnTedEnergySensor(MijnTedSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator, "energy_usage", "Energy Usage")

    @property
    def state(self):
        return self.coordinator.data.get("energy_usage")

    @property
    def unit_of_measurement(self):
        return UNIT_MIJNTED

class MijnTedLastUpdateSensor(MijnTedSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator, "last_update", "Last Update")

    @property
    def state(self):
        return self.coordinator.data.get('last_update')

    @property
    def device_class(self):
        return SensorDeviceClass.TIMESTAMP

class MijnTedFilterSensor(MijnTedSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator, "filter", "Filter")

    @property
    def state(self):
        return self.coordinator.data.get('filter_status')

    @property
    def unit_of_measurement(self):
        return UNIT_MIJNTED

class MijnTedActiveModelSensor(MijnTedSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator, "active_model", "Active model")

    @property
    def state(self):
        return self.coordinator.data.get("active_model")

class MijnTedDeliveryTypesSensor(MijnTedSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator, "delivery_types", "Delivery types")

    @property
    def state(self):
        return ", ".join(self.coordinator.data.get("delivery_types", []))

class MijnTedResidentialUnitDetailSensor(MijnTedSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator, "residential_unit_detail", "Residential unit detail")

    @property
    def state(self):
        return self.coordinator.data.get("residential_unit")

    @property
    def extra_state_attributes(self):
        return self.coordinator.data.get("residential_unit_detail", {})

class MijnTedUsageLastYearSensor(MijnTedSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator, "usage_last_year", "Usage last year")

    @property
    def state(self):
        return self.coordinator.data.get("usage_last_year", {}).get("total")

    @property
    def extra_state_attributes(self):
        return self.coordinator.data.get("usage_last_year", {})

class MijnTedUsageThisYearSensor(MijnTedSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator, "usage_this_year", "Usage this year")

    @property
    def state(self):
        return self.coordinator.data.get("usage_this_year", {}).get("total")

    @property
    def extra_state_attributes(self):
        return self.coordinator.data.get("usage_this_year", {})
