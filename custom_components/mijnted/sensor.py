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
from .const import DOMAIN, UNIT_MIJNTED, YEAR_TRANSITION_MULTIPLIER
import logging

_LOGGER = logging.getLogger(__name__)


def translate_room_code(room_code: str, hass: Optional[HomeAssistant] = None) -> str:
    """Translate room codes to full room names.
    
    Args:
        room_code: Room code to translate (e.g., "KA", "W")
        hass: Home Assistant instance for translations (optional)
        
    Returns:
        Translated room name or original code if translation not found
    """
    if hass:
        try:
            # Try to get translation from translation files
            translations = hass.data.get("frontend_translations", {}).get("en", {})
            room_translations = translations.get("room_codes", {})
            if room_code in room_translations:
                return room_translations[room_code]
        except Exception:
            pass
    
    # Fallback to hardcoded translations
    room_translations = {
        "KA": "bedroom",
        "W": "living room",
    }
    return room_translations.get(room_code, room_code)


def _extract_monthly_breakdown(usage_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Extract monthly breakdown from usage data.
    
    Args:
        usage_data: Dictionary containing monthlyEnergyUsages list
        
    Returns:
        Dictionary with monthYear as key and month data as value
        
    Example:
        Input: {"monthlyEnergyUsages": [{"monthYear": "11.2025", ...}]}
        Output: {"11.2025": {"total_energy_usage": 100.0, ...}}
    """
    month_breakdown: Dict[str, Dict[str, Any]] = {}
    
    if not isinstance(usage_data, dict):
        return month_breakdown
    
    monthly_usages = usage_data.get("monthlyEnergyUsages", [])
    if not monthly_usages:
        return month_breakdown
    
    for month in monthly_usages:
        if not isinstance(month, dict):
            continue
        
        month_year = month.get("monthYear")
        if not month_year:
            continue
        
        month_data: Dict[str, Any] = {}
        
        # Store all available fields
        if "totalEnergyUsage" in month:
            total_usage = month.get("totalEnergyUsage")
            if total_usage is not None:
                try:
                    month_data["total_energy_usage"] = float(total_usage)
                except (ValueError, TypeError):
                    pass
        
        if "unitOfMeasurement" in month:
            month_data["unit_of_measurement"] = month.get("unitOfMeasurement")
        
        if "averageEnergyUseForBillingUnit" in month:
            avg_usage = month.get("averageEnergyUseForBillingUnit")
            if avg_usage is not None:
                try:
                    month_data["average_energy_use_for_billing_unit"] = float(avg_usage)
                except (ValueError, TypeError):
                    pass
        
        if month_data:
            month_breakdown[month_year] = month_data
    
    return month_breakdown


def _extract_usage_insight_attributes(usage_insight: Dict[str, Any]) -> Dict[str, Any]:
    """Extract attributes from usage insight data.
    
    Args:
        usage_insight: Dictionary containing usage insight data
        
    Returns:
        Dictionary of extracted attributes with snake_case keys
        
    Example:
        Input: {"unitType": "heat", "billingUnitAverageUsage": 50.0}
        Output: {"unit_type": "heat", "billing_unit_average_usage": 50.0}
    """
    attributes: Dict[str, Any] = {}
    
    if not isinstance(usage_insight, dict):
        return attributes
    
    if "unitType" in usage_insight:
        attributes["unit_type"] = usage_insight.get("unitType")
    
    if "billingUnitAverageUsage" in usage_insight:
        billing_avg = usage_insight.get("billingUnitAverageUsage")
        if billing_avg is not None:
            try:
                attributes["billing_unit_average_usage"] = float(billing_avg)
            except (ValueError, TypeError):
                pass
    
    if "usageDifference" in usage_insight:
        usage_diff = usage_insight.get("usageDifference")
        if usage_diff is not None:
            try:
                attributes["usage_difference"] = float(usage_diff)
            except (ValueError, TypeError):
                pass
    
    if "deviceModel" in usage_insight:
        attributes["device_model"] = usage_insight.get("deviceModel")
    
    return attributes


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
        """Initialize the sensor.
        
        Args:
            coordinator: Data update coordinator
            sensor_type: Type identifier for the sensor
            name: Display name for the sensor
        """
        super().__init__(coordinator)
        self.sensor_type = sensor_type
        self._name = name
        # Normalize to lowercase to avoid duplicate ID issues with case differences
        self._attr_unique_id = f"{DOMAIN}_{sensor_type.lower()}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information.
        
        Returns:
            DeviceInfo object with device identifiers and details
        """
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
        """Return the name of the sensor.
        
        Returns:
            Formatted sensor name with "MijnTed" prefix
        """
        return f"MijnTed {self._name}"

class MijnTedDeviceSensor(MijnTedSensor):
    """Sensor for Mijnted devices."""
    
    def __init__(self, coordinator, device_number: str):
        """Initialize the device sensor.
        
        Args:
            coordinator: Data update coordinator
            device_number: Device number identifier
        """
        super().__init__(
            coordinator,
            f"device_{device_number}",
            f"device {device_number}"
        )
        self.device_number = device_number
        self._attr_icon = "mdi:radiator"
        self._attr_suggested_display_precision = 0
        # unique_id will be set dynamically in the property based on room name

    @property
    def _device_data(self) -> Optional[Dict[str, Any]]:
        """Get device data from coordinator.
        
        Returns:
            Device data dictionary if found, None otherwise
        """
        filter_status = self.coordinator.data.get("filter_status", [])
        if isinstance(filter_status, list):
            for device in filter_status:
                if isinstance(device, dict) and str(device.get("deviceNumber", "")) == str(self.device_number):
                    return device
        return None

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor.
        
        Returns:
            Unique identifier string based on room and device number
        """
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
            # Get hass instance from coordinator (DataUpdateCoordinator has hass attribute)
            hass = getattr(self.coordinator, 'hass', None)
            room_name = translate_room_code(room_code, hass)
            return f"MijnTed device {room_name}"
        return f"MijnTed device {self.device_number}"

    @property
    def state(self) -> Any:
        """Return the state of the sensor.
        
        Returns:
            Current reading value from device data
        """
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
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing room, device_id, and measurement_device_id
        """
        device_data = self._device_data
        if device_data:
            return {
                "room": device_data.get("room"),
                "device_id": device_data.get("deviceId"),
                "measurement_device_id": device_data.get("measurementDeviceId"),
            }
        return {}


class MijnTedThisMonthUsageSensor(MijnTedSensor):
    """Sensor for this month's usage."""
    
    def __init__(self, coordinator):
        """Initialize the this month usage sensor."""
        super().__init__(coordinator, "energy_usage", "this month usage")
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_suggested_display_precision = 0

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
        """Find a specific month entry by monthYear identifier.
        
        Args:
            usage_data: Dictionary containing monthly energy usage data
            month_identifier: Month identifier in format "MM.YYYY"
            
        Returns:
            Month dictionary if found, None otherwise
        """
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
        """Extract month number from monthYear format.
        
        Args:
            month_year: Month year string in format "MM.YYYY"
            
        Returns:
            Month number (1-12) if valid, None otherwise
        """
        try:
            parts = month_year.split(".")
            if len(parts) == 2:
                return int(parts[0])
        except (ValueError, IndexError):
            pass
        return None

    def _calculate_measured_months_total(self, usage_data: Dict[str, Any], current_year: int) -> Optional[float]:
        """Calculate the sum of all measured months for the current year.
        
        Args:
            usage_data: Dictionary containing monthly energy usage data
            current_year: Year to calculate for
            
        Returns:
            Total usage for measured months, or None if no valid data
        """
        if not isinstance(usage_data, dict):
            return None
        
        monthly_usages = usage_data.get("monthlyEnergyUsages", [])
        if not monthly_usages:
            return None
        
        total = 0.0
        has_valid_data = False
        
        for month in monthly_usages:
            if not isinstance(month, dict):
                continue
            
            month_year = month.get("monthYear", "")
            if not month_year:
                continue
            
            # Check if this month is for the current year
            try:
                parts = month_year.split(".")
                if len(parts) == 2:
                    year = int(parts[1])
                    if year == current_year:
                        total_usage = month.get("totalEnergyUsage", 0)
                        if isinstance(total_usage, (int, float)) and float(total_usage) > 0:
                            total += float(total_usage)
                            has_valid_data = True
            except (ValueError, IndexError):
                continue
        
        return total if has_valid_data else None

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor.
        
        Returns:
            This month's usage calculated from total minus measured months, or None if not available
        """
        # Get total usage from filter_status (sum of all device readings - cumulative)
        total_usage = None
        filter_status = self.coordinator.data.get('filter_status')
        if isinstance(filter_status, list):
            total = sum(
                float(device.get("currentReadingValue", 0))
                for device in filter_status
                if isinstance(device, dict)
            )
            total_usage = total if total > 0 else None
        
        if total_usage is None:
            return None
        
        # Try to calculate using monthly breakdown (handles year transitions correctly)
        current_year = datetime.now().year
        energy_usage_data = self.coordinator.data.get("energy_usage_data", {})
        measured_months_total = self._calculate_measured_months_total(energy_usage_data, current_year)
        
        if measured_months_total is not None:
            # Use monthly breakdown: total - sum of measured months = unmeasured usage
            this_month_usage = total_usage - measured_months_total
            if this_month_usage >= 0:
                return this_month_usage
        
        # Fallback: Use usage_insight (works during normal months, but breaks at year transition)
        # This is kept for backward compatibility and when monthly data isn't available
        this_year_usage = None
        usage_insight = self.coordinator.data.get("usage_insight", {})
        if isinstance(usage_insight, dict):
            usage = usage_insight.get("usage")
            if usage is not None:
                try:
                    this_year_usage = float(usage)
                except (ValueError, TypeError):
                    pass
        
        # Only use this calculation if we have valid data and it makes sense
        # At year transition, this_year_usage might be very low, causing incorrect high values
        # So we validate: if the difference is suspiciously large, don't trust it
        if this_year_usage is not None and this_year_usage > 0:
            this_month_usage = total_usage - this_year_usage
            # Sanity check: if difference is more than 2x this_year_usage, likely year transition issue
            # In that case, return None to indicate data isn't ready yet
            if this_month_usage >= 0:
                if this_year_usage > 0 and this_month_usage > (this_year_usage * YEAR_TRANSITION_MULTIPLIER):
                    # Suspiciously large difference - likely year transition issue
                    # Return None to wait for monthly data to be available
                    return None
                return this_month_usage
        
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL

    def _is_current_month(self, month_year: str) -> bool:
        """Check if the given month_year string represents the current month."""
        try:
            parts = month_year.split(".")
            if len(parts) == 2:
                month_num = int(parts[0])
                year = int(parts[1])
                now = datetime.now()
                return month_num == now.month and year == now.year
        except (ValueError, IndexError):
            pass
        return False

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing month data, averages, and last year comparisons
        """
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
                    
                    # Check if this is the current month or previous month
                    is_current = self._is_current_month(month_year)
                    if not is_current:
                        attributes["data_for_previous_month"] = True
                    
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
                                    attributes["last_year_usage"] = float(last_year_total)
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
        """Initialize the last update sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "last_update", "last update")
        self._attr_icon = "mdi:clock-outline"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    def _parse_date_to_timestamp(self, date_str: str) -> Optional[str]:
        """Convert date string to ISO 8601 timestamp.
        
        Args:
            date_str: Date string in DD/MM/YYYY format or ISO 8601 format
            
        Returns:
            ISO 8601 timestamp string (YYYY-MM-DDTHH:MM:SSZ) or None if parsing fails
        """
        if not date_str or not isinstance(date_str, str):
            return None
        
        date_str = date_str.strip()
        if not date_str:
            return None
        
        # Check if already in ISO 8601 format
        if "T" in date_str or date_str.count("-") >= 2:
            try:
                # Try to parse as ISO format
                if date_str.endswith("Z"):
                    return date_str
                # Try parsing various ISO formats
                for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"]:
                    try:
                        parsed = datetime.strptime(date_str, fmt)
                        return parsed.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
                    except ValueError:
                        continue
            except (ValueError, AttributeError):
                pass
        
        # Try DD/MM/YYYY format
        try:
            date_obj = datetime.strptime(date_str, "%d/%m/%Y")
            # Convert to ISO 8601 format (midnight UTC)
            return date_obj.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
        except (ValueError, AttributeError):
            _LOGGER.debug("Failed to parse date string: %s", date_str)
            return None

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

class MijnTedTotalUsageSensor(MijnTedSensor):
    """Sensor for total device readings from all devices."""
    
    def __init__(self, coordinator):
        """Initialize the total usage sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "filter", "total usage")
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_suggested_display_precision = 0

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor.
        
        Returns:
            Sum of all device readings, or None if no valid data
        """
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
        """Return the unit of measurement.
        
        Returns:
            Unit string constant
        """
        return UNIT_MIJNTED
    
    def _calculate_last_year_total(self) -> Optional[float]:
        """Calculate total usage from last year's monthly data.
        
        Returns:
            Total usage for last year, or None if no valid data
        """
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
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing device list and last year usage
        """
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
        """Initialize the active model sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "active_model", "active model")
        self._attr_icon = "mdi:tag"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor.
        
        Returns:
            Active model string, or None if not available
        """
        return self.coordinator.data.get("active_model")

