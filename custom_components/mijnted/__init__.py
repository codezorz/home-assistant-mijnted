from datetime import timedelta, datetime, timezone, date
from typing import Any, Dict, Optional, Tuple, List
import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import MijntedApi
from .exceptions import MijntedApiError, MijntedAuthenticationError, MijntedGrantExpiredError, MijntedConnectionError
from .const import DOMAIN, DEFAULT_POLLING_INTERVAL, CACHE_HISTORY_MONTHS, DEFAULT_START_VALUE
from .utils import ApiUtil, DateUtil, TimestampUtil, DataUtil

_LOGGER = logging.getLogger(__name__)


def _extract_end_values_from_devices(devices_list: List[Dict[str, Any]]) -> Dict[str, float]:
    """Extract end values from devices list as a readings map.
    
    Args:
        devices_list: List of device dictionaries with 'id' and 'end' keys
        
    Returns:
        Dictionary mapping device ID strings to end values as floats
    """
    end_readings = {}
    for device in devices_list:
        if isinstance(device, dict):
            device_id = device.get("id")
            end_value = device.get("end")
            if device_id is not None and end_value is not None:
                try:
                    end_readings[str(device_id)] = float(end_value)
                except (ValueError, TypeError):
                    pass
    return end_readings


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MijnTed from a config entry."""
    
    async def token_update_callback(refresh_token: str, access_token: Optional[str], residential_unit: Optional[str], refresh_token_expires_at: Optional[datetime] = None) -> None:
        """Callback to persist updated tokens to config entry."""
        refresh_token_expires_at_str = None
        if refresh_token_expires_at:
            refresh_token_expires_at_str = refresh_token_expires_at.isoformat()
        
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                "refresh_token": refresh_token,
                "access_token": access_token,
                "residential_unit": residential_unit,
                "refresh_token_expires_at": refresh_token_expires_at_str
            }
        )
        _LOGGER.debug(
            "Updated tokens in config entry",
            extra={
                "entry_id": entry.entry_id,
                "has_residential_unit": bool(residential_unit),
                "refresh_token_expires_at": refresh_token_expires_at_str
            }
        )
    
    async def credentials_callback() -> Tuple[str, str]:
        """Callback to retrieve credentials from config entry for re-authentication."""
        username = entry.data.get("username")
        password = entry.data.get("password")
        if not username or not password:
            raise MijntedAuthenticationError("Username and password not found in config entry")
        return (username, password)
    
    async def async_update_data() -> Dict[str, Any]:
        """Fetch data from the API and structure it for sensors."""
        refresh_token_expires_at = None
        refresh_token_expires_at_str = entry.data.get("refresh_token_expires_at")
        if refresh_token_expires_at_str:
            try:
                refresh_token_expires_at = datetime.fromisoformat(refresh_token_expires_at_str.replace('Z', '+00:00'))
                if refresh_token_expires_at.tzinfo is None:
                    refresh_token_expires_at = refresh_token_expires_at.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError) as err:
                _LOGGER.warning(
                    "Could not parse refresh_token_expires_at from config: %s",
                    refresh_token_expires_at_str,
                    extra={"entry_id": entry.entry_id},
                    exc_info=True
                )
        
        api = MijntedApi(
            hass=hass,
            client_id=entry.data["client_id"],
            refresh_token=entry.data["refresh_token"],
            access_token=entry.data.get("access_token"),
            residential_unit=entry.data.get("residential_unit"),
            refresh_token_expires_at=refresh_token_expires_at,
            token_update_callback=token_update_callback,
            credentials_callback=credentials_callback
        )
        
        try:
            async with api:
                await api.authenticate()
                
                original_refresh_token = entry.data.get("refresh_token")
                original_access_token = entry.data.get("access_token")
                
                if (api.refresh_token != original_refresh_token or 
                    api.access_token != original_access_token or
                    api.residential_unit != entry.data.get("residential_unit")):
                    refresh_token_expires_at_str = None
                    if api.refresh_token_expires_at:
                        refresh_token_expires_at_str = api.refresh_token_expires_at.isoformat()
                    
                    hass.config_entries.async_update_entry(
                        entry,
                        data={
                            **entry.data,
                            "refresh_token": api.refresh_token,
                            "access_token": api.access_token,
                            "residential_unit": api.residential_unit,
                            "refresh_token_expires_at": refresh_token_expires_at_str
                        }
                    )
                
                last_year = DateUtil.get_last_year()
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
                
                delivery_types = await api.get_delivery_types()
                
                def handle_result(name: str, result: Any, default_empty: Any) -> Any:
                    """Handle result from gather, converting exceptions to defaults."""
                    if isinstance(result, Exception):
                        _LOGGER.warning(
                            "Failed to fetch %s: %s",
                            name,
                            result,
                            extra={"data_type": name, "residential_unit": api.residential_unit, "error_type": type(result).__name__}
                        )
                        return default_empty
                    return result
                
                energy_usage_data = handle_result("energy_usage", energy_usage_data, {})
                last_update_data = handle_result("last_update", last_update_data, {})
                filter_status_data = handle_result("filter_status", filter_status_data, [])
                usage_insight_data = handle_result("usage_insight", usage_insight_data, {})
                usage_insight_last_year_data = handle_result("usage_insight_last_year", usage_insight_last_year_data, {})
                active_model_data = handle_result("active_model", active_model_data, {})
                residential_unit_detail_data = handle_result("residential_unit_detail", residential_unit_detail_data, {})
                usage_last_year_data = handle_result("usage_last_year", usage_last_year_data, {})
                usage_per_room_data = handle_result("usage_per_room", usage_per_room_data, {})
                unit_of_measures_data = handle_result("unit_of_measures", unit_of_measures_data, [])
                
                energy_usage_total = 0.0
                if isinstance(energy_usage_data, dict):
                    monthly_usages = energy_usage_data.get("monthlyEnergyUsages", [])
                    if monthly_usages:
                        energy_usage_total = sum(
                            float(month.get("totalEnergyUsage", 0))
                            for month in monthly_usages
                            if isinstance(month, dict)
                        )
                
                last_update = ApiUtil.extract_value(last_update_data, "")
                filter_status = filter_status_data if isinstance(filter_status_data, list) else []
                active_model = ApiUtil.extract_value(active_model_data, None)
                
                usage_this_year = energy_usage_data if isinstance(energy_usage_data, dict) else {}
                usage_last_year = usage_last_year_data if isinstance(usage_last_year_data, dict) else {}
                
                room_usage = {}
                if isinstance(usage_per_room_data, dict):
                    rooms = usage_per_room_data.get("rooms", [])
                    current_year_data = usage_per_room_data.get("currentYear", {})
                    values = current_year_data.get("values", [])
                    
                    for i, room_name in enumerate(rooms):
                        if i < len(values):
                            value = values[i]
                            if room_name in room_usage:
                                if isinstance(room_usage[room_name], (int, float)):
                                    room_usage[room_name] = float(room_usage[room_name]) + float(value)
                                else:
                                    room_usage[room_name] = float(value)
                            else:
                                room_usage[room_name] = float(value)
                elif isinstance(usage_per_room_data, list):
                    for i, item in enumerate(usage_per_room_data):
                        if isinstance(item, dict):
                            room_name = item.get("room") or item.get("roomName") or item.get("name") or item.get("id")
                            if room_name:
                                room_usage[room_name] = item
                            else:
                                room_usage[f"room_{i}"] = item
                        else:
                            room_usage[f"room_{i}"] = item
                
                now = datetime.now(timezone.utc)
                last_successful_sync = TimestampUtil.format_datetime_to_timestamp(now)
                
                calculated_history: Dict[str, float] = {}
                current_month_calculated: Optional[float] = None
                
                try:
                    prev_month, prev_year = DateUtil.get_previous_month()
                    month_key = f"{prev_month}.{prev_year}"
                    
                    has_previous_month_in_analytics = False
                    if isinstance(energy_usage_data, dict):
                        monthly_usages = energy_usage_data.get("monthlyEnergyUsages", [])
                        for month in monthly_usages:
                            if isinstance(month, dict) and month.get("monthYear") == month_key:
                                has_previous_month_in_analytics = True
                                break
                    
                    if not has_previous_month_in_analytics:
                        try:
                            first_day = DateUtil.get_first_day_of_month(prev_month, prev_year)
                            last_day = DateUtil.get_last_day_of_month(prev_month, prev_year)
                            
                            start_anchor = await api.get_device_statuses_for_date(first_day)
                            end_anchor = await api.get_device_statuses_for_date(last_day)
                            
                            start_total = DataUtil.calculate_filter_status_total(start_anchor)
                            end_total = DataUtil.calculate_filter_status_total(end_anchor)
                            
                            if start_total is not None and end_total is not None:
                                if prev_month == 1:
                                    calculated_history[month_key] = end_total
                                else:
                                    calculated_history[month_key] = end_total - start_total
                            else:
                                _LOGGER.warning(
                                    "Could not calculate previous month usage: missing anchor data for %s",
                                    month_key,
                                    extra={"month": month_key, "has_start": start_total is not None, "has_end": end_total is not None}
                                )
                        except Exception as err:
                            _LOGGER.warning(
                                "Failed to calculate previous month usage for %s: %s",
                                month_key,
                                err,
                                extra={"month": month_key, "error_type": type(err).__name__},
                                exc_info=True
                            )
                    
                    # Step C: Current Month Calculation
                    try:
                        current_month = datetime.now().month
                        current_year = datetime.now().year
                        current_month_first_day = DateUtil.get_first_day_of_month(current_month, current_year)
                        
                        current_month_start_anchor = await api.get_device_statuses_for_date(current_month_first_day)
                        current_month_start_total = DataUtil.calculate_filter_status_total(current_month_start_anchor)
                        current_readings_total = DataUtil.calculate_filter_status_total(filter_status)
                        
                        if current_month_start_total is not None and current_readings_total is not None:
                            if current_month == 1:
                                current_month_calculated = current_readings_total
                            else:
                                current_month_calculated = current_readings_total - current_month_start_total
                        else:
                            _LOGGER.debug(
                                "Could not calculate current month usage: missing anchor data",
                                extra={"has_start": current_month_start_total is not None, "has_current": current_readings_total is not None}
                            )
                    except Exception as err:
                        _LOGGER.warning(
                            "Failed to calculate current month usage: %s",
                            err,
                            extra={"error_type": type(err).__name__},
                            exc_info=True
                        )
                
                except Exception as err:
                    _LOGGER.warning(
                        "Error in anchor calculation logic: %s",
                        err,
                        extra={"error_type": type(err).__name__},
                        exc_info=True
                    )
                
                monthly_history_cache: Dict[str, Dict[str, Any]] = {}
                cached_last_update_date: Optional[str] = None
                
                if entry.entry_id in hass.data.get(DOMAIN, {}):
                    existing_coordinator = hass.data[DOMAIN][entry.entry_id]
                    if existing_coordinator and existing_coordinator.data:
                        monthly_history_cache = existing_coordinator.data.get("monthly_history_cache", {})
                        cached_last_update_date = existing_coordinator.data.get("cached_last_update_date")
                
                current_last_update_date = None
                if isinstance(last_update, dict):
                    current_last_update_date = last_update.get("lastSyncDate") or last_update.get("date")
                elif isinstance(last_update, str):
                    current_last_update_date = last_update
                
                last_update_date_changed = current_last_update_date != cached_last_update_date
                
                try:
                    if not monthly_history_cache:
                        _LOGGER.info(f"Building {CACHE_HISTORY_MONTHS}-month history cache (this may take a moment)")
                        last_sync_date_obj = DateUtil.parse_last_sync_date(last_update)
                        if last_sync_date_obj:
                            prev_month, prev_year = DateUtil.get_previous_month_from_date(last_sync_date_obj)
                            prev_month_date = DateUtil.get_first_day_of_month(prev_month, prev_year)
                            months_to_build = DateUtil.get_last_n_months_from_date(CACHE_HISTORY_MONTHS, prev_month_date)
                        else:
                            now = datetime.now()
                            prev_month, prev_year = DateUtil.get_previous_month()
                            prev_month_date = DateUtil.get_first_day_of_month(prev_month, prev_year)
                            months_to_build = DateUtil.get_last_n_months_from_date(CACHE_HISTORY_MONTHS, prev_month_date)
                        
                        months_to_build = list(reversed(months_to_build))
                        
                        for month_num, year in months_to_build:
                            month_key = DateUtil.format_month_key(year, month_num)
                            
                            try:
                                first_day = DateUtil.get_first_day_of_month(month_num, year)
                                last_day = DateUtil.get_last_day_of_month(month_num, year)
                                
                                end_anchor = await api.get_device_statuses_for_date(last_day)
                                end_readings = DataUtil.extract_device_readings_map(end_anchor)
                                end_total = DataUtil.calculate_filter_status_total(end_anchor)
                                
                                now = datetime.now()
                                is_current_month = (month_num == now.month and year == now.year)
                                
                                if month_num == 1:
                                    start_readings = {}
                                    start_total = DEFAULT_START_VALUE
                                    devices_list = []
                                    for device_id_str, end_value in end_readings.items():
                                        try:
                                            devices_list.append({
                                                "id": device_id_str,
                                                "start": DEFAULT_START_VALUE,
                                                "end": float(end_value)
                                            })
                                        except (ValueError, TypeError):
                                            continue
                                else:
                                    prev_month, prev_year = DateUtil.get_previous_month_from_date(first_day)
                                    prev_month_key = DateUtil.format_month_key(prev_year, prev_month)
                                    prev_month_data = monthly_history_cache.get(prev_month_key)
                                    
                                    if prev_month_data and isinstance(prev_month_data, dict):
                                        prev_devices = prev_month_data.get("devices", [])
                                        start_readings = _extract_end_values_from_devices(prev_devices)
                                    else:
                                        prev_last_day = DateUtil.get_last_day_of_month(prev_month, prev_year)
                                        prev_anchor = await api.get_device_statuses_for_date(prev_last_day)
                                        start_readings = DataUtil.extract_device_readings_map(prev_anchor)
                                    
                                    start_total = sum(start_readings.values()) if start_readings else None
                                    
                                    if is_current_month:
                                        existing_month_cache = monthly_history_cache.get(month_key, {})
                                        existing_devices = existing_month_cache.get("devices", [])
                                        has_start_values = any(
                                            isinstance(device, dict) and device.get("start") is not None
                                            for device in existing_devices
                                        )
                                        
                                        if not has_start_values:
                                            devices_list = DataUtil.calculate_per_device_usage(start_readings, end_readings)
                                        else:
                                            devices_list = existing_devices
                                    else:
                                        devices_list = DataUtil.calculate_per_device_usage(start_readings, end_readings)
                                
                                if start_total is not None and end_total is not None:
                                    if end_total < start_total:
                                        total_usage = end_total
                                    else:
                                        total_usage = end_total - start_total
                                else:
                                    total_usage = None
                                
                                average_usage = None
                                finalized = False
                                month_year_str = f"{month_num}.{year}"
                                
                                if isinstance(energy_usage_data, dict):
                                    monthly_usages = energy_usage_data.get("monthlyEnergyUsages", [])
                                    for month in monthly_usages:
                                        if isinstance(month, dict) and month.get("monthYear") == month_year_str:
                                            avg = month.get("averageEnergyUseForBillingUnit")
                                            if avg is not None:
                                                try:
                                                    average_usage = float(avg)
                                                    finalized = True
                                                except (ValueError, TypeError):
                                                    pass
                                            break
                                
                                if average_usage is None and isinstance(usage_last_year_data, dict):
                                    monthly_usages = usage_last_year_data.get("monthlyEnergyUsages", [])
                                    for month in monthly_usages:
                                        if isinstance(month, dict) and month.get("monthYear") == month_year_str:
                                            avg = month.get("averageEnergyUseForBillingUnit")
                                            if avg is not None:
                                                try:
                                                    average_usage = float(avg)
                                                    finalized = True
                                                except (ValueError, TypeError):
                                                    pass
                                            break
                                
                                month_year_key = f"{month_num}.{year}"
                                monthly_history_cache[month_key] = {
                                    "month_id": month_year_key,
                                    "year": year,
                                    "month": month_num,
                                    "start_date": DateUtil.format_date_for_api(first_day),
                                    "end_date": DateUtil.format_date_for_api(last_day),
                                    "total_usage": total_usage,
                                    "average_usage": average_usage,
                                    "devices": devices_list,
                                    "finalized": finalized
                                }
                                
                            except Exception as err:
                                _LOGGER.warning(
                                    "Failed to build cache entry for %s: %s",
                                    month_key,
                                    err,
                                    extra={"month": month_key, "error_type": type(err).__name__},
                                    exc_info=True
                                )
                                month_year_key = f"{month_num}.{year}"
                                monthly_history_cache[month_key] = {
                                    "month_id": month_year_key,
                                    "year": year,
                                    "month": month_num,
                                    "start_date": DateUtil.format_date_for_api(DateUtil.get_first_day_of_month(month_num, year)),
                                    "end_date": DateUtil.format_date_for_api(DateUtil.get_last_day_of_month(month_num, year)),
                                    "total_usage": None,
                                    "average_usage": None,
                                    "devices": [],
                                    "finalized": False
                                }
                    
                    else:
                        if last_update_date_changed:
                            current_month = datetime.now().month
                            current_year = datetime.now().year
                            current_month_key = DateUtil.format_month_key(current_year, current_month)
                            
                            try:
                                current_month_first_day = DateUtil.get_first_day_of_month(current_month, current_year)
                                
                                current_month_cache = monthly_history_cache.get(current_month_key, {})
                                existing_devices = current_month_cache.get("devices", [])
                                has_start_values = any(
                                    isinstance(device, dict) and device.get("start") is not None
                                    for device in existing_devices
                                )
                                
                                end_readings = DataUtil.extract_device_readings_map(filter_status)
                                end_total = DataUtil.calculate_filter_status_total(filter_status)
                                
                                if not has_start_values:
                                    if current_month == 1:
                                        start_readings = {}
                                        start_total = DEFAULT_START_VALUE
                                        devices_list = []
                                        for device_id_str, end_value in end_readings.items():
                                            try:
                                                devices_list.append({
                                                    "id": device_id_str,
                                                    "start": DEFAULT_START_VALUE,
                                                    "end": float(end_value)
                                                })
                                            except (ValueError, TypeError):
                                                continue
                                    else:
                                        prev_month, prev_year = DateUtil.get_previous_month()
                                        prev_month_key = DateUtil.format_month_key(prev_year, prev_month)
                                        prev_month_data = monthly_history_cache.get(prev_month_key)
                                        
                                        if prev_month_data and isinstance(prev_month_data, dict):
                                            prev_devices = prev_month_data.get("devices", [])
                                            start_readings = _extract_end_values_from_devices(prev_devices)
                                        else:
                                            prev_last_day = DateUtil.get_last_day_of_month(prev_month, prev_year)
                                            prev_anchor = await api.get_device_statuses_for_date(prev_last_day)
                                            start_readings = DataUtil.extract_device_readings_map(prev_anchor)
                                        
                                        start_total = sum(start_readings.values()) if start_readings else None
                                        devices_list = DataUtil.calculate_per_device_usage(start_readings, end_readings)
                                else:
                                    devices_list = existing_devices
                                    if current_month == 1:
                                        start_total = DEFAULT_START_VALUE
                                    else:
                                        prev_month, prev_year = DateUtil.get_previous_month()
                                        prev_month_key = DateUtil.format_month_key(prev_year, prev_month)
                                        prev_month_data = monthly_history_cache.get(prev_month_key)
                                        
                                        if prev_month_data and isinstance(prev_month_data, dict):
                                            prev_devices = prev_month_data.get("devices", [])
                                            start_readings = _extract_end_values_from_devices(prev_devices)
                                            start_total = sum(start_readings.values()) if start_readings else None
                                        else:
                                            prev_last_day = DateUtil.get_last_day_of_month(prev_month, prev_year)
                                            prev_anchor = await api.get_device_statuses_for_date(prev_last_day)
                                            start_total = DataUtil.calculate_filter_status_total(prev_anchor)
                                
                                if start_total is not None and end_total is not None:
                                    if current_month == 1:
                                        total_usage = end_total
                                    else:
                                        total_usage = end_total - start_total
                                else:
                                    total_usage = None
                                
                                end_date_str = None
                                last_sync_date_obj = DateUtil.parse_last_sync_date(last_update)
                                if last_sync_date_obj:
                                    end_date_str = DateUtil.format_date_for_api(last_sync_date_obj)
                                else:
                                    end_date_str = DateUtil.format_date_for_api(DateUtil.get_last_day_of_month(current_month, current_year))
                                
                                average_usage = None
                                finalized = False
                                if isinstance(energy_usage_data, dict):
                                    monthly_usages = energy_usage_data.get("monthlyEnergyUsages", [])
                                    month_year_str = f"{current_month}.{current_year}"
                                    for month in monthly_usages:
                                        if isinstance(month, dict) and month.get("monthYear") == month_year_str:
                                            avg = month.get("averageEnergyUseForBillingUnit")
                                            if avg is not None:
                                                try:
                                                    average_usage = float(avg)
                                                    finalized = True
                                                except (ValueError, TypeError):
                                                    pass
                                            break
                                
                                current_month_year_key = f"{current_month}.{current_year}"
                                monthly_history_cache[current_month_key] = {
                                    "month_id": current_month_year_key,
                                    "year": current_year,
                                    "month": current_month,
                                    "start_date": DateUtil.format_date_for_api(current_month_first_day),
                                    "end_date": end_date_str,
                                    "total_usage": total_usage,
                                    "average_usage": average_usage,
                                    "devices": devices_list,
                                    "finalized": finalized
                                }
                                
                            except Exception as err:
                                _LOGGER.warning(
                                    "Failed to refresh current month in cache: %s",
                                    err,
                                    extra={"error_type": type(err).__name__},
                                    exc_info=True
                                )
                    
                    # Enrich all months with averages from official analytics (runs after both initial build and incremental updates)
                    for usage_data_source in [energy_usage_data, usage_last_year_data]:
                        if not isinstance(usage_data_source, dict):
                            continue
                        
                        monthly_usages = usage_data_source.get("monthlyEnergyUsages", [])
                        for month in monthly_usages:
                            if not isinstance(month, dict):
                                continue
                            
                            month_year_str = month.get("monthYear")
                            if not month_year_str:
                                continue
                            
                            parsed = DataUtil.parse_month_year(month_year_str)
                            if not parsed:
                                continue
                            
                            month_num, year = parsed
                            month_key = DateUtil.format_month_key(year, month_num)
                            
                            if month_key in monthly_history_cache:
                                cache_entry = monthly_history_cache[month_key]
                                avg = month.get("averageEnergyUseForBillingUnit")
                                if avg is not None:
                                    try:
                                        average_usage = float(avg)
                                        if not cache_entry.get("finalized", False) or cache_entry.get("average_usage") is None:
                                            cache_entry["average_usage"] = average_usage
                                            cache_entry["finalized"] = True
                                            _LOGGER.debug(
                                                "Enriched month %s with average: %s",
                                                month_key,
                                                average_usage
                                            )
                                    except (ValueError, TypeError):
                                        pass
                
                except Exception as err:
                    _LOGGER.warning(
                        "Error in monthly history cache logic: %s",
                        err,
                        extra={"error_type": type(err).__name__},
                        exc_info=True
                    )
                
                return {
                    "energy_usage": energy_usage_total,
                    "energy_usage_data": energy_usage_data,
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
                    "last_successful_sync": last_successful_sync,
                    "calculated_history": calculated_history,
                    "current_month_calculated": current_month_calculated,
                    "monthly_history_cache": monthly_history_cache,
                    "cached_last_update_date": current_last_update_date
                }
        except MijntedGrantExpiredError as err:
            _LOGGER.warning(
                "Refresh token grant has expired. Triggering re-authentication flow: %s",
                err,
                extra={"entry_id": entry.entry_id, "error_type": "MijntedGrantExpiredError"}
            )
            flows_in_progress = [
                flow
                for flow in hass.config_entries.flow.async_progress()
                if flow.get("handler") == DOMAIN
                and flow.get("context", {}).get("entry_id") == entry.entry_id
                and flow.get("context", {}).get("source") == "reauth"
            ]
            
            if not flows_in_progress:
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": "reauth", "entry_id": entry.entry_id},
                        data=entry.data,
                    )
                )
            else:
                _LOGGER.debug(
                    "Reauth flow already in progress, skipping duplicate trigger",
                    extra={"entry_id": entry.entry_id}
                )
            raise UpdateFailed(
                "Refresh token has expired. Please re-authenticate using the configuration flow."
            ) from err
        except MijntedAuthenticationError as err:
            _LOGGER.error(
                "Authentication error: %s",
                err,
                extra={"entry_id": entry.entry_id, "error_type": "MijntedAuthenticationError"}
            )
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except MijntedConnectionError as err:
            cached_data = None
            if entry.entry_id in hass.data.get(DOMAIN, {}):
                coordinator = hass.data[DOMAIN][entry.entry_id]
                if coordinator.data:
                    cached_data = coordinator.data
            
            token_expired = api.auth.is_access_token_expired() if api.auth else True
            
            if token_expired:
                _LOGGER.error(
                    "Connection error with expired token: %s",
                    err,
                    extra={"entry_id": entry.entry_id, "error_type": "MijntedConnectionError", "token_expired": True}
                )
                raise UpdateFailed(f"Connection failed: {err}") from err
            
            if cached_data:
                _LOGGER.warning(
                    "Connection error, returning cached data (token still valid): %s",
                    err,
                    extra={"entry_id": entry.entry_id, "error_type": "MijntedConnectionError", "using_cached_data": True}
                )
                return cached_data
            
            _LOGGER.error(
                "Connection error with no cached data available: %s",
                err,
                extra={"entry_id": entry.entry_id, "error_type": "MijntedConnectionError", "has_cached_data": False}
            )
            raise UpdateFailed(f"Connection failed: {err}") from err
        except MijntedApiError as err:
            _LOGGER.error(
                "API error: %s",
                err,
                extra={"entry_id": entry.entry_id, "error_type": "MijntedApiError"}
            )
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:
            _LOGGER.exception(
                "Unexpected error communicating with API: %s",
                err,
                extra={"entry_id": entry.entry_id, "error_type": type(err).__name__}
            )
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

