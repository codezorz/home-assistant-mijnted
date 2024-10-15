import requests
import json
import base64
from homeassistant import core
from datetime import datetime, timedelta
from .const import DOMAIN, LOGGER, BASE_PATH, AUTH_PATH
from .sensor import MijnTedSensor
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import MijntedApi

DEFAULT_POLLING_INTERVAL = timedelta(hours=1)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    api = MijntedApi(
        entry.data["username"],
        entry.data["password"],
        entry.data["client_id"]
    )

    async def async_update_data():
        try:
            await api.authenticate()
            energy_usage = await api.get_energy_usage()
            last_update = await api.get_last_data_update()
            filter_status = await api.get_filter_status()
            usage_insight = await api.get_usage_insight()
            return {
                "energy_usage": energy_usage,
                "last_update": last_update,
                "filter_status": filter_status,
                "usage_insight": usage_insight
            }
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        hass.logger,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=entry.data.get("polling_interval", DEFAULT_POLLING_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
