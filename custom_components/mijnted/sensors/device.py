from typing import Any, Dict, Optional
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .base import MijnTedSensor
from ..const import DOMAIN, UNIT_MIJNTED
from ..utils import TranslationUtil


class MijnTedDeviceSensor(MijnTedSensor):
    """Sensor for Mijnted devices."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]], device_number: str) -> None:
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

    @property
    def _device_data(self) -> Optional[Dict[str, Any]]:
        data = self.coordinator.data
        if not data:
            return None
        
        filter_status = data.get("filter_status", [])
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
            room = device_data.get("room", "").lower().replace(" ", "_")
            room = "".join(c if c.isalnum() or c == "_" else "_" for c in room)
            return f"{DOMAIN}_device_{room}_{self.device_number}"
        return f"{DOMAIN}_device_{self.device_number}"

    @property
    def name(self) -> str:
        """Return the name of the sensor.
        
        Returns:
            Formatted sensor name with room name if available, otherwise device number
        """
        device_data = self._device_data
        if device_data and device_data.get("room"):
            room_code = device_data['room']
            hass = getattr(self.coordinator, 'hass', None)
            room_name = TranslationUtil.translate_room_code(room_code, hass)
            return f"MijnTed device {room_name}"
        return f"MijnTed device {self.device_number}"

    @property
    def state(self) -> Any:
        """Return the state of the sensor.
        
        Returns:
            Current reading value from device data, or last known value if unavailable
        """
        device_data = self._device_data
        if device_data:
            value = device_data.get("currentReadingValue")
            if value is not None:
                self._update_last_known_value(value)
                return value
        
        return self._last_known_value

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit of measurement string from device data, or empty string if not available
        """
        device_data = self._device_data
        if device_data:
            unit = device_data.get("unitOfMeasure", "")
            if unit in ("Einheiten", "Eenheden"):
                return UNIT_MIJNTED
            return unit if unit else ""
        return ""

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing room, device_id, measurement_device_id
        """
        attributes: Dict[str, Any] = {}
        
        device_data = self._device_data
        if device_data:
            attributes.update({
                "room": device_data.get("room"),
                "device_id": device_data.get("deviceId"),
                "measurement_device_id": device_data.get("measurementDeviceId")
            })
        
        return attributes

