from typing import Any, Dict, List, Optional
from datetime import datetime
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


def translate_room_code(room_code: str) -> str:
    """Translate room codes to full room names.
    
    Maps common room codes to their English names.
    If no translation exists, returns the original code.
    """
    room_translations = {
        "KA": "bedroom",
        "W": "living room",
    }
    return room_translations.get(room_code, room_code)


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
        MijnTedUsageThisYearSensor(coordinator),
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
    
    def __init__(self, coordinator, device_number: str):
        """Initialize the device sensor."""
        super().__init__(
            coordinator,
            f"device_{device_number}",
            f"device {device_number}"
        )
        self.device_number = device_number
        self._attr_icon = "mdi:radiator"
        # unique_id will be set dynamically in the property based on room name

    @property
    def _device_data(self) -> Optional[Dict[str, Any]]:
        """Get device data from coordinator."""
        filter_status = self.coordinator.data.get("filter_status", [])
        if isinstance(filter_status, list):
            for device in filter_status:
                if isinstance(device, dict) and str(device.get("deviceNumber", "")) == str(self.device_number):
                    return device
        return None

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        device_data = self._device_data
        if device_data and device_data.get("room"):
            # Normalize room name: lowercase and replace spaces/special chars with underscore
            room = device_data.get("room", "").lower().replace(" ", "_")
            # Remove any other special characters that might cause issues
            room = "".join(c if c.isalnum() or c == "_" else "_" for c in room)
            return f"{DOMAIN}_device_{room}_{self.device_number}"
        return f"{DOMAIN}_device_{self.device_number}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        device_data = self._device_data
        if device_data and device_data.get("room"):
            room_code = device_data['room']
            room_name = translate_room_code(room_code)
            return f"MijnTed device {room_name}"
        return f"MijnTed device {self.device_number}"

    @property
    def state(self) -> Any:
        """Return the state of the sensor."""
        device_data = self._device_data
        if device_data:
            return device_data.get("currentReadingValue")
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        device_data = self._device_data
        if device_data:
            unit = device_data.get("unitOfMeasure", "")
            # Translate German/Dutch "Einheiten"/"Eenheden" to "Units"
            if unit in ("Einheiten", "Eenheden"):
                return UNIT_MIJNTED
            return unit if unit else ""
        return ""

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        device_data = self._device_data
        if device_data:
            return {
                "room": device_data.get("room"),
                "device_id": device_data.get("deviceId"),
                "measurement_device_id": device_data.get("measurementDeviceId"),
            }
        return {}

