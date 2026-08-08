from typing import Any, Dict, Optional
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.storage import Store
from ..const import DOMAIN
from .base import MijnTedSensor, unit_slug
from .models import StatisticsTracking

_LOGGER = logging.getLogger(__name__)

_STORAGE_VERSION = 1
_STORAGE_KEY = f"{DOMAIN}_monthly_cache"


class MijnTedResetStatisticsButton(CoordinatorEntity, ButtonEntity):
    """Button entity to reset statistics tracking and trigger re-injection.

    Clears persisted storage, resets all statistics tracking fields, and triggers
    a complete refresh from the MijnTed API on press.

    Args:
        coordinator: DataUpdateCoordinator providing MijnTed API data.
        hass: Home Assistant instance (optional; will try to get from coordinator).
        entry_id: Config entry ID (optional; will try to find from coordinator).
    """
    
    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Dict[str, Any]],
        hass: Optional[HomeAssistant] = None,
        entry_id: Optional[str] = None,
        cache_id: Optional[str] = None,
    ) -> None:
        """Initialize the reset statistics button.

        Args:
            coordinator: Data update coordinator
            hass: Home Assistant instance (optional, will try to get from coordinator)
            entry_id: Config entry ID (optional, will try to find from coordinator)
            cache_id: Per-meter persistent-storage id to clear on press
        """
        super().__init__(coordinator)
        data = coordinator.data or {}
        delivery_type = data.get("delivery_type")
        label = data.get("delivery_label")
        if delivery_type is None:
            self._attr_unique_id = f"{DOMAIN}_reset_statistics"
        else:
            unit_part = unit_slug(data.get("meter_unit"))
            self._attr_unique_id = f"{DOMAIN}_{delivery_type}_{unit_part}_reset_statistics"
        prefix = f"MijnTed {label} " if label else "MijnTed "
        self._attr_name = f"{prefix}reset statistics"
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.CONFIG
        self._hass = hass
        self._entry_id = entry_id
        self._cache_id = cache_id or entry_id

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
        if not hass and hasattr(self, 'hass'):
            hass = self.hass

        cache_id = self._cache_id
        if hass and cache_id:
            try:
                store = Store(hass, _STORAGE_VERSION, f"{_STORAGE_KEY}_{cache_id}")
                await store.async_save({"monthly_history_cache": {}})
                _LOGGER.info("Cleared persisted cache storage for %s", cache_id)
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
