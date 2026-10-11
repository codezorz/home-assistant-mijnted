from typing import Any, Dict, List, Optional

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .base import MijnTedSensor
from ..const import DEFAULT_NAME, UNIT_WATER
from ..utils import DataUtil, TranslationUtil

WATER_KIND_WARM = "warm"
WATER_KIND_COLD = "cold"

# Model prefixes returned by the activeModel endpoint (e.g. "WWZF-AP", "KWZF-AP").
_MODEL_PREFIX_KINDS = {"WWZF": WATER_KIND_WARM, "KWZF": WATER_KIND_COLD}
# Fallback when the model is unknown; observed delivery type IDs for water.
_DELIVERY_TYPE_KINDS = {"2": WATER_KIND_WARM, "3": WATER_KIND_COLD}


def _delivery_data(data: Optional[Dict[str, Any]], delivery_type: str) -> Dict[str, Any]:
    """Return the extra delivery-type payload for a delivery type, or an empty dict."""
    if not data:
        return {}
    extra = data.get("extra_delivery_data")
    if not isinstance(extra, dict):
        return {}
    delivery = extra.get(str(delivery_type))
    return delivery if isinstance(delivery, dict) else {}


def _delivery_devices(delivery: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return device status dicts of a delivery-type payload."""
    devices = delivery.get("filter_status")
    if not isinstance(devices, list):
        return []
    return [device for device in devices if isinstance(device, dict)]


def get_water_kind(delivery_type: str, active_model: Any) -> Optional[str]:
    """Classify a water delivery type as warm or cold, or None when unknown.

    The active model wins over the delivery type ID because the ID mapping is
    only observed behavior, not documented by the API.
    """
    model = str(active_model or "").upper()
    for prefix, kind in _MODEL_PREFIX_KINDS.items():
        if model.startswith(prefix):
            return kind
    return _DELIVERY_TYPE_KINDS.get(str(delivery_type))


def is_water_delivery(delivery: Dict[str, Any]) -> bool:
    """Return True when a delivery-type payload reports its readings in m³."""
    for device in _delivery_devices(delivery):
        if device.get("unitOfMeasure") == UNIT_WATER:
            return True
    unit_of_measures = delivery.get("unit_of_measures")
    if isinstance(unit_of_measures, list):
        for unit in unit_of_measures:
            if isinstance(unit, dict) and UNIT_WATER in (unit.get("value"), unit.get("displayName")):
                return True
    return False


def get_water_deliveries(data: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Map each water delivery type ID to its unique device numbers.

    Args:
        data: Coordinator data containing ``extra_delivery_data``.

    Returns:
        Delivery type ID (string) -> device numbers (strings, in API order).
        Delivery types that are not measured in m³ are left out.
    """
    water: Dict[str, List[str]] = {}
    extra = data.get("extra_delivery_data") if data else None
    if not isinstance(extra, dict):
        return water
    for delivery_type, delivery in extra.items():
        if not isinstance(delivery, dict) or not is_water_delivery(delivery):
            continue
        device_numbers: List[str] = []
        for device in _delivery_devices(delivery):
            device_number = device.get("deviceNumber")
            if device_number is not None and str(device_number) not in device_numbers:
                device_numbers.append(str(device_number))
        water[str(delivery_type)] = device_numbers
    return water


def _water_label(kind: Optional[str]) -> str:
    """Return the display label for a water kind ("Warm water", "Cold water", "Water")."""
    return f"{kind.capitalize()} water" if kind else "Water"


class MijnTedWaterMeterSensor(MijnTedSensor):
    """Meter-reading sensor for one water device, usable in the Energy dashboard.

    Args:
        coordinator: DataUpdateCoordinator providing MijnTed API data.
        delivery_type: Delivery type ID the device belongs to.
        device_number: Device number of the water meter.
        entry_id: Config entry ID used to scope entity identity.
        config_name: User-configured device name.
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Dict[str, Any]],
        delivery_type: str,
        device_number: str,
        entry_id: str,
        config_name: str = DEFAULT_NAME,
    ) -> None:
        """Initialize the water meter sensor."""
        super().__init__(
            coordinator,
            f"water_{delivery_type}_device_{device_number}",
            f"water meter {device_number}",
            entry_id,
            config_name=config_name,
        )
        self.delivery_type = str(delivery_type)
        self.device_number = str(device_number)
        self._attr_icon = "mdi:water"
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UNIT_WATER

    @property
    def _delivery(self) -> Dict[str, Any]:
        """Extra delivery-type payload for this sensor's delivery type."""
        return _delivery_data(self.coordinator.data, self.delivery_type)

    @property
    def _device_data(self) -> Optional[Dict[str, Any]]:
        """Device status for this sensor, or None when the API no longer lists it."""
        for device in _delivery_devices(self._delivery):
            if str(device.get("deviceNumber", "")) == self.device_number:
                return device
        return None

    @property
    def name(self) -> str:
        """Return e.g. "Warm water meter Hallway", falling back to "Water meter <deviceNumber>"."""
        kind = get_water_kind(self.delivery_type, self._delivery.get("active_model"))
        device_data = self._device_data
        room = device_data.get("room") if device_data else None
        if room:
            hass = getattr(self.coordinator, "hass", None)
            suffix = TranslationUtil.translate_room_code(room, hass)
        else:
            suffix = self.device_number
        return f"{_water_label(kind)} meter {suffix}"

    @property
    def native_value(self) -> Optional[float]:
        """Return the meter reading, or the last known reading when it is missing.

        A reading <= 0 is treated as missing data: for a total_increasing
        sensor it would be recorded as a meter reset and, once the real
        reading returns, add the whole counter to the Energy statistics.
        """
        device_data = self._device_data
        if device_data:
            value = DataUtil.safe_float(device_data.get("currentReadingValue"))
            if value is not None and value > 0:
                self._update_last_known_value(value)
                return value
        return self._last_known_value

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return room, device_id, measurement_device_id and delivery_type."""
        attributes: Dict[str, Any] = {"delivery_type": self.delivery_type}
        device_data = self._device_data
        if device_data:
            attributes.update({
                "room": device_data.get("room"),
                "device_id": device_data.get("deviceId"),
                "measurement_device_id": device_data.get("measurementDeviceId"),
            })
        return attributes
