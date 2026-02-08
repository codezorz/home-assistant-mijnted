from typing import List

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
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
    
    buttons: List[ButtonEntity] = [
        MijnTedResetStatisticsButton(coordinator, hass=hass, entry_id=entry.entry_id)
    ]
    
    async_add_entities(buttons, True)
