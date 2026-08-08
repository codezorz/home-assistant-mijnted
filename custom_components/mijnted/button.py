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
    store = hass.data[DOMAIN][entry.entry_id]
    coordinators = store["coordinators"]
    meters = store["meters"]

    buttons: List[ButtonEntity] = []
    for meter in meters:
        coordinator = coordinators.get(meter.key)
        if coordinator is None:
            continue
        buttons.append(
            MijnTedResetStatisticsButton(
                coordinator,
                hass=hass,
                entry_id=entry.entry_id,
                cache_id=meter.cache_id(entry.entry_id),
            )
        )

    async_add_entities(buttons, True)