class MijnTedDeliveryTypesSensor(MijnTedSensor):
    """Sensor for delivery types."""
    
    def __init__(self, coordinator):
        """Initialize the delivery types sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "delivery_types", "delivery type")
        self._attr_icon = "mdi:package-variant"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor.
        
        Returns:
            Comma-separated list of delivery types, or None if empty
        """
        delivery_types = self.coordinator.data.get("delivery_types", [])
        if not delivery_types:
            return None
        # Convert to strings in case they're integers
        return ", ".join(str(dt) for dt in delivery_types)

class MijnTedResidentialUnitDetailSensor(MijnTedSensor):
    """Sensor for residential unit details."""
    
    def __init__(self, coordinator):
        """Initialize the residential unit detail sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "residential_unit_detail", "residential unit")
        self._attr_icon = "mdi:home"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor.
        
        Returns:
            Residential unit identifier, or None if not available
        """
        return self.coordinator.data.get("residential_unit")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing all residential unit detail data
        """
        return self.coordinator.data.get("residential_unit_detail", {})

class MijnTedUnitOfMeasuresSensor(MijnTedSensor):
    """Sensor for unit of measures information."""
    
    def __init__(self, coordinator):
        """Initialize the unit of measures sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "unit_of_measures", "unit of measures")
        self._attr_icon = "mdi:ruler"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor.
        
        Returns:
            Display name of first unit of measure, or None if not available
        """
        unit_of_measures = self.coordinator.data.get("unit_of_measures", [])
        if isinstance(unit_of_measures, list) and len(unit_of_measures) > 0:
            # Get the first item's displayName
            first_item = unit_of_measures[0]
            if isinstance(first_item, dict):
                return first_item.get("displayName")
        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing unit of measures list
        """
        unit_of_measures = self.coordinator.data.get("unit_of_measures", [])
        if isinstance(unit_of_measures, list):
            return {"unit_of_measures": unit_of_measures}
        return {}

