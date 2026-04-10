from typing import List

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_NAME, DEFAULT_NAME, DOMAIN
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
    
    buttons: List[ButtonEntity] = [
        MijnTedResetStatisticsButton(coordinator, hass=hass, entry_id=entry.entry_id, config_name=config_name)
    ]
    
    async_add_entities(buttons, True)
