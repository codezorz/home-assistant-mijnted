"""Diagnostic sensors for MijnTed integration."""
from typing import Any, Dict, Optional
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .base import MijnTedSensor
from ..utils import TimestampUtil, ListUtil


class MijnTedLastUpdateSensor(MijnTedSensor):
    """Sensor for last update timestamp."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the last update sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "last_update", "last update")
        self._attr_icon = "mdi:clock-outline"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        data = self.coordinator.data
        if not data:
            return None
        
        last_update = data.get('last_update')
        if isinstance(last_update, dict):
            date_str = last_update.get("lastSyncDate") or last_update.get("date")
        else:
            date_str = str(last_update) if last_update else None
        
        if date_str:
            return TimestampUtil.parse_date_to_timestamp(date_str)
        return None


class MijnTedActiveModelSensor(MijnTedSensor):
    """Sensor for active model information."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
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
        data = self.coordinator.data
        if not data:
            return None
        return data.get("active_model")


class MijnTedDeliveryTypesSensor(MijnTedSensor):
    """Sensor for delivery types."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
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
        data = self.coordinator.data
        if not data:
            return None
        
        delivery_types = data.get("delivery_types", [])
        if not delivery_types:
            return None
        # Convert to strings in case they're integers
        return ", ".join(str(dt) for dt in delivery_types)


class MijnTedResidentialUnitDetailSensor(MijnTedSensor):
    """Sensor for residential unit details."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
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
        data = self.coordinator.data
        if not data:
            return None
        return data.get("residential_unit")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing all residential unit detail data
        """
        data = self.coordinator.data
        if not data:
            return {}
        return data.get("residential_unit_detail", {})


class MijnTedUnitOfMeasuresSensor(MijnTedSensor):
    """Sensor for unit of measures information."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
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
        data = self.coordinator.data
        if not data:
            return None
        
        unit_of_measures = data.get("unit_of_measures", [])
        first_item = ListUtil.get_first_item(unit_of_measures)
        if first_item is not None:
            # Get the first item's displayName
            if isinstance(first_item, dict):
                return first_item.get("displayName")
        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing unit of measures list
        """
        data = self.coordinator.data
        if not data:
            return {}
        
        unit_of_measures = data.get("unit_of_measures", [])
        if isinstance(unit_of_measures, list):
            return {"unit_of_measures": unit_of_measures}
        return {}


class MijnTedLastSuccessfulSyncSensor(MijnTedSensor):
    """Sensor for the timestamp of the last successful data sync."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the last successful sync sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "last_successful_sync", "last successful sync")
        self._attr_icon = "mdi:clock-check"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
    
    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor.
        
        Returns:
            ISO timestamp string of last successful sync, or None if not available
        """
        return self._get_last_successful_sync()

