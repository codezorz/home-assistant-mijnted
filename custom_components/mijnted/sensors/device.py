from typing import Any, Dict, Optional
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .base import MijnTedSensor, device_class_for, display_precision_for, is_superseded_meter, radiographic_rooms, unit_slug
from ..const import DOMAIN, UNIT_MIJNTED
from ..utils import TranslationUtil


class MijnTedDeviceSensor(MijnTedSensor):
    """Sensor for individual MijnTed device readings.

    Displays the current meter reading for a specific device from filter_status.

    Args:
        coordinator: DataUpdateCoordinator providing MijnTed API data.
        device_number: Zero-based index or identifier of the device in the filter_status list.
    """
    
    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Dict[str, Any]],
        device_number: str,
        delivery_type: Any = None,
        unit: Optional[str] = None,
        label: Optional[str] = None,
    ) -> None:
        """Initialize the device sensor.

        Args:
            coordinator: Data update coordinator
            device_number: Device number identifier
            delivery_type: Delivery type id this meter belongs to
            unit: Selected unit value for this meter
            label: Friendly delivery-type label
        """
        super().__init__(
            coordinator,
            f"device_{device_number}",
            f"device {device_number}",
            delivery_type=delivery_type,
            unit=unit,
            label=label,
        )
        self.device_number = device_number
        self._attr_suggested_display_precision = display_precision_for(self.meter_unit)

    @property
    def icon(self) -> str:
        """Return an icon matching the meter type (water vs. heating)."""
        if device_class_for(getattr(self, "meter_unit", None)) is not None:
            return "mdi:water"
        return "mdi:radiator"

    @property
    def _device_data(self) -> Optional[Dict[str, Any]]:
        """Device data for this sensor from coordinator filter_status."""
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
        prefix = f"{DOMAIN}"
        if self.delivery_type is not None:
            prefix = f"{DOMAIN}_{self.delivery_type}_{unit_slug(self.meter_unit)}"
        if device_data and device_data.get("room"):
            room = device_data.get("room", "").lower().replace(" ", "_")
            room = "".join(c if c.isalnum() or c == "_" else "_" for c in room)
            return f"{prefix}_device_{room}_{self.device_number}"
        return f"{prefix}_device_{self.device_number}"

    @property
    def name(self) -> str:
        """Return the name of the sensor.
        
        Returns:
            Formatted sensor name with room name if available, otherwise device number
        """
        device_data = self._device_data
        label_prefix = f"MijnTed {self.meter_label} " if self.meter_label else "MijnTed "
        if device_data and device_data.get("room"):
            room_code = device_data['room']
            hass = getattr(self.coordinator, 'hass', None)
            room_name = TranslationUtil.translate_room_code(room_code, hass)
            # Disambiguate when a room contains more than one meter so they don't
            # share an identical display name.
            if self._room_meter_count(room_code) > 1:
                return f"{label_prefix}device {room_name} {self.device_number}"
            return f"{label_prefix}device {room_name}"
        return f"{label_prefix}device {self.device_number}"

    def _room_meter_count(self, room_code: Any) -> int:
        """Count visible (non-superseded) meters that share the given room code."""
        data = self.coordinator.data
        if not data:
            return 0
        filter_status = data.get("filter_status", [])
        if not isinstance(filter_status, list):
            return 0
        radio_rooms = radiographic_rooms(filter_status)
        return sum(
            1 for device in filter_status
            if isinstance(device, dict)
            and device.get("room") == room_code
            and not is_superseded_meter(device, radio_rooms)
        )

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