class MijnTedSyncDateSensor(MijnTedSensor):
    """Sensor for last synchronization date."""
    
    def __init__(self, coordinator):
        """Initialize the sync date sensor."""
        super().__init__(coordinator, "sync_date", "last synchronization")
        
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
        super().__init__(coordinator, "residential_unit", "residential unit")
        
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
        super().__init__(coordinator, f"usage_room_{room}", f"usage {room}")
        self.room = room
        self._attr_icon = "mdi:lightning-bolt"

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
        super().__init__(coordinator, "energy_usage", "usage")
        self._attr_icon = "mdi:lightning-bolt"

    def _find_latest_valid_month(self, usage_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find the most recent month with totalEnergyUsage > 0 and averageEnergyUseForBillingUnit != null."""
        if not isinstance(usage_data, dict):
            return None
        
        monthly_usages = usage_data.get("monthlyEnergyUsages", [])
        if not monthly_usages:
            return None
        
        # Parse monthYear format (e.g., "11.2025") and sort by date (most recent first)
        valid_months = []
        for month in monthly_usages:
            if not isinstance(month, dict):
                continue
            
            total_usage = month.get("totalEnergyUsage", 0)
            avg_usage = month.get("averageEnergyUseForBillingUnit")
            
            # Check if this month has valid data
            if (isinstance(total_usage, (int, float)) and float(total_usage) > 0 and 
                avg_usage is not None):
                month_year = month.get("monthYear", "")
                try:
                    # Parse "11.2025" format
                    parts = month_year.split(".")
                    if len(parts) == 2:
                        month_num = int(parts[0])
                        year = int(parts[1])
                        # Create a sortable key (year * 100 + month)
                        sort_key = year * 100 + month_num
                        valid_months.append((sort_key, month))
                except (ValueError, IndexError):
                    continue
        
        # Sort by date descending (most recent first) and return the first valid one
        if valid_months:
            valid_months.sort(key=lambda x: x[0], reverse=True)
            return valid_months[0][1]
        
        return None

    def _find_month_by_identifier(self, usage_data: Dict[str, Any], month_identifier: str) -> Optional[Dict[str, Any]]:
        """Find a specific month entry by monthYear identifier."""
        if not isinstance(usage_data, dict):
            return None
        
        monthly_usages = usage_data.get("monthlyEnergyUsages", [])
        if not monthly_usages:
            return None
        
        for month in monthly_usages:
            if isinstance(month, dict) and month.get("monthYear") == month_identifier:
                return month
        
        return None

    def _extract_month_number(self, month_year: str) -> Optional[int]:
        """Extract month number from monthYear format (e.g., "11.2025" -> 11)."""
        try:
            parts = month_year.split(".")
            if len(parts) == 2:
                return int(parts[0])
        except (ValueError, IndexError):
            pass
        return None

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

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        attributes: Dict[str, Any] = {}
        
        # Get current year usage data
        energy_usage_data = self.coordinator.data.get("energy_usage_data", {})
        if isinstance(energy_usage_data, dict):
            latest_month = self._find_latest_valid_month(energy_usage_data)
            if latest_month:
                # Add the month identifier
                month_year = latest_month.get("monthYear")
                if month_year:
                    attributes["month"] = month_year
                    
                    # Extract month number to find same month in last year
                    month_num = self._extract_month_number(month_year)
                    
                    # Get last year usage data
                    usage_last_year = self.coordinator.data.get("usage_last_year", {})
                    if isinstance(usage_last_year, dict) and month_num:
                        # Find the same month in last year (e.g., if current is "11.2025", find "11.2024")
                        last_year = datetime.now().year - 1
                        last_year_month_identifier = f"{month_num}.{last_year}"
                        last_year_month = self._find_month_by_identifier(usage_last_year, last_year_month_identifier)
                        
                        if last_year_month:
                            # Add last year's average usage from the same month
                            last_year_avg = last_year_month.get("averageEnergyUseForBillingUnit")
                            if last_year_avg is not None:
                                try:
                                    attributes["last_year_average_usage"] = float(last_year_avg)
                                except (ValueError, TypeError):
                                    pass
                            
                            # Add last year's total usage from the same month
                            last_year_total = last_year_month.get("totalEnergyUsage")
                            if last_year_total is not None:
                                try:
                                    attributes["last_year_total_usage"] = float(last_year_total)
                                except (ValueError, TypeError):
                                    pass
                
                # Add average usage for billing unit from this month
                avg_usage = latest_month.get("averageEnergyUseForBillingUnit")
                if avg_usage is not None:
                    try:
                        attributes["average_usage"] = float(avg_usage)
                    except (ValueError, TypeError):
                        pass
        
        return attributes

class MijnTedLastUpdateSensor(MijnTedSensor):
    """Sensor for last update timestamp."""
    
    def __init__(self, coordinator):
        """Initialize the last update sensor."""
        super().__init__(coordinator, "last_update", "last update")
        self._attr_icon = "mdi:clock-outline"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    def _parse_date_to_timestamp(self, date_str: str) -> Optional[str]:
        """Convert date string (DD/MM/YYYY) to ISO 8601 timestamp."""
        if not date_str:
            return None
        
        try:
            # Parse DD/MM/YYYY format
            date_obj = datetime.strptime(date_str.strip(), "%d/%m/%Y")
            # Convert to ISO 8601 format (midnight UTC)
            return date_obj.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
        except (ValueError, AttributeError):
            # If parsing fails, try to return as-is (might already be in correct format)
            return date_str if date_str else None

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        last_update = self.coordinator.data.get('last_update')
        if isinstance(last_update, dict):
            date_str = last_update.get("lastSyncDate") or last_update.get("date")
        else:
            date_str = str(last_update) if last_update else None
        
        if date_str:
            return self._parse_date_to_timestamp(date_str)
        return None

class MijnTedFilterSensor(MijnTedSensor):
    """Sensor for total device readings from all devices."""
    
    def __init__(self, coordinator):
        """Initialize the device readings sensor."""
        super().__init__(coordinator, "filter", "total usage")
        self._attr_icon = "mdi:lightning-bolt"
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
    
    def _calculate_last_year_total(self) -> Optional[float]:
        """Calculate total usage from last year's monthly data."""
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
            return float(usage_data.get("total", 0)) if usage_data.get("total") else None
        return float(usage_data) if isinstance(usage_data, (int, float)) else None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        attributes: Dict[str, Any] = {}
        
        filter_status = self.coordinator.data.get('filter_status')
        if isinstance(filter_status, list):
            attributes["devices"] = filter_status
            attributes["device_count"] = len(filter_status)
        
        # Add last year's total usage
        last_year_total = self._calculate_last_year_total()
        if last_year_total is not None:
            attributes["last_year_usage"] = last_year_total
        
        return attributes

class MijnTedActiveModelSensor(MijnTedSensor):
    """Sensor for active model information."""
    
    def __init__(self, coordinator):
        """Initialize the active model sensor."""
        super().__init__(coordinator, "active_model", "active model")
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
        super().__init__(coordinator, "delivery_types", "delivery type")
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
        super().__init__(coordinator, "residential_unit_detail", "residential unit")
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

class MijnTedUsageThisYearSensor(MijnTedSensor):
    """Sensor for this year's usage."""
    
    def __init__(self, coordinator):
        """Initialize the this year usage sensor."""
        super().__init__(coordinator, "usage_this_year", "usage this year")
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
