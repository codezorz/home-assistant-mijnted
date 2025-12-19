from typing import Any, Dict, List, Optional
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory, DeviceInfo
from .const import DOMAIN, UNIT_MIJNTED

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the Mijnted sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    sensors: List[SensorEntity] = [
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
    room_usage = coordinator.data.get("room_usage", {})
    # Use a set to track normalized room names to avoid duplicates
    seen_rooms = set()
    
    # Handle both dict and list formats
    if isinstance(room_usage, list):
        # Extract room names from list of dicts
        for item in room_usage:
            if isinstance(item, dict):
                room_name = item.get("room") or item.get("roomName") or item.get("name") or item.get("id")
                if room_name:
                    normalized_room = room_name.lower()
                    if normalized_room not in seen_rooms:
                        seen_rooms.add(normalized_room)
                        sensors.append(MijnTedRoomUsageSensor(coordinator, room_name))
    elif isinstance(room_usage, dict):
        # Dict format - iterate over keys
        for room in room_usage:
            normalized_room = room.lower()
            if normalized_room not in seen_rooms:
                seen_rooms.add(normalized_room)
                sensors.append(MijnTedRoomUsageSensor(coordinator, room))
    
    async_add_entities(sensors, True)

class MijnTedSensor(CoordinatorEntity, SensorEntity):
    """Base class for Mijnted sensors."""
    
    def __init__(self, coordinator, sensor_type: str, name: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.sensor_type = sensor_type
        self._name = name
        # Normalize to lowercase to avoid duplicate ID issues with case differences
        self._attr_unique_id = f"{DOMAIN}_{sensor_type.lower()}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        residential_unit = self.coordinator.data.get("residential_unit", "unknown")
        
        # Build device name from address if available
        residential_unit_detail = self.coordinator.data.get("residential_unit_detail", {})
        device_name = "MijnTed"
        
        if isinstance(residential_unit_detail, dict):
            street = residential_unit_detail.get("street", "")
            appartment_no = residential_unit_detail.get("appartmentNo", "")
            zip_code = residential_unit_detail.get("zipCode", "")
            
            # Build address string in format: "Street Number, ZipCode"
            address_parts = []
            if street:
                if appartment_no:
                    address_parts.append(f"{street} {appartment_no}")
                else:
                    address_parts.append(street)
            elif appartment_no:
                address_parts.append(appartment_no)
            
            if zip_code:
                address_parts.append(zip_code)
            
            if address_parts:
                device_name = f"MijnTed - {', '.join(address_parts)}"
        
        return DeviceInfo(
            identifiers={(DOMAIN, residential_unit)},
            name=device_name,
            manufacturer="MijnTed",
            model=self.coordinator.data.get("active_model", "Unknown"),
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"MijnTed {self._name}"

class MijnTedDeviceSensor(MijnTedSensor):
    """Sensor for Mijnted devices."""
    
    def __init__(self, coordinator, device: Dict[str, Any]):
        """Initialize the device sensor."""
        super().__init__(
            coordinator,
            f"device_{device['deviceNumber']}",
            f"Device {device['deviceNumber']} ({device['room']})"
        )
        self.device = device
        self._attr_unique_id = f"{DOMAIN}_device_{device['deviceNumber']}"

    @property
    def state(self) -> Any:
        """Return the state of the sensor."""
        return self.device['currentReadingValue']

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self.device['unitOfMeasure']

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            "room": self.device['room'],
            "device_id": self.device['deviceId'],
            "measurement_device_id": self.device['measurementDeviceId'],
        }

class MijnTedSyncDateSensor(MijnTedSensor):
    """Sensor for last synchronization date."""
    
    def __init__(self, coordinator):
        """Initialize the sync date sensor."""
        super().__init__(coordinator, "sync_date", "Last synchronization")
        
    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class."""
        return SensorDeviceClass.TIMESTAMP

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        return self.coordinator.data.get("sync_date")

class MijnTedResidentialUnitSensor(MijnTedSensor):
    """Sensor for residential unit information."""
    
    def __init__(self, coordinator):
        """Initialize the residential unit sensor."""
        super().__init__(coordinator, "residential_unit", "Residential unit")
        
    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        return self.coordinator.data.get("residential_unit")

    @property
    def entity_category(self) -> EntityCategory:
        """Return the entity category."""
        return EntityCategory.DIAGNOSTIC

class MijnTedUsageSensor(MijnTedSensor):
    """Base class for usage sensors."""
    
    def __init__(self, coordinator, period: str, name: str):
        """Initialize the usage sensor."""
        super().__init__(coordinator, f"usage_{period}", name)
        self.period = period

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self.coordinator.data.get("usage", {}).get(self.period)

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UNIT_MIJNTED

class MijnTedRoomUsageSensor(MijnTedSensor):
    """Sensor for room usage."""
    
    def __init__(self, coordinator, room: str):
        """Initialize the room usage sensor."""
        super().__init__(coordinator, f"usage_room_{room}", f"Usage {room}")
        self.room = room
        self._attr_icon = "mdi:door"

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor."""
        room_usage = self.coordinator.data.get("room_usage", {})
        
        if isinstance(room_usage, dict):
            # Dict format - get by room name (case-insensitive match)
            for room_key, room_value in room_usage.items():
                if room_key.lower() == self.room.lower():
                    if isinstance(room_value, (int, float)):
                        return float(room_value)
                    elif isinstance(room_value, dict):
                        # Extract usage value from dict
                        return float(room_value.get("usage") or room_value.get("value") or room_value.get("total", 0))
            return None
        elif isinstance(room_usage, list):
            # Fallback: if it's still a list, find the room
            for item in room_usage:
                if isinstance(item, dict):
                    room_name = item.get("room") or item.get("roomName") or item.get("name")
                    if room_name and room_name.lower() == self.room.lower():
                        return float(item.get("usage") or item.get("value") or item.get("total", 0))
            return None
        return None

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UNIT_MIJNTED

class MijnTedInsightSensor(MijnTedSensor):
    """Sensor for usage insights."""
    
    def __init__(self, coordinator, insight_type: str, name: str):
        """Initialize the insight sensor."""
        super().__init__(coordinator, f"insight_{insight_type}", name)
        self.insight_type = insight_type

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self.coordinator.data.get("insights", {}).get(self.insight_type)

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.MEASUREMENT

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UNIT_MIJNTED

class MijnTedEnergySensor(MijnTedSensor):
    """Sensor for energy usage."""
    
    def __init__(self, coordinator):
        """Initialize the energy sensor."""
        super().__init__(coordinator, "energy_usage", "Energy Usage")
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor."""
        energy_usage = self.coordinator.data.get("energy_usage")
        if isinstance(energy_usage, (int, float)):
            return float(energy_usage)
        elif isinstance(energy_usage, dict):
            return float(energy_usage.get("total", 0))
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL

class MijnTedLastUpdateSensor(MijnTedSensor):
    """Sensor for last update timestamp."""
    
    def __init__(self, coordinator):
        """Initialize the last update sensor."""
        super().__init__(coordinator, "last_update", "Last Update")
        self._attr_icon = "mdi:clock-outline"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        last_update = self.coordinator.data.get('last_update')
        if isinstance(last_update, dict):
            return last_update.get("lastSyncDate") or last_update.get("date")
        return str(last_update) if last_update else None

class MijnTedFilterSensor(MijnTedSensor):
    """Sensor for total device readings from all devices."""
    
    def __init__(self, coordinator):
        """Initialize the device readings sensor."""
        super().__init__(coordinator, "filter", "Total Device Readings")
        self._attr_icon = "mdi:counter"
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor."""
        filter_status = self.coordinator.data.get('filter_status')
        # API returns an array of device objects
        if isinstance(filter_status, list):
            # Sum all currentReadingValue from all devices
            total = sum(
                float(device.get("currentReadingValue", 0))
                for device in filter_status
                if isinstance(device, dict)
            )
            return total if total > 0 else None
        elif isinstance(filter_status, dict):
            return filter_status.get("filterStatus") or filter_status.get("status")
        return float(filter_status) if isinstance(filter_status, (int, float)) else None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UNIT_MIJNTED
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        filter_status = self.coordinator.data.get('filter_status')
        if isinstance(filter_status, list):
            return {
                "devices": filter_status,
                "device_count": len(filter_status)
            }
        return {}

class MijnTedActiveModelSensor(MijnTedSensor):
    """Sensor for active model information."""
    
    def __init__(self, coordinator):
        """Initialize the active model sensor."""
        super().__init__(coordinator, "active_model", "Active model")
        self._attr_icon = "mdi:tag"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        return self.coordinator.data.get("active_model")

class MijnTedDeliveryTypesSensor(MijnTedSensor):
    """Sensor for delivery types."""
    
    def __init__(self, coordinator):
        """Initialize the delivery types sensor."""
        super().__init__(coordinator, "delivery_types", "Delivery types")
        self._attr_icon = "mdi:package-variant"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        delivery_types = self.coordinator.data.get("delivery_types", [])
        if not delivery_types:
            return None
        # Convert to strings in case they're integers
        return ", ".join(str(dt) for dt in delivery_types)

class MijnTedResidentialUnitDetailSensor(MijnTedSensor):
    """Sensor for residential unit details."""
    
    def __init__(self, coordinator):
        """Initialize the residential unit detail sensor."""
        super().__init__(coordinator, "residential_unit_detail", "Residential unit detail")
        self._attr_icon = "mdi:home"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        return self.coordinator.data.get("residential_unit")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        return self.coordinator.data.get("residential_unit_detail", {})

class MijnTedUsageLastYearSensor(MijnTedSensor):
    """Sensor for last year's usage."""
    
    def __init__(self, coordinator):
        """Initialize the last year usage sensor."""
        super().__init__(coordinator, "usage_last_year", "Usage last year")
        self._attr_icon = "mdi:chart-line"

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor."""
        usage_data = self.coordinator.data.get("usage_last_year", {})
        # API returns {"monthlyEnergyUsages": [...], "averageEnergyUseForBillingUnit": 0}
        if isinstance(usage_data, dict):
            monthly_usages = usage_data.get("monthlyEnergyUsages", [])
            if monthly_usages:
                total = sum(
                    float(month.get("totalEnergyUsage", 0))
                    for month in monthly_usages
                    if isinstance(month, dict)
                )
                return total if total > 0 else None
            return float(usage_data.get("total", 0))
        return float(usage_data) if isinstance(usage_data, (int, float)) else None

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UNIT_MIJNTED

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        usage_data = self.coordinator.data.get("usage_last_year", {})
        return usage_data if isinstance(usage_data, dict) else {}

class MijnTedUsageThisYearSensor(MijnTedSensor):
    """Sensor for this year's usage."""
    
    def __init__(self, coordinator):
        """Initialize the this year usage sensor."""
        super().__init__(coordinator, "usage_this_year", "Usage this year")
        self._attr_icon = "mdi:chart-line"

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor."""
        usage_data = self.coordinator.data.get("usage_this_year", {})
        # API returns {"monthlyEnergyUsages": [...], "averageEnergyUseForBillingUnit": 0}
        if isinstance(usage_data, dict):
            monthly_usages = usage_data.get("monthlyEnergyUsages", [])
            if monthly_usages:
                total = sum(
                    float(month.get("totalEnergyUsage", 0))
                    for month in monthly_usages
                    if isinstance(month, dict)
                )
                return total if total > 0 else None
            return float(usage_data.get("total", 0))
        return float(usage_data) if isinstance(usage_data, (int, float)) else None

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UNIT_MIJNTED

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        usage_data = self.coordinator.data.get("usage_this_year", {})
        return usage_data if isinstance(usage_data, dict) else {}
