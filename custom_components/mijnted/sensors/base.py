from typing import Any, Dict, Optional
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity import DeviceInfo
from ..const import DOMAIN


class MijnTedSensor(CoordinatorEntity, SensorEntity):
    """Base class for Mijnted sensors."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]], sensor_type: str, name: str) -> None:
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
        # Store last known value for when sensor becomes unavailable
        self._last_known_value = None
        self._last_known_state = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information.
        
        Returns:
            DeviceInfo object with device identifiers and details
        """
        data = self.coordinator.data
        if not data:
            return DeviceInfo(
                identifiers={(DOMAIN, "unknown")},
                name="MijnTed",
                manufacturer="MijnTed",
                model="Unknown",
            )
        
        residential_unit = data.get("residential_unit", "unknown")
        
        residential_unit_detail = data.get("residential_unit_detail", {})
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
            model=data.get("active_model", "Unknown"),
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor.
        
        Returns:
            Formatted sensor name with "MijnTed" prefix
        """
        return f"MijnTed {self._name}"
    
    @property
    def available(self) -> bool:
        """Return True if sensor has fresh data from coordinator.
        
        Returns:
            True if coordinator last update was successful, False otherwise
        """
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
        )
    
    def _get_last_successful_sync(self) -> Optional[str]:
        data = self.coordinator.data
        if not data:
            return None
        return data.get("last_successful_sync")
    
    def _update_last_known_value(self, value: Any) -> None:
        if value is not None:
            self._last_known_value = value
            self._last_known_state = value

