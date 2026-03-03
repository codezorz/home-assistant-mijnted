import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MijntedApi
from .const import (
    CACHE_HISTORY_MONTHS,
    CONF_PASSWORD,
    CONF_POLLING_INTERVAL,
    CONF_USERNAME,
    DEFAULT_POLLING_INTERVAL,
    DEFAULT_START_VALUE,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .exceptions import (
    MijntedApiError,
    MijntedAuthenticationError,
    MijntedConnectionError,
    MijntedGrantExpiredError,
)
from .utils import ApiUtil, DataUtil, DateUtil, TimestampUtil
from .sensors.base import MijnTedSensor
from .sensors.models import (
    DeviceReading,
    MONTH_STATE_COMPLETE_READINGS,
    MONTH_STATE_FINALIZED,
    MONTH_STATE_OPEN,
    MonthCacheEntry,
    StatisticsTracking,
    VALID_MONTH_STATES,
)

_LOGGER = logging.getLogger(__name__)


async def _load_persisted_cache(hass: HomeAssistant, entry_id: str) -> Optional[Dict[str, MonthCacheEntry]]:
    """Load monthly history cache from persistent storage."""
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")
    try:
        data = await store.async_load()
        if data and isinstance(data, dict):
            cache = data.get("monthly_history_cache")
            if isinstance(cache, dict):
                validated_cache: Dict[str, MonthCacheEntry] = {}
                for month_key, cache_entry_dict in cache.items():
                    if not isinstance(cache_entry_dict, dict):
                        continue
                    
                    try:
                        cache_entry = MonthCacheEntry.from_dict(cache_entry_dict)
                    except Exception as err:
                        _LOGGER.warning("Failed to deserialize cache entry for %s: %s", month_key, err)
                        continue
                    
                    cache_entry_dict_check = cache_entry.to_dict()
                    if _is_month_cache_complete(cache_entry_dict_check, DateUtil.is_current_month_from_key(month_key)):
                        validated_cache[month_key] = cache_entry
                
                if validated_cache:
                    _LOGGER.debug("Loaded %d complete months from persistent storage", len(validated_cache))
                    return validated_cache
    except Exception as err:
        _LOGGER.warning("Failed to load persisted cache: %s", err)
    return None


async def _save_persisted_cache(
    hass: HomeAssistant, 
    entry_id: str, 
    monthly_history_cache: Dict[str, MonthCacheEntry]
) -> None:
    """Save monthly history cache to persistent storage."""
    complete_cache: Dict[str, Dict[str, Any]] = {}
    for month_key, cache_entry in monthly_history_cache.items():
        if not isinstance(cache_entry, MonthCacheEntry):
            try:
                if isinstance(cache_entry, dict):
                    cache_entry = MonthCacheEntry.from_dict(cache_entry)
                else:
                    continue
            except Exception as err:
                _LOGGER.warning("Failed to convert cache entry for %s: %s", month_key, err)
                continue
        
        cache_entry_dict = cache_entry.to_dict()
        if _is_month_cache_complete(cache_entry_dict, DateUtil.is_current_month_from_key(month_key)):
            complete_cache[month_key] = cache_entry_dict
    
    if not complete_cache:
        _LOGGER.debug("No complete months to persist")
        return
    
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")
    try:
        await store.async_save({"monthly_history_cache": complete_cache})
        _LOGGER.debug("Saved %d complete months to persistent storage", len(complete_cache))
    except Exception as err:
        _LOGGER.warning("Failed to save persisted cache: %s", err)


async def _clear_persisted_cache(hass: HomeAssistant, entry_id: str) -> None:
    """Clear monthly history cache from persistent storage."""
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")
    try:
        await store.async_save({"monthly_history_cache": {}})
        _LOGGER.info("Cleared persisted cache for entry %s", entry_id)
    except Exception as err:
        _LOGGER.warning("Failed to clear persisted cache: %s", err)


def _derive_month_state(finalized: bool, complete_readings: bool) -> str:
    """Return normalized month state from finalized and complete-readings flags."""
    if finalized:
        return MONTH_STATE_FINALIZED
    if complete_readings:
        return MONTH_STATE_COMPLETE_READINGS
    return MONTH_STATE_OPEN


def _get_cache_entry_state(cache_entry: Any) -> str:
    """Return cache-entry state with backward-compatible fallback rules."""
    state: Optional[str] = None
    finalized = False

    if isinstance(cache_entry, MonthCacheEntry):
        state = cache_entry.state
        finalized = cache_entry.finalized
    elif isinstance(cache_entry, dict):
        state = cache_entry.get("state")
        finalized = bool(cache_entry.get("finalized", False))

    if isinstance(state, str) and state in VALID_MONTH_STATES:
        return state
    return MONTH_STATE_FINALIZED if finalized else MONTH_STATE_OPEN


def _is_cache_entry_start_locked(cache_entry: Any) -> bool:
    """Return True when cache entry has start values marked as locked."""
    if isinstance(cache_entry, MonthCacheEntry):
        return cache_entry.start_locked
    if isinstance(cache_entry, dict):
        return bool(cache_entry.get("start_locked", False))
    return False


def _has_complete_readings_for_month(last_update: Any, month_num: int, year: int) -> bool:
    """Return True when last_update is at or beyond the month's last day."""
    last_sync_date = DateUtil.parse_last_sync_date(last_update)
    if not last_sync_date:
        return False
    month_last_day = DateUtil.get_last_day_of_month(month_num, year)
    return last_sync_date >= month_last_day


def _is_month_cache_complete(
    cache_entry: Dict[str, Any],
    is_current_month: bool = False
) -> bool:
    """Check if a month cache entry has complete data."""
    if not isinstance(cache_entry, dict):
        return False
    
    total_usage = cache_entry.get("total_usage")
    if total_usage is None:
        return False
    
    devices = cache_entry.get("devices", [])
    if not devices or not isinstance(devices, list):
        return False
    
    if not is_current_month:
        state = cache_entry.get("state")
        if state not in (MONTH_STATE_COMPLETE_READINGS, MONTH_STATE_FINALIZED):
            finalized = bool(cache_entry.get("finalized", False))
            if not finalized:
                return False
    
    return True


def _is_previous_month_readings_complete(last_update: Any, now: datetime) -> bool:
    """Return True when last_update has reached previous month last day."""
    first_day_current = DateUtil.get_first_day_of_month(now.month, now.year)
    prev_month, prev_year = DateUtil.get_previous_month_from_date(first_day_current)
    return _has_complete_readings_for_month(last_update, prev_month, prev_year)


def _readings_list_to_dicts(device_readings: List[DeviceReading]) -> List[Dict[str, Any]]:
    """Convert a list of DeviceReading objects to dictionaries."""
    return [reading.to_dict() for reading in device_readings]


def _extract_prev_month_keys_from_current(current_month: int, current_year: int) -> Tuple[int, int, str]:
    """Return (prev_month, prev_year, prev_month_key) for the current month context."""
    current_month_first_day = DateUtil.get_first_day_of_month(current_month, current_year)
    prev_month, prev_year = DateUtil.get_previous_month_from_date(current_month_first_day)
    return prev_month, prev_year, DateUtil.format_month_key(prev_year, prev_month)


def _build_updated_month_cache_entry(
    cache_entry: MonthCacheEntry,
    *,
    total_usage: Optional[float],
    average_usage: Optional[float],
    devices: List[DeviceReading],
    finalized: bool,
    state: str,
    start_locked: bool
) -> MonthCacheEntry:
    """Build updated MonthCacheEntry while preserving date and id fields."""
    return MonthCacheEntry(
        month_id=cache_entry.month_id,
        year=cache_entry.year,
        month=cache_entry.month,
        start_date=cache_entry.start_date,
        end_date=cache_entry.end_date,
        total_usage=total_usage,
        average_usage=average_usage,
        devices=devices,
        finalized=finalized,
        state=state,
        start_locked=start_locked,
    )


def _normalize_month_state(state: Any, finalized: bool = False) -> str:
    """Normalize arbitrary state value to a known month state."""
    if finalized:
        return MONTH_STATE_FINALIZED
    if isinstance(state, str) and state in VALID_MONTH_STATES:
        return state
    return MONTH_STATE_OPEN


def _mark_month_complete_readings(cache_entry: Any) -> Any:
    """Set month state to COMPLETE_READINGS unless already finalized."""
    if isinstance(cache_entry, MonthCacheEntry):
        new_state = MONTH_STATE_FINALIZED if cache_entry.finalized else MONTH_STATE_COMPLETE_READINGS
        if cache_entry.state == new_state:
            return cache_entry
        return _build_updated_month_cache_entry(
            cache_entry,
            total_usage=cache_entry.total_usage,
            average_usage=cache_entry.average_usage,
            devices=cache_entry.devices,
            finalized=cache_entry.finalized,
            state=new_state,
            start_locked=cache_entry.start_locked,
        )
    if isinstance(cache_entry, dict):
        finalized = bool(cache_entry.get("finalized", False))
        new_state = MONTH_STATE_FINALIZED if finalized else MONTH_STATE_COMPLETE_READINGS
        cache_entry["state"] = new_state
        return cache_entry
    return cache_entry


def _mark_month_finalized(cache_entry: Any, average_usage: float) -> Any:
    """Set month state to FINALIZED and persist the provided average usage."""
    if isinstance(cache_entry, MonthCacheEntry):
        return _build_updated_month_cache_entry(
            cache_entry,
            total_usage=cache_entry.total_usage,
            average_usage=average_usage,
            devices=cache_entry.devices,
            finalized=True,
            state=MONTH_STATE_FINALIZED,
            start_locked=cache_entry.start_locked,
        )
    if isinstance(cache_entry, dict):
        cache_entry["average_usage"] = average_usage
        cache_entry["finalized"] = True
        cache_entry["state"] = MONTH_STATE_FINALIZED
        return cache_entry
    return cache_entry


def _is_current_month_start_locked(monthly_history_cache: Dict[str, Any], now: datetime) -> bool:
    """Return True when current month cache entry has start lock enabled."""
    current_month_key = DateUtil.format_month_key(now.year, now.month)
    return _is_cache_entry_start_locked(monthly_history_cache.get(current_month_key))


def _should_lock_current_month_starts(
    monthly_history_cache: Dict[str, Any],
    last_update: Any,
    now: datetime,
) -> bool:
    """Return True when previous month reached complete readings and current start is not locked."""
    if not _is_previous_month_readings_complete(last_update, now):
        return False
    return not _is_current_month_start_locked(monthly_history_cache, now)


def _ensure_month_cache_entry_state(entry: MonthCacheEntry) -> MonthCacheEntry:
    """Normalize state/finalized relationship for MonthCacheEntry."""
    if entry.finalized:
        normalized_state = MONTH_STATE_FINALIZED
    elif isinstance(entry.state, str) and entry.state in VALID_MONTH_STATES:
        normalized_state = entry.state
    else:
        normalized_state = MONTH_STATE_OPEN
    if normalized_state == entry.state:
        return entry
    return _build_updated_month_cache_entry(
        entry,
        total_usage=entry.total_usage,
        average_usage=entry.average_usage,
        devices=entry.devices,
        finalized=entry.finalized,
        state=normalized_state,
        start_locked=entry.start_locked,
    )


def _ensure_dict_cache_entry_state(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize state/finalized relationship for dict cache entries."""
    finalized = bool(entry.get("finalized", False))
    state_raw = entry.get("state")
    if finalized:
        entry["state"] = MONTH_STATE_FINALIZED
    elif isinstance(state_raw, str) and state_raw in VALID_MONTH_STATES:
        entry["state"] = state_raw
    else:
        entry["state"] = MONTH_STATE_OPEN
    if "start_locked" not in entry:
        entry["start_locked"] = False
    return entry


def _normalize_cache_entry_state(cache_entry: Any) -> Any:
    """Normalize state fields for MonthCacheEntry or dict cache entries."""
    if isinstance(cache_entry, MonthCacheEntry):
        return _ensure_month_cache_entry_state(cache_entry)
    if isinstance(cache_entry, dict):
        return _ensure_dict_cache_entry_state(cache_entry)
    return cache_entry


def _devices_have_start_values(devices: List[Dict[str, Any]]) -> bool:
    """Check if any device in the list has a non-None start value."""
    return any(
        isinstance(device, dict) and device.get("start") is not None
        for device in devices
    )


def _convert_device_dicts_to_readings(devices_list: List[Any]) -> List[DeviceReading]:
    """Convert a list of device dicts to DeviceReading objects via from_dict."""
    device_readings: List[DeviceReading] = []
    for device_dict in devices_list:
        if isinstance(device_dict, dict):
            device = DeviceReading.from_dict(device_dict)
            if device:
                device_readings.append(device)
    return device_readings


def _extract_end_values_from_devices(devices_list: List[Dict[str, Any]]) -> Dict[str, float]:
    """Extract end values from devices list."""
    end_readings = {}
    for device in devices_list:
        if isinstance(device, dict):
            device_id = device.get("id")
            end_value = device.get("end")
            if device_id is not None and end_value is not None:
                converted = DataUtil.safe_float(end_value)
                if converted is not None:
                    end_readings[str(device_id)] = converted
    return end_readings


def _has_usable_cache_data(entry: Any) -> bool:
    """Return True if cache entry has data worth preserving."""
    devices = MijnTedSensor._get_devices_from_cache_entry(entry)
    if _extract_end_values_from_devices(devices):
        return True
    if isinstance(entry, MonthCacheEntry):
        return entry.total_usage is not None
    if isinstance(entry, dict):
        return entry.get("total_usage") is not None
    return False


def _extract_start_values_from_devices(devices_list: List[Dict[str, Any]]) -> Dict[str, float]:
    """Extract start values from devices list."""
    start_readings = {}
    for device in devices_list:
        if isinstance(device, dict):
            device_id = device.get("id")
            start_value = device.get("start")
            if device_id is not None and start_value is not None:
                converted = DataUtil.safe_float(start_value)
                if converted is not None:
                    start_readings[str(device_id)] = converted
    return start_readings



def _extract_average_usage_from_energy_data(
    energy_usage_data: Dict[str, Any],
    month_num: int,
    year: int
) -> Tuple[Optional[float], bool]:
    """Extract average usage from energy usage data for a specific month."""
    if not isinstance(energy_usage_data, dict):
        return None, False
    
    month_year_str = DateUtil.format_month_year_key(month_num, year)
    monthly_usages = energy_usage_data.get("monthlyEnergyUsages", [])
    
    for month in monthly_usages:
        if isinstance(month, dict) and month.get("monthYear") == month_year_str:
            avg = month.get("averageEnergyUseForBillingUnit")
            if avg is not None:
                average_usage = DataUtil.safe_float(avg)
                if average_usage is not None:
                    return average_usage, True
            break
    
    return None, False


def _calculate_total_usage_from_start_end(
    start_total: Optional[float],
    end_total: Optional[float],
    month_num: int
) -> Optional[float]:
    """Calculate total usage from start and end totals."""
    if start_total is None or end_total is None:
        return None
    
    if month_num == 1:
        return end_total
    
    if end_total < start_total:
        return end_total
    
    return end_total - start_total


def _build_devices_list_for_january(end_readings: Dict[str, float]) -> List[Dict[str, Any]]:
    """Build devices list for January (start of year reset)."""
    devices_list = []
    for device_id_str, end_value in end_readings.items():
        converted = DataUtil.safe_float(end_value)
        if converted is not None:
            devices_list.append({
                "id": device_id_str,
                "start": DEFAULT_START_VALUE,
                "end": converted
            })
    return devices_list


async def _get_start_readings_from_previous_month(
    api: MijntedApi,
    monthly_history_cache: Dict[str, Any],
    month_num: int,
    year: int,
    first_day: date
) -> Tuple[Dict[str, float], Optional[float]]:
    """Get start readings from previous month, either from cache or API."""
    prev_month, prev_year = DateUtil.get_previous_month_from_date(first_day)
    prev_month_key = DateUtil.format_month_key(prev_year, prev_month)
    prev_month_data = monthly_history_cache.get(prev_month_key)
    
    if prev_month_data:
        prev_devices = MijnTedSensor._get_devices_from_cache_entry(prev_month_data)
        if prev_devices:
            start_readings = _extract_end_values_from_devices(prev_devices)
        else:
            start_readings = {}
    else:
        start_readings = {}
    
    if not start_readings:
        prev_last_day = DateUtil.get_last_day_of_month(prev_month, prev_year)
        prev_anchor = await api.get_device_statuses_for_date(prev_last_day)
        start_readings = DataUtil.extract_device_readings_map(prev_anchor)
    
    start_total = sum(start_readings.values()) if start_readings else None
    return start_readings, start_total


def _empty_month_cache_entry(month_num: int, year: int) -> MonthCacheEntry:
    """Build an empty MonthCacheEntry for a month (e.g. when API build fails)."""
    month_year_key = DateUtil.format_month_year_key(month_num, year)
    return MonthCacheEntry(
        month_id=month_year_key,
        year=year,
        month=month_num,
        start_date=DateUtil.format_date_for_api(DateUtil.get_first_day_of_month(month_num, year)),
        end_date=DateUtil.format_date_for_api(DateUtil.get_last_day_of_month(month_num, year)),
        total_usage=None,
        average_usage=None,
        devices=[],
        finalized=False,
        state=MONTH_STATE_OPEN,
        start_locked=False,
    )


def _resolve_devices_for_month(
    monthly_history_cache: Dict[str, Any],
    month_num: int,
    year: int,
    month_key: str,
    start_readings: Dict[str, float],
    end_readings: Dict[str, float],
) -> List[Any]:
    """Build device list for a month, handling January, current-month, and historical cases."""
    if month_num == 1:
        return _build_devices_list_for_january(end_readings)

    if DateUtil.is_current_month(month_num, year):
        existing = MijnTedSensor._get_devices_from_cache_entry(monthly_history_cache.get(month_key))
        if _devices_have_start_values(existing):
            return existing

    return DataUtil.calculate_per_device_usage(start_readings, end_readings)


async def _resolve_average_usage(
    api: MijntedApi,
    energy_usage_data: Dict[str, Any],
    month_num: int,
    year: int,
) -> Tuple[Optional[float], bool]:
    """Extract average usage from energy data, falling back to a per-year API call."""
    average_usage, finalized = _extract_average_usage_from_energy_data(
        energy_usage_data, month_num, year
    )
    if average_usage is not None:
        return (average_usage, finalized)
    try:
        year_data = await api.get_energy_usage(year)
        if isinstance(year_data, dict):
            return _extract_average_usage_from_energy_data(year_data, month_num, year)
    except Exception as err:
        _LOGGER.debug("Failed to fetch energy usage for year %s while building cache: %s", year, err)
    return (average_usage, finalized)


async def _build_month_cache_entry(
    api: MijntedApi,
    month_num: int,
    year: int,
    monthly_history_cache: Dict[str, Any],
    energy_usage_data: Dict[str, Any],
    complete_readings: bool = False,
) -> MonthCacheEntry:
    """Build a MonthCacheEntry for a specific month from API anchors and energy data."""
    month_key = DateUtil.format_month_key(year, month_num)
    first_day = DateUtil.get_first_day_of_month(month_num, year)
    last_day = DateUtil.get_last_day_of_month(month_num, year)

    end_anchor = await api.get_device_statuses_for_date(last_day)
    end_readings = DataUtil.extract_device_readings_map(end_anchor)
    end_total = DataUtil.calculate_filter_status_total(end_anchor)

    if month_num == 1:
        start_readings: Dict[str, float] = {}
        start_total: Optional[float] = DEFAULT_START_VALUE
    else:
        start_readings, start_total = await _get_start_readings_from_previous_month(
            api, monthly_history_cache, month_num, year, first_day
        )

    devices_list = _resolve_devices_for_month(
        monthly_history_cache, month_num, year, month_key, start_readings, end_readings
    )
    total_usage = _calculate_total_usage_from_start_end(start_total, end_total, month_num)
    average_usage, finalized = await _resolve_average_usage(api, energy_usage_data, month_num, year)
    month_state = _derive_month_state(finalized, complete_readings)

    return MonthCacheEntry(
        month_id=DateUtil.format_month_year_key(month_num, year),
        year=year,
        month=month_num,
        start_date=DateUtil.format_date_for_api(first_day),
        end_date=DateUtil.format_date_for_api(last_day),
        total_usage=total_usage,
        average_usage=average_usage,
        devices=_convert_device_dicts_to_readings(devices_list),
        finalized=finalized,
        state=month_state,
        start_locked=False,
    )


def _should_skip_existing_entry(existing_entry: Any, month_num: int, year: int) -> bool:
    """Return True if the existing cache entry is already complete and can be skipped."""
    if not existing_entry:
        return False
    if isinstance(existing_entry, MonthCacheEntry):
        entry_dict = existing_entry.to_dict()
    elif isinstance(existing_entry, dict):
        entry_dict = existing_entry
    else:
        return False
    return _is_month_cache_complete(entry_dict, DateUtil.is_current_month(month_num, year))


async def _build_initial_monthly_history_cache(
    api: MijntedApi,
    last_update: Any,
    energy_usage_data: Dict[str, Any],
    now: datetime,
    existing_cache: Optional[Dict[str, MonthCacheEntry]] = None,
) -> Dict[str, MonthCacheEntry]:
    """Build the initial N-month history cache from API data."""
    monthly_history_cache: Dict[str, MonthCacheEntry] = {}
    if existing_cache:
        monthly_history_cache = existing_cache.copy()
    
    _LOGGER.info(f"Building {CACHE_HISTORY_MONTHS}-month history cache (this may take a moment)")
    prev_month, prev_year = DateUtil.get_previous_month_from_date(
        date(now.year, now.month, 1)
    )
    prev_month_date = DateUtil.get_first_day_of_month(prev_month, prev_year)
    months_to_build = DateUtil.get_last_n_months_from_date(CACHE_HISTORY_MONTHS, prev_month_date)
    
    months_to_build = list(reversed(months_to_build))
    
    for month_num, year in months_to_build:
        month_key = DateUtil.format_month_key(year, month_num)
        if _should_skip_existing_entry(monthly_history_cache.get(month_key), month_num, year):
            _LOGGER.debug("Skipping %s - already has complete data, no API calls needed", month_key)
            continue
        
        try:
            complete_readings = _has_complete_readings_for_month(last_update, month_num, year)
            cache_entry = await _build_month_cache_entry(
                api, month_num, year, monthly_history_cache,
                energy_usage_data, complete_readings=complete_readings
            )
            monthly_history_cache[month_key] = _normalize_cache_entry_state(cache_entry)
        except Exception as err:
            _LOGGER.warning(
                "Failed to build cache entry for %s: %s",
                month_key,
                err,
                extra={"month": month_key, "error_type": type(err).__name__},
                exc_info=True
            )
            monthly_history_cache[month_key] = _empty_month_cache_entry(month_num, year)
    
    return monthly_history_cache


async def _resolve_current_month_devices(
    api: MijntedApi,
    monthly_history_cache: Dict[str, MonthCacheEntry],
    existing_devices: List[Dict[str, Any]],
    current_month: int,
    current_year: int,
    current_month_first_day: date,
    end_readings: Dict[str, float],
    start_locked: bool,
) -> Tuple[List[Any], Optional[float]]:
    """Resolve device list and start_total for the current month cache update."""
    if current_month == 1:
        return (_build_devices_list_for_january(end_readings), DEFAULT_START_VALUE)

    if start_locked and _devices_have_start_values(existing_devices):
        locked_start_readings = _extract_start_values_from_devices(existing_devices)
        if locked_start_readings:
            locked_start_total = sum(locked_start_readings.values())
            locked_devices = DataUtil.calculate_per_device_usage(locked_start_readings, end_readings)
            if locked_devices:
                return (locked_devices, locked_start_total)

    start_readings, start_total = await _get_start_readings_from_previous_month(
        api, monthly_history_cache, current_month, current_year, current_month_first_day
    )

    recalculated_devices = DataUtil.calculate_per_device_usage(start_readings, end_readings)
    if recalculated_devices:
        return (recalculated_devices, start_total)

    # Fallback: preserve existing month starts if previous-month anchors are unavailable.
    if _devices_have_start_values(existing_devices):
        existing_start_readings = _extract_start_values_from_devices(existing_devices)
        if existing_start_readings:
            fallback_start_total = sum(existing_start_readings.values())
            fallback_devices = DataUtil.calculate_per_device_usage(
                existing_start_readings, end_readings
            )
            if fallback_devices:
                return (fallback_devices, fallback_start_total)
        return (existing_devices, start_total)

    return ([], start_total)


def _resolve_current_month_end_date(last_update: Any, current_month: int, current_year: int) -> str:
    """Determine end date string from last_update or last day of month."""
    last_sync = DateUtil.parse_last_sync_date(last_update)
    if last_sync:
        return DateUtil.format_date_for_api(last_sync)
    return DateUtil.format_date_for_api(DateUtil.get_last_day_of_month(current_month, current_year))


async def _update_current_month_cache(
    api: MijntedApi,
    monthly_history_cache: Dict[str, MonthCacheEntry],
    filter_status: List[Dict[str, Any]],
    last_update: Any,
    energy_usage_data: Dict[str, Any],
    now: datetime,
) -> None:
    """Update the current month's cache entry with latest filter status and API data."""
    current_month = now.month
    current_year = now.year
    current_month_key = DateUtil.format_month_key(current_year, current_month)
    current_month_first_day = DateUtil.get_first_day_of_month(current_month, current_year)
    current_month_cache = _normalize_cache_entry_state(monthly_history_cache.get(current_month_key))
    existing_start_locked = _is_cache_entry_start_locked(current_month_cache)

    existing_devices = MijnTedSensor._get_devices_from_cache_entry(
        current_month_cache
    )
    end_readings = DataUtil.extract_device_readings_map(filter_status)
    if not end_readings and _has_usable_cache_data(current_month_cache):
        _LOGGER.debug(
            "Skipping current month %s cache update: filter_status is empty, preserving existing cache",
            current_month_key,
        )
        return
    end_total = DataUtil.calculate_filter_status_total(filter_status)

    devices_list, start_total = await _resolve_current_month_devices(
        api, monthly_history_cache, existing_devices,
        current_month, current_year, current_month_first_day, end_readings,
        existing_start_locked,
    )
    total_usage = _calculate_total_usage_from_start_end(start_total, end_total, current_month)
    end_date_str = _resolve_current_month_end_date(last_update, current_month, current_year)
    average_usage, finalized = _extract_average_usage_from_energy_data(
        energy_usage_data, current_month, current_year
    )
    month_state = _derive_month_state(finalized, False)

    monthly_history_cache[current_month_key] = MonthCacheEntry(
        month_id=DateUtil.format_month_year_key(current_month, current_year),
        year=current_year,
        month=current_month,
        start_date=DateUtil.format_date_for_api(current_month_first_day),
        end_date=end_date_str,
        total_usage=total_usage,
        average_usage=average_usage,
        devices=_convert_device_dicts_to_readings(devices_list),
        finalized=finalized,
        state=month_state,
        start_locked=existing_start_locked,
    )


async def _lock_current_month_starts_when_previous_complete(
    api: MijntedApi,
    monthly_history_cache: Dict[str, MonthCacheEntry],
    filter_status: List[Dict[str, Any]],
    last_update: Any,
    energy_usage_data: Dict[str, Any],
    now: datetime,
) -> bool:
    """Lock current-month start values once previous month reached complete readings."""
    current_month = now.month
    current_year = now.year
    current_month_key = DateUtil.format_month_key(current_year, current_month)

    if current_month == 1:
        return False
    if not _should_lock_current_month_starts(monthly_history_cache, last_update, now):
        return False

    prev_month, prev_year, prev_month_key = _extract_prev_month_keys_from_current(current_month, current_year)
    modified = False

    prev_month_data = _normalize_cache_entry_state(monthly_history_cache.get(prev_month_key))
    if isinstance(prev_month_data, MonthCacheEntry):
        monthly_history_cache[prev_month_key] = prev_month_data
    if not prev_month_data:
        try:
            prev_month_data = await _build_month_cache_entry(
                api,
                prev_month,
                prev_year,
                monthly_history_cache,
                energy_usage_data,
                complete_readings=True,
            )
            monthly_history_cache[prev_month_key] = _mark_month_complete_readings(prev_month_data)
            prev_month_data = monthly_history_cache.get(prev_month_key)
            modified = True
        except Exception as err:
            _LOGGER.warning(
                "Failed to build previous month %s while locking current starts: %s",
                prev_month_key,
                err,
                extra={"error_type": type(err).__name__},
                exc_info=True,
            )
            return modified

    prev_state_before = _get_cache_entry_state(prev_month_data)
    if prev_state_before == MONTH_STATE_OPEN:
        monthly_history_cache[prev_month_key] = _mark_month_complete_readings(prev_month_data)
        prev_month_data = monthly_history_cache.get(prev_month_key)
        modified = True
        _LOGGER.info(
            "Month %s transitioned OPEN -> COMPLETE_READINGS based on last_update.",
            prev_month_key
        )

    prev_devices = MijnTedSensor._get_devices_from_cache_entry(prev_month_data)
    prev_end_readings = _extract_end_values_from_devices(prev_devices)
    if not prev_end_readings:
        try:
            prev_last_day = DateUtil.get_last_day_of_month(prev_month, prev_year)
            prev_anchor = await api.get_device_statuses_for_date(prev_last_day)
            prev_end_readings = DataUtil.extract_device_readings_map(prev_anchor)
        except Exception as err:
            _LOGGER.warning(
                "Failed to fetch previous month end readings for start lock: %s",
                err,
                extra={"error_type": type(err).__name__},
                exc_info=True,
            )
            return modified

    current_month_cache = _normalize_cache_entry_state(monthly_history_cache.get(current_month_key))
    if isinstance(current_month_cache, MonthCacheEntry):
        monthly_history_cache[current_month_key] = current_month_cache
    if not current_month_cache:
        try:
            await _update_current_month_cache(
                api, monthly_history_cache, filter_status, last_update, energy_usage_data, now
            )
            current_month_cache = _normalize_cache_entry_state(monthly_history_cache.get(current_month_key))
            if isinstance(current_month_cache, MonthCacheEntry):
                monthly_history_cache[current_month_key] = current_month_cache
            modified = True
        except Exception as err:
            _LOGGER.warning(
                "Failed to create current month cache %s while locking starts: %s",
                current_month_key,
                err,
                extra={"error_type": type(err).__name__},
                exc_info=True,
            )
            return modified

    if not current_month_cache:
        return modified

    current_end_readings = DataUtil.extract_device_readings_map(filter_status)
    if not current_end_readings:
        return modified

    recalculated_devices = DataUtil.calculate_per_device_usage(prev_end_readings, current_end_readings)
    if not recalculated_devices:
        return modified

    existing_devices = MijnTedSensor._get_devices_from_cache_entry(current_month_cache)
    current_locked = _is_cache_entry_start_locked(current_month_cache)
    needs_recalc = _needs_device_start_recalculation(existing_devices, recalculated_devices)
    if not needs_recalc and current_locked:
        return modified

    _LOGGER.info(
        "Locking current month %s start values from previous month %s end readings.",
        current_month_key,
        prev_month_key
    )
    _apply_recalculated_devices(
        monthly_history_cache,
        current_month_key,
        current_month_cache,
        _convert_device_dicts_to_readings(recalculated_devices),
        prev_end_readings,
        filter_status,
        current_month,
        current_year,
        state=MONTH_STATE_OPEN,
        start_locked=True,
    )
    return True


def _did_previous_month_just_finalize(
    cache_before_enrich: Dict[str, Optional[float]],
    cache_after_enrich: Dict[str, Optional[float]],
    prev_month_key: str
) -> bool:
    """Check if the previous month's average_usage just transitioned from None to a value."""
    prev_before = cache_before_enrich.get(prev_month_key)
    prev_after = cache_after_enrich.get(prev_month_key)
    return prev_before is None and prev_after is not None


def _needs_device_start_recalculation(
    existing_devices: List[Dict[str, Any]],
    recalculated_devices: List[Dict[str, Any]]
) -> bool:
    """Check if any device start values differ between existing and recalculated lists."""
    existing_devices_map: Dict[str, Dict[str, Any]] = {}
    for device in existing_devices:
        if isinstance(device, dict):
            device_id = device.get("id")
            if device_id is not None:
                existing_devices_map[str(device_id)] = device

    for recalc_device in recalculated_devices:
        device_id_str = str(recalc_device.get("id", ""))
        existing_device = existing_devices_map.get(device_id_str)
        if existing_device:
            existing_start = DataUtil.safe_float(existing_device.get("start"))
            recalc_start = DataUtil.safe_float(recalc_device.get("start"))
            if existing_start != recalc_start:
                return True
        else:
            return True
    return False


def _apply_recalculated_devices(
    monthly_history_cache: Dict[str, MonthCacheEntry],
    current_month_key: str,
    current_month_cache: Any,
    device_readings: List[DeviceReading],
    prev_end_readings: Dict[str, float],
    filter_status: List[Dict[str, Any]],
    current_month: int,
    current_year: int,
    state: Optional[str] = None,
    start_locked: Optional[bool] = None,
) -> None:
    """Apply recalculated device readings and totals to the current month cache entry."""
    start_total = sum(prev_end_readings.values()) if prev_end_readings else None
    end_total = DataUtil.calculate_filter_status_total(filter_status)
    total_usage = _calculate_total_usage_from_start_end(start_total, end_total, current_month)

    if isinstance(current_month_cache, MonthCacheEntry):
        end_date_str = current_month_cache.end_date
        if not end_date_str:
            end_date_str = DateUtil.format_date_for_api(
                DateUtil.get_last_day_of_month(current_month, current_year)
            )
        current_state = _normalize_month_state(current_month_cache.state, current_month_cache.finalized)
        next_state = current_state if state is None else _normalize_month_state(
            state, current_month_cache.finalized
        )
        next_start_locked = current_month_cache.start_locked if start_locked is None else start_locked
        monthly_history_cache[current_month_key] = MonthCacheEntry(
            month_id=current_month_cache.month_id,
            year=current_month_cache.year,
            month=current_month_cache.month,
            start_date=current_month_cache.start_date,
            end_date=end_date_str,
            total_usage=total_usage,
            average_usage=current_month_cache.average_usage,
            devices=device_readings,
            finalized=current_month_cache.finalized,
            state=next_state,
            start_locked=next_start_locked,
        )
    elif isinstance(current_month_cache, dict):
        current_month_cache["devices"] = _readings_list_to_dicts(device_readings)
        current_month_cache["total_usage"] = total_usage
        if "total_usage_start" in current_month_cache:
            current_month_cache["total_usage_start"] = start_total
        if "total_usage_end" in current_month_cache:
            current_month_cache["total_usage_end"] = end_total
        finalized = bool(current_month_cache.get("finalized", False))
        if state is not None:
            current_month_cache["state"] = _normalize_month_state(state, finalized)
        elif "state" in current_month_cache:
            current_month_cache["state"] = _normalize_month_state(current_month_cache.get("state"), finalized)
        if start_locked is not None:
            current_month_cache["start_locked"] = start_locked


async def _recalculate_current_month_starts_if_previous_finalized(
    api: MijntedApi,
    monthly_history_cache: Dict[str, MonthCacheEntry],
    filter_status: List[Dict[str, Any]],
    cache_before_enrich: Dict[str, Optional[float]],
    cache_after_enrich: Dict[str, Optional[float]],
    now: datetime,
) -> bool:
    """Fallback recalculation when previous month just finalized and starts are not yet locked."""
    current_month = now.month
    current_year = now.year
    current_month_key = DateUtil.format_month_key(current_year, current_month)
    current_month_first_day = DateUtil.get_first_day_of_month(current_month, current_year)

    if current_month == 1:
        return False

    prev_month, prev_year = DateUtil.get_previous_month_from_date(current_month_first_day)
    prev_month_key = DateUtil.format_month_key(prev_year, prev_month)

    if not _did_previous_month_just_finalize(cache_before_enrich, cache_after_enrich, prev_month_key):
        return False

    prev_month_data = monthly_history_cache.get(prev_month_key)
    if not prev_month_data:
        return False

    prev_finalized = False
    if isinstance(prev_month_data, MonthCacheEntry):
        prev_finalized = prev_month_data.finalized and prev_month_data.average_usage is not None
    elif isinstance(prev_month_data, dict):
        prev_finalized = prev_month_data.get("finalized", False) and prev_month_data.get("average_usage") is not None
    if not prev_finalized:
        return False

    current_month_cache = monthly_history_cache.get(current_month_key)
    if not current_month_cache:
        return False
    if _is_cache_entry_start_locked(current_month_cache):
        return False

    prev_devices = MijnTedSensor._get_devices_from_cache_entry(prev_month_data)
    prev_end_readings = _extract_end_values_from_devices(prev_devices)
    if not prev_end_readings:
        try:
            prev_last_day = DateUtil.get_last_day_of_month(prev_month, prev_year)
            prev_anchor = await api.get_device_statuses_for_date(prev_last_day)
            prev_end_readings = DataUtil.extract_device_readings_map(prev_anchor)
        except Exception as err:
            _LOGGER.debug(
                "Failed to get previous month end readings from API for recalculation: %s",
                err
            )
            return False

    current_end_readings = DataUtil.extract_device_readings_map(filter_status)
    if not current_end_readings:
        return False

    recalculated_devices = DataUtil.calculate_per_device_usage(prev_end_readings, current_end_readings)
    if not recalculated_devices:
        return False

    existing_devices = MijnTedSensor._get_devices_from_cache_entry(current_month_cache)
    if not _needs_device_start_recalculation(existing_devices, recalculated_devices):
        return False

    _LOGGER.info(
        "Previous month %s just became finalized. Recalculating and locking current month %s start values.",
        prev_month_key,
        current_month_key
    )

    _apply_recalculated_devices(
        monthly_history_cache,
        current_month_key,
        current_month_cache,
        _convert_device_dicts_to_readings(recalculated_devices),
        prev_end_readings,
        filter_status,
        current_month,
        current_year,
        state=MONTH_STATE_OPEN,
        start_locked=True,
    )
    return True


def _collect_years_from_cache(monthly_history_cache: Dict[str, MonthCacheEntry]) -> set[int]:
    """Return the set of distinct years present in the cache."""
    years: set[int] = set()
    for cache_entry in monthly_history_cache.values():
        if isinstance(cache_entry, MonthCacheEntry):
            year = cache_entry.year
        elif isinstance(cache_entry, dict):
            year = cache_entry.get("year")
        else:
            continue
        if isinstance(year, int):
            years.add(year)
    return years


async def _fetch_missing_years_data(
    api: MijntedApi,
    years_needed: set[int],
    energy_usage_data: Dict[str, Any],
    current_year: int,
) -> Dict[int, Dict[str, Any]]:
    """Fetch energy-usage data for each required year, reusing current-year data when available."""
    years_with_data: Dict[int, Dict[str, Any]] = {}
    if isinstance(energy_usage_data, dict):
        if current_year in years_needed:
            years_with_data[current_year] = energy_usage_data

    for year in years_needed:
        if year not in years_with_data:
            try:
                year_data = await api.get_energy_usage(year)
                if isinstance(year_data, dict):
                    years_with_data[year] = year_data
                    _LOGGER.debug("Fetched energy usage data for year %s", year)
            except Exception as err:
                _LOGGER.warning(
                    "Failed to fetch energy usage data for year %s: %s",
                    year,
                    err,
                    extra={"year": year, "error_type": type(err).__name__}
                )
    return years_with_data


def _apply_enrichment_to_cache_entries(
    monthly_history_cache: Dict[str, MonthCacheEntry],
    years_with_data: Dict[int, Dict[str, Any]],
) -> None:
    """Update cache entries with average usage and finalized flag from API data."""
    for usage_data in years_with_data.values():
        if not isinstance(usage_data, dict):
            continue
        for month in usage_data.get("monthlyEnergyUsages", []):
            if not isinstance(month, dict):
                continue
            month_year_str = month.get("monthYear")
            if not month_year_str:
                continue
            parsed = DataUtil.parse_month_year(month_year_str)
            if not parsed:
                continue
            month_num, month_year = parsed
            month_key = DateUtil.format_month_key(month_year, month_num)
            if month_key not in monthly_history_cache:
                continue
            avg = month.get("averageEnergyUseForBillingUnit")
            if avg is None:
                continue
            average_usage = DataUtil.safe_float(avg)
            if average_usage is None:
                continue
            cache_entry = monthly_history_cache[month_key]
            if isinstance(cache_entry, MonthCacheEntry):
                if not cache_entry.finalized or cache_entry.average_usage is None:
                    monthly_history_cache[month_key] = _mark_month_finalized(cache_entry, average_usage)
                    _LOGGER.debug("Enriched month %s with average: %s", month_key, average_usage)
            elif isinstance(cache_entry, dict):
                if not cache_entry.get("finalized", False) or cache_entry.get("average_usage") is None:
                    _mark_month_finalized(cache_entry, average_usage)
                    _LOGGER.debug("Enriched month %s with average: %s", month_key, average_usage)


async def _enrich_cache_with_api_data(
    api: MijntedApi,
    monthly_history_cache: Dict[str, MonthCacheEntry],
    energy_usage_data: Dict[str, Any],
    now: datetime,
) -> None:
    """Enrich cache entries with average usage from API data for each required year."""
    years_needed = _collect_years_from_cache(monthly_history_cache)
    years_with_data = await _fetch_missing_years_data(api, years_needed, energy_usage_data, now.year)
    _apply_enrichment_to_cache_entries(monthly_history_cache, years_with_data)


def _parse_refresh_token_expires_at(entry: ConfigEntry) -> Optional[datetime]:
    """Parse refresh_token_expires_at from config entry data."""
    refresh_token_expires_at_str = entry.data.get("refresh_token_expires_at")
    if not refresh_token_expires_at_str:
        return None
    try:
        refresh_token_expires_at = datetime.fromisoformat(
            refresh_token_expires_at_str.replace("Z", "+00:00")
        )
        if refresh_token_expires_at.tzinfo is None:
            refresh_token_expires_at = refresh_token_expires_at.replace(tzinfo=timezone.utc)
        return refresh_token_expires_at
    except (ValueError, AttributeError) as err:
        _LOGGER.warning(
            "Could not parse refresh_token_expires_at from config: %s",
            refresh_token_expires_at_str,
            extra={"entry_id": entry.entry_id},
            exc_info=True
        )
        return None


def _handle_gather_result(
    name: str,
    result: Any,
    default_empty: Any,
    residential_unit: Optional[str],
) -> Any:
    """Handle result from asyncio.gather: return value or default and log on exception."""
    if isinstance(result, Exception):
        _LOGGER.warning(
            "Failed to fetch %s: %s",
            name,
            result,
            extra={
                "data_type": name,
                "residential_unit": residential_unit,
                "error_type": type(result).__name__
            }
        )
        return default_empty
    return result


def _build_room_usage(usage_per_room_data: Any) -> Dict[str, Any]:
    """Build room_usage dict from API usage_per_room response (dict or list)."""
    room_usage: Dict[str, Any] = {}
    if isinstance(usage_per_room_data, dict):
        rooms = usage_per_room_data.get("rooms", [])
        current_year_data = usage_per_room_data.get("currentYear", {})
        values = current_year_data.get("values", [])
        for i, room_name in enumerate(rooms):
            if i < len(values):
                value = values[i]
                if room_name in room_usage:
                    existing = DataUtil.safe_float(room_usage[room_name], 0.0) or 0.0
                    new_value = DataUtil.safe_float(value, 0.0) or 0.0
                    room_usage[room_name] = existing + new_value
                else:
                    room_usage[room_name] = DataUtil.safe_float(value, 0.0) or 0.0
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
    return room_usage


async def _fetch_and_normalize_api_data(api: MijntedApi) -> Dict[str, Any]:
    """Fetch all API data via gather + delivery_types and normalize (exceptions to defaults)."""
    last_year = DateUtil.get_last_year()
    (
        energy_usage_data,
        last_update_data,
        filter_status_data,
        usage_insight_data,
        usage_insight_last_year_data,
        active_model_data,
        residential_unit_detail_data,
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
        api.get_usage_per_room(),
        api.get_unit_of_measures(),
        return_exceptions=True,
    )
    residential_unit = api.residential_unit
    energy_usage_data = _handle_gather_result("energy_usage", energy_usage_data, {}, residential_unit)
    last_update_data = _handle_gather_result("last_update", last_update_data, {}, residential_unit)
    filter_status_data = _handle_gather_result("filter_status", filter_status_data, [], residential_unit)
    usage_insight_data = _handle_gather_result("usage_insight", usage_insight_data, {}, residential_unit)
    usage_insight_last_year_data = _handle_gather_result(
        "usage_insight_last_year", usage_insight_last_year_data, {}, residential_unit
    )
    active_model_data = _handle_gather_result("active_model", active_model_data, {}, residential_unit)
    residential_unit_detail_data = _handle_gather_result(
        "residential_unit_detail", residential_unit_detail_data, {}, residential_unit
    )
    usage_per_room_data = _handle_gather_result(
        "usage_per_room", usage_per_room_data, {}, residential_unit
    )
    unit_of_measures_data = _handle_gather_result(
        "unit_of_measures", unit_of_measures_data, [], residential_unit
    )
    delivery_types = await api.get_delivery_types()
    return {
        "energy_usage_data": energy_usage_data,
        "last_update_data": last_update_data,
        "filter_status_data": filter_status_data,
        "usage_insight_data": usage_insight_data,
        "usage_insight_last_year_data": usage_insight_last_year_data,
        "active_model_data": active_model_data,
        "residential_unit_detail_data": residential_unit_detail_data,
        "usage_per_room_data": usage_per_room_data,
        "unit_of_measures_data": unit_of_measures_data,
        "delivery_types": delivery_types,
    }


async def _compute_previous_month_anchor(
    api: MijntedApi,
    energy_usage_data: Dict[str, Any],
) -> Dict[str, float]:
    """Compute previous month usage from device anchors if not yet in analytics."""
    prev_month, prev_year = DateUtil.get_previous_month()
    month_key = DateUtil.format_month_year_key(prev_month, prev_year)

    if isinstance(energy_usage_data, dict):
        for month in energy_usage_data.get("monthlyEnergyUsages", []):
            if isinstance(month, dict) and month.get("monthYear") == month_key:
                return {}

    try:
        first_day = DateUtil.get_first_day_of_month(prev_month, prev_year)
        last_day = DateUtil.get_last_day_of_month(prev_month, prev_year)
        start_anchor = await api.get_device_statuses_for_date(first_day)
        end_anchor = await api.get_device_statuses_for_date(last_day)
        start_total = DataUtil.calculate_filter_status_total(start_anchor)
        end_total = DataUtil.calculate_filter_status_total(end_anchor)
        if start_total is not None and end_total is not None:
            usage = end_total if prev_month == 1 else end_total - start_total
            return {month_key: usage}
        _LOGGER.warning(
            "Could not calculate previous month usage: missing anchor data for %s",
            month_key,
            extra={"month": month_key, "has_start": start_total is not None, "has_end": end_total is not None},
        )
    except Exception as err:
        _LOGGER.warning(
            "Failed to calculate previous month usage for %s: %s",
            month_key, err,
            extra={"month": month_key, "error_type": type(err).__name__},
            exc_info=True,
        )
    return {}


async def _compute_current_month_anchor(
    api: MijntedApi,
    filter_status: List[Dict[str, Any]],
) -> Optional[float]:
    """Compute current month usage from first-day anchor vs current filter status."""
    try:
        now = datetime.now()
        first_day = DateUtil.get_first_day_of_month(now.month, now.year)
        start_anchor = await api.get_device_statuses_for_date(first_day)
        start_total = DataUtil.calculate_filter_status_total(start_anchor)
        current_total = DataUtil.calculate_filter_status_total(filter_status)
        if start_total is not None and current_total is not None:
            return current_total if now.month == 1 else current_total - start_total
        _LOGGER.debug(
            "Could not calculate current month usage: missing anchor data",
            extra={"has_start": start_total is not None, "has_current": current_total is not None},
        )
    except Exception as err:
        _LOGGER.warning(
            "Failed to calculate current month usage: %s", err,
            extra={"error_type": type(err).__name__},
            exc_info=True,
        )
    return None


async def _compute_anchor_calculations(
    api: MijntedApi,
    energy_usage_data: Dict[str, Any],
    filter_status: List[Dict[str, Any]],
) -> Tuple[Dict[str, float], Optional[float]]:
    """Compute calculated_history and current_month_calculated from device anchors."""
    try:
        calculated_history = await _compute_previous_month_anchor(api, energy_usage_data)
        current_month_calculated = await _compute_current_month_anchor(api, filter_status)
        return (calculated_history, current_month_calculated)
    except Exception as err:
        _LOGGER.warning(
            "Error in anchor calculation logic: %s", err,
            extra={"error_type": type(err).__name__},
            exc_info=True,
        )
    return ({}, None)


def _load_cache_from_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry
) -> Tuple[Dict[str, MonthCacheEntry], Optional[str]]:
    """Load monthly history cache and cached_last_update_date from existing coordinator data."""
    monthly_history_cache: Dict[str, MonthCacheEntry] = {}
    cached_last_update_date: Optional[str] = None

    if entry.entry_id in hass.data.get(DOMAIN, {}):
        existing_coordinator = hass.data[DOMAIN][entry.entry_id]
        if existing_coordinator and existing_coordinator.data:
            cache_data = existing_coordinator.data.get("monthly_history_cache", {})
            cached_last_update_date = existing_coordinator.data.get("cached_last_update_date")
            if cache_data:
                converted_cache: Dict[str, MonthCacheEntry] = {}
                for month_key, entry_data in cache_data.items():
                    if isinstance(entry_data, MonthCacheEntry):
                        converted_cache[month_key] = _ensure_month_cache_entry_state(entry_data)
                    elif isinstance(entry_data, dict):
                        try:
                            converted_cache[month_key] = MonthCacheEntry.from_dict(
                                _ensure_dict_cache_entry_state(entry_data)
                            )
                        except Exception as err:
                            _LOGGER.warning("Failed to convert cache entry for %s: %s", month_key, err)
                    else:
                        _LOGGER.warning("Invalid cache entry type for %s: %s", month_key, type(entry_data))
                monthly_history_cache = converted_cache

    return monthly_history_cache, cached_last_update_date


def _extract_last_update_date(last_update: Any) -> Optional[str]:
    """Extract the last update date string from last_update data (dict or str)."""
    if isinstance(last_update, dict):
        return last_update.get("lastSyncDate") or last_update.get("date")
    if isinstance(last_update, str):
        return last_update
    return None


def _snapshot_cache_averages(
    monthly_history_cache: Dict[str, MonthCacheEntry]
) -> Dict[str, Optional[float]]:
    """Take a snapshot of average_usage values from the cache for change detection."""
    snapshot: Dict[str, Optional[float]] = {}
    for k, v in monthly_history_cache.items():
        if isinstance(v, MonthCacheEntry):
            snapshot[k] = v.average_usage
        elif isinstance(v, dict):
            snapshot[k] = v.get("average_usage")
    return snapshot


def _get_or_create_statistics_tracking(
    hass: HomeAssistant,
    entry: ConfigEntry
) -> StatisticsTracking:
    """Get existing StatisticsTracking from coordinator or create a new one."""
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        existing_coordinator = hass.data[DOMAIN][entry.entry_id]
        if existing_coordinator and existing_coordinator.data:
            existing_tracking = existing_coordinator.data.get("statistics_tracking")
            if isinstance(existing_tracking, StatisticsTracking):
                return existing_tracking
    return StatisticsTracking(
        monthly_usage=None,
        last_year_monthly_usage=None,
        average_monthly_usage=None,
        last_year_average_monthly_usage=None,
        total_usage=None
    )


async def _load_or_build_cache(
    api: MijntedApi,
    hass: HomeAssistant,
    entry: ConfigEntry,
    last_update: Any,
    energy_usage_data: Dict[str, Any],
    now: datetime,
) -> Tuple[Dict[str, MonthCacheEntry], bool]:
    """Load cache from coordinator/storage, or build initial. Returns (cache, was_modified)."""
    monthly_history_cache, _ = _load_cache_from_coordinator(hass, entry)

    if not monthly_history_cache:
        persisted_cache = await _load_persisted_cache(hass, entry.entry_id)
        if persisted_cache:
            monthly_history_cache = persisted_cache
            _LOGGER.info("Restored monthly history cache from storage (%d complete months)", len(monthly_history_cache))

    if not monthly_history_cache:
        cache = await _build_initial_monthly_history_cache(
            api, last_update, energy_usage_data, now, existing_cache=monthly_history_cache
        )
        return (cache, True)

    cache_before = len(monthly_history_cache)
    monthly_history_cache = await _build_initial_monthly_history_cache(
        api, last_update, energy_usage_data, now, existing_cache=monthly_history_cache
    )
    was_modified = len(monthly_history_cache) > cache_before
    return (monthly_history_cache, was_modified)


async def _update_and_enrich_cache(
    api: MijntedApi,
    monthly_history_cache: Dict[str, MonthCacheEntry],
    filter_status: List[Dict[str, Any]],
    last_update: Any,
    energy_usage_data: Dict[str, Any],
    last_update_date_changed: bool,
    now: datetime,
) -> bool:
    """Update cache, apply month-boundary lock, enrich averages, and run finalization fallback."""
    modified = False

    if last_update_date_changed:
        try:
            await _update_current_month_cache(
                api, monthly_history_cache, filter_status, last_update, energy_usage_data, now
            )
            modified = True
        except Exception as err:
            _LOGGER.warning(
                "Failed to refresh current month in cache: %s", err,
                extra={"error_type": type(err).__name__}, exc_info=True,
            )

    try:
        boundary_lock_modified = await _lock_current_month_starts_when_previous_complete(
            api, monthly_history_cache, filter_status, last_update, energy_usage_data, now
        )
        if boundary_lock_modified:
            modified = True
    except Exception as err:
        _LOGGER.warning(
            "Failed to lock current month starts from previous-month complete readings: %s",
            err, extra={"error_type": type(err).__name__}, exc_info=True,
        )

    cache_before_enrich = _snapshot_cache_averages(monthly_history_cache)
    await _enrich_cache_with_api_data(api, monthly_history_cache, energy_usage_data, now)
    cache_after_enrich = _snapshot_cache_averages(monthly_history_cache)

    if cache_before_enrich != cache_after_enrich:
        modified = True

    try:
        fallback_recalc_modified = await _recalculate_current_month_starts_if_previous_finalized(
            api, monthly_history_cache, filter_status,
            cache_before_enrich, cache_after_enrich, now,
        )
        if fallback_recalc_modified:
            modified = True
    except Exception as err:
        _LOGGER.warning(
            "Failed to recalculate current month start values after previous month finalization: %s",
            err, extra={"error_type": type(err).__name__}, exc_info=True,
        )

    return modified


async def _ensure_monthly_history_cache(
    api: MijntedApi,
    hass: HomeAssistant,
    entry: ConfigEntry,
    last_update: Any,
    energy_usage_data: Dict[str, Any],
    filter_status: List[Dict[str, Any]],
) -> Tuple[Dict[str, MonthCacheEntry], Optional[str], StatisticsTracking]:
    """Load/build/update/enrich/persist monthly history cache."""
    now = datetime.now()
    current_last_update_date = _extract_last_update_date(last_update)
    _, cached_last_update_date = _load_cache_from_coordinator(hass, entry)
    last_update_date_changed = current_last_update_date != cached_last_update_date

    try:
        monthly_history_cache, cache_was_modified = await _load_or_build_cache(
            api, hass, entry, last_update, energy_usage_data, now
        )
        enrichment_modified = await _update_and_enrich_cache(
            api, monthly_history_cache, filter_status,
            last_update, energy_usage_data, last_update_date_changed, now,
        )
        if cache_was_modified or enrichment_modified:
            try:
                await _save_persisted_cache(hass, entry.entry_id, monthly_history_cache)
            except Exception as err:
                _LOGGER.warning("Failed to persist cache: %s", err)
    except Exception as err:
        _LOGGER.warning(
            "Error in monthly history cache logic: %s", err,
            extra={"error_type": type(err).__name__}, exc_info=True,
        )
        monthly_history_cache = {}

    statistics_tracking = _get_or_create_statistics_tracking(hass, entry)
    return (monthly_history_cache, current_last_update_date, statistics_tracking)


def _build_coordinator_return_dict(
    api: MijntedApi,
    energy_usage_data: Dict[str, Any],
    energy_usage_total: float,
    last_update: Any,
    filter_status: List[Dict[str, Any]],
    usage_insight_data: Dict[str, Any],
    usage_insight_last_year_data: Dict[str, Any],
    active_model: Any,
    delivery_types: List[Any],
    residential_unit_detail_data: Dict[str, Any],
    usage_this_year: Dict[str, Any],
    usage_last_year: Dict[str, Any],
    room_usage: Dict[str, Any],
    unit_of_measures_data: List[Any],
    last_successful_sync: str,
    calculated_history: Dict[str, float],
    current_month_calculated: Optional[float],
    monthly_history_cache: Dict[str, MonthCacheEntry],
    current_last_update_date: Optional[str],
    statistics_tracking: StatisticsTracking,
) -> Dict[str, Any]:
    """Build the coordinator data dictionary returned by async_update_data."""
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
        "cached_last_update_date": current_last_update_date,
        "statistics_tracking": statistics_tracking
    }