class MijnTedThisYearUsageSensor(MijnTedSensor):
    """Sensor for this year's total usage with month breakdown."""
    
    def __init__(self, coordinator):
        """Initialize the this year usage sensor."""
        super().__init__(coordinator, "this_year_usage", "this year usage")
        self._attr_icon = "mdi:chart-line"
        self._attr_suggested_display_precision = 0
    
    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor from usageInsight."""
        usage_insight = self.coordinator.data.get("usage_insight", {})
        if isinstance(usage_insight, dict):
            usage = usage_insight.get("usage")
            if usage is not None:
                try:
                    return float(usage)
                except (ValueError, TypeError):
                    pass
        return None
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL
    
    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant
        """
        return UNIT_MIJNTED
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes from usageInsight and residentialUnitUsage.
        
        Returns:
            Dictionary containing usage insight data and monthly breakdown
        """
        attributes: Dict[str, Any] = {}
        
        # Add all properties from usageInsight
        usage_insight = self.coordinator.data.get("usage_insight", {})
        attributes.update(_extract_usage_insight_attributes(usage_insight))
        
        # Add monthly breakdown from residentialUnitUsage
        usage_data = self.coordinator.data.get("usage_this_year", {})
        month_breakdown = _extract_monthly_breakdown(usage_data)
        if month_breakdown:
            attributes["monthly_breakdown"] = month_breakdown
        
        return attributes

class MijnTedLastYearUsageSensor(MijnTedSensor):
    """Sensor for last year's total usage with month breakdown."""
    
    def __init__(self, coordinator):
        """Initialize the last year usage sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "last_year_usage", "last year usage")
        self._attr_icon = "mdi:chart-line"
        self._attr_suggested_display_precision = 0
    
    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor from usageInsight.
        
        Returns:
            Total usage for last year, or None if not available
        """
        usage_insight = self.coordinator.data.get("usage_insight_last_year", {})
        if isinstance(usage_insight, dict):
            usage = usage_insight.get("usage")
            if usage is not None:
                try:
                    return float(usage)
                except (ValueError, TypeError):
                    pass
        return None
    
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
        """Return entity specific state attributes from usageInsight and residentialUnitUsage."""
        attributes: Dict[str, Any] = {}
        
        # Add all properties from usageInsight
        usage_insight = self.coordinator.data.get("usage_insight_last_year", {})
        attributes.update(_extract_usage_insight_attributes(usage_insight))
        
        # Add monthly breakdown from residentialUnitUsage
        usage_data = self.coordinator.data.get("usage_last_year", {})
        month_breakdown = _extract_monthly_breakdown(usage_data)
        if month_breakdown:
            attributes["monthly_breakdown"] = month_breakdown
        
        return attributes
