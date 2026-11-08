"""Installation-language labels loaded through Home Assistant's translation API."""

import asyncio
import logging
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Dict, Optional

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import async_add_external_statistics, get_metadata
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ROOM_KEYS = {"KA": "room_bedroom", "W": "room_living_room"}
STATISTIC_TRANSLATION_KEYS = {
    "monthly_usage": "published_usage",
    "last_year_monthly_usage": "last_year_monthly_usage",
    "average_monthly_usage": "average_monthly_usage",
    "last_year_average_monthly_usage": "last_year_average_monthly_usage",
    "reported_daily_usage": "reported_daily_usage",
}


@dataclass(frozen=True)
class MijnTedTranslations:
    """One setup's server-language resources, including HA's English fallback."""

    entity: Dict[str, str]
    common: Dict[str, str]

    def sensor_name(self, translation_key: str) -> str:
        """Resolve an entity-local label, also used for related external series."""
        return self.entity[f"component.{DOMAIN}.entity.sensor.{translation_key}.name"]

    def common_label(self, key: str) -> str:
        """Resolve a shared label from the supported common section."""
        return self.common[f"component.{DOMAIN}.common.{key}"]

    def room_label(self, room: str) -> str:
        """Translate only known codes; retain arbitrary codes and names verbatim."""
        key = ROOM_KEYS.get(room)
        return self.common_label(key) if key else room

    def statistic_name(self, series_key: str) -> str:
        """Name a reporting series independently of the entity exporting it."""
        key = STATISTIC_TRANSLATION_KEYS[series_key]
        if series_key == "reported_daily_usage":
            return self.common_label(key)
        return self.sensor_name(key)


async def async_load_translations(hass: HomeAssistant) -> MijnTedTranslations:
    """Load the server language once per setup; HA owns locale fallback and caching."""
    entity, common = await asyncio.gather(
        async_get_translations(hass, hass.config.language, "entity", {DOMAIN}),
        async_get_translations(hass, hass.config.language, "common", {DOMAIN}),
    )
    return MijnTedTranslations(entity, common)


async def async_refresh_statistic_names(
    hass: HomeAssistant, entry_id: str, translations: MijnTedTranslations,
) -> None:
    """Rename existing external metadata without importing or changing any samples.

    Recorder's external import API updates metadata even for an empty sample
    list. Read existing metadata first so absent series are not created and all
    non-name fields, including units and mean/sum semantics, are retained.
    """
    if "recorder" not in hass.config.components:
        return
    series_ids = {
        f"{DOMAIN}:{entry_id.lower()}_{key}": key
        for key in STATISTIC_TRANSLATION_KEYS
    }
    metadata = await get_instance(hass).async_add_executor_job(
        partial(get_metadata, hass, statistic_ids=set(series_ids)),
    )
    for statistic_id, (_, existing) in metadata.items():
        if existing["source"] != DOMAIN:
            continue
        name = translations.statistic_name(series_ids[statistic_id])
        if existing["name"] != name:
            async_add_external_statistics(hass, {**existing, "name": name}, [])


async def async_setup_statistic_names(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: DataUpdateCoordinator[Dict[str, Any]],
) -> None:
    """Refresh cosmetic metadata without making sensor availability depend on recorder."""
    async def refresh() -> bool:
        """Leave failures pending for a later successful coordinator update."""
        try:
            await async_refresh_statistic_names(hass, entry.entry_id, coordinator.mijnted_translations)
        except Exception as err:
            _LOGGER.warning(
                "Could not refresh statistic names for %s: %s; retrying after a successful update",
                entry.entry_id, err,
            )
            return False
        return True

    if await refresh():
        return

    remove_listener: Optional[Callable[[], None]] = None
    task: Optional[asyncio.Task[None]] = None

    def stop_listening() -> None:
        """Remove the retry listener once, on success or unload."""
        nonlocal remove_listener
        if remove_listener is not None:
            remove_listener()
            remove_listener = None

    async def retry() -> None:
        """Retry asynchronously so coordinator updates can still deliver sensor states."""
        if await refresh():
            stop_listening()

    def on_update() -> None:
        """Allow at most one metadata refresh in flight after a successful update."""
        nonlocal task
        if remove_listener is not None and coordinator.last_update_success and (task is None or task.done()):
            task = hass.async_create_task(retry())

    def unload() -> None:
        """Cancel pending work and unsubscribe before an entry can be reloaded."""
        stop_listening()
        if task is not None and not task.done():
            task.cancel()

    remove_listener = coordinator.async_add_listener(on_update)
    entry.async_on_unload(unload)
