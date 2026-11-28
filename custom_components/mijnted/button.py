from typing import List

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_NAME, DEFAULT_NAME, DOMAIN
from .meters import meter_coordinators
from .sensors import MijnTedResetStatisticsButton


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up the Mijnted buttons.
    
    Args:
        hass: Home Assistant instance
        entry: Configuration entry
        async_add_entities: Callback to add entities
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    config_name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    
    added = set()
    primary_added = False

    def add_meter_buttons() -> None:
        """Register a reset button for each newly available reporting group."""
        nonlocal primary_added
        new_buttons: List[ButtonEntity] = []
        if not primary_added and not (coordinator.data or {}).get("primary_unresolved"):
            primary_added = True
            new_buttons.append(MijnTedResetStatisticsButton(
                coordinator, hass=hass, entry_id=entry.entry_id, config_name=config_name,
            ))
        for key, view in meter_coordinators(coordinator).items():
            if key not in added:
                added.add(key)
                new_buttons.append(MijnTedResetStatisticsButton(
                    view, hass=hass, entry_id=view.mijnted_meter.scope(entry.entry_id), config_name=config_name,
                ))
        if new_buttons:
            async_add_entities(new_buttons, False)

    add_meter_buttons()
    entry.async_on_unload(coordinator.async_add_listener(add_meter_buttons))
