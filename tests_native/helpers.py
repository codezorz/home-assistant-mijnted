"""Shared native recorder queries and entry-owned entity lookups."""

from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.helpers import entity_registry
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util
from pytest_homeassistant.components.recorder.common import async_wait_recording_done

DOMAIN = "mijnted"
ENTRY_ID = "native_usage_reporting"


async def settled(hass):
    """Flush production platform tasks and the recorder's actual database queue."""
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)


async def query(hass, identifiers, start, end, period="month", types=None):
    """Query actual recorder imports with HA's reducer and metadata rules."""
    return await get_instance(hass).async_add_executor_job(
        statistics_during_period, hass, dt_util.as_utc(start), dt_util.as_utc(end),
        set(identifiers), period, None, types or {"mean"},
    )


def own_id(entry=ENTRY_ID):
    """Identify the entry-owned monthly report statistic."""
    return f"{DOMAIN}:{entry}_monthly_usage"


async def refresh(hass, runtime):
    """Run the production update method and wait for recording completion."""
    await hass.data[DOMAIN][runtime.entry_id].async_refresh()
    await settled(hass)


def reporting_entities(hass, entry):
    """Find entry-owned sensors independently of HA's entity-ID naming settings."""
    registry = entity_registry.async_get(hass)
    prefix = f"{DOMAIN}_{entry.entry_id}_"
    return {row.unique_id.removeprefix(prefix): row for row in
            entity_registry.async_entries_for_config_entry(registry, entry.entry_id)
            if row.domain == "sensor"}