def _sync_tokens_to_config(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: MijntedApi
) -> None:
    """Persist API tokens to config entry if they changed after authentication."""
    if (api.refresh_token != entry.data.get("refresh_token") or
        api.access_token != entry.data.get("access_token") or
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


def _calculate_energy_usage_total(energy_usage_data: Dict[str, Any]) -> float:
    """Sum totalEnergyUsage across all months in energy usage data."""
    if not isinstance(energy_usage_data, dict):
        return 0.0
    monthly_usages = energy_usage_data.get("monthlyEnergyUsages", [])
    if not monthly_usages:
        return 0.0
    return sum(
        DataUtil.safe_float(month.get("totalEnergyUsage"), 0.0) or 0.0
        for month in monthly_usages
        if isinstance(month, dict)
    )


def _handle_connection_error(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: MijntedApi,
    err: MijntedConnectionError
) -> Dict[str, Any]:
    """Handle connection error: return cached data if available, otherwise raise UpdateFailed."""
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


def _handle_grant_expired(hass: HomeAssistant, entry: ConfigEntry, err: MijntedGrantExpiredError) -> None:
    """Trigger a reauth flow if the refresh token grant has expired (unless one is already in progress)."""
    _LOGGER.warning(
        "Refresh token grant has expired. Triggering re-authentication flow: %s",
        err,
        extra={"entry_id": entry.entry_id, "error_type": "MijntedGrantExpiredError"},
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
            extra={"entry_id": entry.entry_id},
        )
    raise UpdateFailed(
        "Refresh token has expired. Please re-authenticate using the configuration flow."
    ) from err


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MijnTed from a config entry.
    
    Args:
        hass: Home Assistant instance
        entry: Configuration entry
        
    Returns:
        True if setup was successful, False otherwise
    """
    
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
        username = entry.data.get(CONF_USERNAME)
        password = entry.data.get(CONF_PASSWORD)
        if not username or not password:
            raise MijntedAuthenticationError("Username and password not found in config entry")
        return (username, password)
    
    async def async_update_data() -> Dict[str, Any]:
        """Fetch data from the API and structure it for sensors."""
        refresh_token_expires_at = _parse_refresh_token_expires_at(entry)
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
                _sync_tokens_to_config(hass, entry, api)

                data = await _fetch_and_normalize_api_data(api)
                energy_usage_data = data["energy_usage_data"]
                last_update_data = data["last_update_data"]
                filter_status_data = data["filter_status_data"]
                energy_usage_total = _calculate_energy_usage_total(energy_usage_data)
                last_update = ApiUtil.extract_value(last_update_data, "")
                filter_status = filter_status_data if isinstance(filter_status_data, list) else []
                active_model = ApiUtil.extract_value(data["active_model_data"], None)
                usage_this_year = energy_usage_data if isinstance(energy_usage_data, dict) else {}
                usage_last_year = {}
                room_usage = _build_room_usage(data["usage_per_room_data"])
                last_successful_sync = TimestampUtil.format_datetime_to_timestamp(
                    datetime.now(timezone.utc)
                )
                calculated_history, current_month_calculated = await _compute_anchor_calculations(
                    api, energy_usage_data, filter_status
                )
                monthly_history_cache, current_last_update_date, statistics_tracking = (
                    await _ensure_monthly_history_cache(
                        api, hass, entry, last_update, energy_usage_data, filter_status
                    )
                )
                return _build_coordinator_return_dict(
                    api,
                    energy_usage_data,
                    energy_usage_total,
                    last_update,
                    filter_status,
                    data["usage_insight_data"],
                    data["usage_insight_last_year_data"],
                    active_model,
                    data["delivery_types"],
                    data["residential_unit_detail_data"],
                    usage_this_year,
                    usage_last_year,
                    room_usage,
                    data["unit_of_measures_data"],
                    last_successful_sync,
                    calculated_history,
                    current_month_calculated,
                    monthly_history_cache,
                    current_last_update_date,
                    statistics_tracking
                )
        except MijntedGrantExpiredError as err:
            _handle_grant_expired(hass, entry, err)
        except MijntedAuthenticationError as err:
            _LOGGER.error(
                "Authentication error: %s",
                err,
                extra={"entry_id": entry.entry_id, "error_type": "MijntedAuthenticationError"}
            )
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except MijntedConnectionError as err:
            return _handle_connection_error(hass, entry, api, err)
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

    polling_interval_seconds = entry.data.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL.total_seconds())
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

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "button"])

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload MijnTed config entry.
    
    Args:
        hass: Home Assistant instance
        entry: Configuration entry to unload
        
    Returns:
        True if unload was successful, False otherwise
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "button"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

