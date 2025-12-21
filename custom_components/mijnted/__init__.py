from datetime import timedelta, datetime
from typing import Any, Dict, Optional
import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import MijntedApi, MijntedApiError, MijntedAuthenticationError, MijntedConnectionError
from .const import DOMAIN, DEFAULT_POLLING_INTERVAL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MijnTed from a config entry."""
    
    async def token_update_callback(refresh_token: str, access_token: Optional[str], residential_unit: Optional[str]) -> None:
        """Callback to persist updated tokens to config entry."""
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                "refresh_token": refresh_token,
                "access_token": access_token,
                "residential_unit": residential_unit
            }
        )
        _LOGGER.debug("Updated tokens in config entry")
    
    async def async_update_data() -> Dict[str, Any]:
        """Fetch data from the API and structure it for sensors."""
        # Create a new API instance for each update to ensure fresh session
        api = MijntedApi(
            client_id=entry.data["client_id"],
            refresh_token=entry.data["refresh_token"],
            access_token=entry.data.get("access_token"),
            residential_unit=entry.data.get("residential_unit"),
            token_update_callback=token_update_callback
        )
        
        try:
            async with api:
                await api.authenticate()
                
                # Update stored tokens if they were refreshed (fallback check in case callback didn't fire)
                if api.refresh_token != entry.data.get("refresh_token") or api.access_token != entry.data.get("access_token"):
                    hass.config_entries.async_update_entry(
                        entry,
                        data={
                            **entry.data,
                            "refresh_token": api.refresh_token,
                            "access_token": api.access_token,
                            "residential_unit": api.residential_unit
                        }
                    )
                
                # Fetch all data in parallel where possible for better performance
                # Group independent calls together
                last_year = datetime.now().year - 1
                
                # First batch: Independent calls that can run in parallel
                (
                    energy_usage_data,
                    last_update_data,
                    filter_status_data,
                    usage_insight_data,
                    usage_insight_last_year_data,
                    active_model_data,
                    residential_unit_detail_data,
                    usage_last_year_data,
                    usage_per_room_data,
                    unit_of_measures_data,
                ) = await asyncio.gather(
                    api.get_energy_usage(),
                    api.get_last_data_update(),
                    api.get_filter_status(),
                    api.get_usage_insight(),
                    api.get_usage_insight(last_year),
                    api.get_active_model(),
                    api.get_residential_unit_detail(),
                    api.get_usage_last_year(),
                    api.get_usage_per_room(),
                    api.get_unit_of_measures(),
                    return_exceptions=True,
                )
                
                # Get all delivery types (already fetched during authenticate)
                delivery_types = await api.get_delivery_types()
                
                # Handle exceptions from parallel calls
                exception_map = {
                    "energy_usage": energy_usage_data,
                    "last_update": last_update_data,
                    "filter_status": filter_status_data,
                    "usage_insight": usage_insight_data,
                    "usage_insight_last_year": usage_insight_last_year_data,
                    "active_model": active_model_data,
                    "residential_unit_detail": residential_unit_detail_data,
                    "usage_last_year": usage_last_year_data,
                    "usage_per_room": usage_per_room_data,
                    "unit_of_measures": unit_of_measures_data,
                }
                
                for name, result in exception_map.items():
                    if isinstance(result, Exception):
                        _LOGGER.warning("Failed to fetch %s: %s", name, result)
                        # Set to default empty value based on expected type
                        if name in ("filter_status", "unit_of_measures"):
                            exception_map[name] = []
                        else:
                            exception_map[name] = {}
                
                # Update variables with potentially corrected values
                energy_usage_data = exception_map["energy_usage"]
                last_update_data = exception_map["last_update"]
                filter_status_data = exception_map["filter_status"]
                usage_insight_data = exception_map["usage_insight"]
                usage_insight_last_year_data = exception_map["usage_insight_last_year"]
                active_model_data = exception_map["active_model"]
                residential_unit_detail_data = exception_map["residential_unit_detail"]
                usage_last_year_data = exception_map["usage_last_year"]
                usage_per_room_data = exception_map["usage_per_room"]
                unit_of_measures_data = exception_map["unit_of_measures"]
                
                # Parse and structure the data for sensors
                # Energy usage: API returns {"monthlyEnergyUsages": [...], "averageEnergyUseForBillingUnit": 0}
                # Calculate total from monthly data
                energy_usage_total = 0.0
                if isinstance(energy_usage_data, dict):
                    monthly_usages = energy_usage_data.get("monthlyEnergyUsages", [])
                    if monthly_usages:
                        energy_usage_total = sum(
                            float(month.get("totalEnergyUsage", 0))
                            for month in monthly_usages
                            if isinstance(month, dict)
                        )
                
                # Last update: API returns plain text "18/12/2025" wrapped in {"value": "..."}
                if isinstance(last_update_data, dict):
                    last_update = last_update_data.get("value", "")
                else:
                    last_update = str(last_update_data) if last_update_data else ""
                
                # Filter status: API returns array of device objects
                # Keep the array as-is for processing
                filter_status = filter_status_data if isinstance(filter_status_data, list) else []
                
                # Active model: API returns plain text "F71" wrapped in {"value": "..."}
                if isinstance(active_model_data, dict):
                    active_model = active_model_data.get("value", "")
                else:
                    active_model = str(active_model_data) if active_model_data else None
                
                # Extract usage data
                # energy_usage_data is for current year
                usage_this_year = energy_usage_data if isinstance(energy_usage_data, dict) else {}
                usage_last_year = usage_last_year_data if isinstance(usage_last_year_data, dict) else {}
                
                # Extract room usage - structure as dict with room names as keys
                # API returns: {"rooms": ["KA", "KA", "W", "W"], "currentYear": {"values": [129.0, 0.0, 0.0, 633.0]}, ...}
                room_usage = {}
                if isinstance(usage_per_room_data, dict):
                    rooms = usage_per_room_data.get("rooms", [])
                    current_year_data = usage_per_room_data.get("currentYear", {})
                    values = current_year_data.get("values", [])
                    
                    # Combine values for rooms with the same name
                    for i, room_name in enumerate(rooms):
                        if i < len(values):
                            value = values[i]
                            if room_name in room_usage:
                                # Room already exists, add the value (or take max, depending on what makes sense)
                                # For now, we'll sum them if there are duplicates
                                if isinstance(room_usage[room_name], (int, float)):
                                    room_usage[room_name] = float(room_usage[room_name]) + float(value)
                                else:
                                    room_usage[room_name] = float(value)
                            else:
                                room_usage[room_name] = float(value)
                elif isinstance(usage_per_room_data, list):
                    # Fallback: if it's a list, convert to dict
                    for i, item in enumerate(usage_per_room_data):
                        if isinstance(item, dict):
                            room_name = item.get("room") or item.get("roomName") or item.get("name") or item.get("id")
                            if room_name:
                                room_usage[room_name] = item
                            else:
                                room_usage[f"room_{i}"] = item
                        else:
                            room_usage[f"room_{i}"] = item
                
                return {
                    "energy_usage": energy_usage_total,
                    "energy_usage_data": energy_usage_data,  # Keep full data for sensors that need it
                    "last_update": last_update,
                    "filter_status": filter_status,
                    "usage_insight": usage_insight_data,
                    "usage_insight_last_year": usage_insight_last_year_data,
                    "active_model": active_model,
                    "delivery_types": delivery_types,
                    "residential_unit": api.residential_unit,
                    "residential_unit_detail": residential_unit_detail_data,
                    "usage_this_year": usage_this_year,
                    "usage_last_year": usage_last_year,
                    "room_usage": room_usage,
                    "unit_of_measures": unit_of_measures_data,
                }
        except MijntedAuthenticationError as err:
            _LOGGER.error("Authentication error: %s", err)
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except MijntedConnectionError as err:
            _LOGGER.error("Connection error: %s", err)
            raise UpdateFailed(f"Connection failed: {err}") from err
        except MijntedApiError as err:
            _LOGGER.error("API error: %s", err)
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error communicating with API: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err

    polling_interval_seconds = entry.data.get("polling_interval", DEFAULT_POLLING_INTERVAL.total_seconds())
    update_interval = timedelta(seconds=int(polling_interval_seconds))
    
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=update_interval,
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

