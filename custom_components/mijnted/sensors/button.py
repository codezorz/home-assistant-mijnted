from typing import Any, Dict, Optional
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.storage import Store
from ..const import DOMAIN
from .base import MijnTedSensor
from .models import StatisticsTracking

_LOGGER = logging.getLogger(__name__)

_STORAGE_VERSION = 1
_STORAGE_KEY = f"{DOMAIN}_monthly_cache"


class MijnTedResetStatisticsButton(CoordinatorEntity, ButtonEntity):
    """Button entity to reset statistics tracking and trigger re-injection."""
    
    def __init__(
        self, 
        coordinator: DataUpdateCoordinator[Dict[str, Any]],
        hass: Optional[HomeAssistant] = None,
        entry_id: Optional[str] = None
    ) -> None:
        """Initialize the reset statistics button.
        
        Args:
            coordinator: Data update coordinator
            hass: Home Assistant instance (optional, will try to get from coordinator)
            entry_id: Config entry ID (optional, will try to find from coordinator)
        """
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_reset_statistics"
        self._attr_name = "MijnTed reset statistics"
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.CONFIG
        self._hass = hass
        self._entry_id = entry_id
    
    @property
    def device_info(self):
        """Return device information.
        
        Returns:
            DeviceInfo object with device identifiers and details
        """
        return MijnTedSensor._build_device_info(self.coordinator.data)
    
    async def async_press(self) -> None:
        """Handle the button press - reset statistics tracking and clear persisted storage.
        
        Clears persisted storage, resets all statistics tracking fields to None,
        clears in-memory cache, and triggers a complete refresh from the API.
        """
        data = self.coordinator.data
        if not data:
            _LOGGER.warning("Cannot reset statistics: coordinator data not available")
            return
        
        hass = self._hass
        entry_id = self._entry_id
        
        if not hass and hasattr(self, 'hass'):
            hass = self.hass
        
        if not entry_id and hass:
            for entry_id_candidate, coordinator_candidate in hass.data.get(DOMAIN, {}).items():
                if coordinator_candidate is self.coordinator:
                    entry_id = entry_id_candidate
                    break
        
        if hass and entry_id:
            try:
                store = Store(hass, _STORAGE_VERSION, f"{_STORAGE_KEY}_{entry_id}")
                await store.async_save({"monthly_history_cache": {}})
                _LOGGER.info("Cleared persisted cache storage")
            except Exception as err:
                _LOGGER.warning("Failed to clear persisted cache: %s", err)
        
        data["monthly_history_cache"] = {}
        
        statistics_tracking = StatisticsTracking(
            monthly_usage=None,
            last_year_monthly_usage=None,
            average_monthly_usage=None,
            last_year_average_monthly_usage=None,
            total_usage=None
        )
        
        data["statistics_tracking"] = statistics_tracking
        
        _LOGGER.info("Statistics tracking and cache reset. Everything will be refreshed from API on next update.")
        
        await self.coordinator.async_request_refresh()
