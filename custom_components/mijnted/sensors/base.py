from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, time, date
import asyncio
import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.recorder.models import StatisticMetaData, StatisticData
from homeassistant.components.recorder.statistics import async_import_statistics
from ..const import DOMAIN, DEFAULT_START_VALUE, CALCULATION_AVERAGE_PER_DAY_DECIMAL_PLACES, ENTITY_REGISTRATION_DELAY_SECONDS
from ..utils import DateUtil, DataUtil

_LOGGER = logging.getLogger(__name__)


class MijnTedSensor(CoordinatorEntity, SensorEntity):
    """Base class for Mijnted sensors."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]], sensor_type: str, name: str) -> None:
        """Initialize the sensor.
        
        Args:
            coordinator: Data update coordinator
            sensor_type: Type identifier for the sensor
            name: Display name for the sensor
        """
        super().__init__(coordinator)
        self.sensor_type = sensor_type
        self._name = name
        self._attr_unique_id = f"{DOMAIN}_{sensor_type.lower()}"
        self._last_known_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information.
        
        Returns:
            DeviceInfo object with device identifiers and details
        """
        data = self.coordinator.data
        if not data:
            return DeviceInfo(
                identifiers={(DOMAIN, "unknown")},
                name="MijnTed",
                manufacturer="MijnTed",
                model="Unknown",
            )
        
        residential_unit = data.get("residential_unit", "unknown")
        
        residential_unit_detail = data.get("residential_unit_detail", {})
        device_name = "MijnTed"
        
        if isinstance(residential_unit_detail, dict):
            street = residential_unit_detail.get("street", "")
            appartment_no = residential_unit_detail.get("appartmentNo", "")
            zip_code = residential_unit_detail.get("zipCode", "")
            
            address_parts = []
            if street:
                if appartment_no:
                    address_parts.append(f"{street} {appartment_no}")
                else:
                    address_parts.append(street)
            elif appartment_no:
                address_parts.append(appartment_no)
            
            if zip_code:
                address_parts.append(zip_code)
            
            if address_parts:
                device_name = f"MijnTed - {', '.join(address_parts)}"
        
        return DeviceInfo(
            identifiers={(DOMAIN, residential_unit)},
            name=device_name,
            manufacturer="MijnTed",
            model=data.get("active_model", "Unknown"),
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor.
        
        Returns:
            Formatted sensor name with "MijnTed" prefix
        """
        return f"MijnTed {self._name}"
    
    @property
    def available(self) -> bool:
        """Return True if sensor has fresh data from coordinator.
        
        Returns:
            True if coordinator last update was successful, False otherwise
        """
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
        )
    
    def _get_last_successful_sync(self) -> Optional[str]:
        data = self.coordinator.data
        if not data:
            return None
        return data.get("last_successful_sync")
    
    def _update_last_known_value(self, value: Any) -> None:
        if value is not None:
            self._last_known_value = value
    
    def _validate_statistics_injection(self) -> bool:
        if not self.entity_id:
            return False
        if not self.hass:
            return False
        if "recorder" not in self.hass.config.components:
            return False
        return True
    
    async def _async_safe_import_statistics(
        self,
        metadata: StatisticMetaData,
        statistics: List[StatisticData]
    ) -> None:
        if not statistics:
            return
        
        try:
            result = async_import_statistics(self.hass, metadata, statistics)
            
            if result is not None:
                await result
            
            _LOGGER.info(
                "Successfully injected statistics for %s: %d entries",
                self.entity_id,
                len(statistics)
            )
        except Exception as err:
            _LOGGER.warning(
                "Failed to inject statistics for %s: %s (stat may not be available yet, will retry next time)",
                self.entity_id,
                err
            )
    
    async def _setup_statistics_injection(self) -> None:
        def _inject_on_update() -> None:
            if self.hass and self.coordinator.data:
                self.hass.async_create_task(self._async_inject_statistics())
        
        self.async_on_remove(
            self.coordinator.async_add_listener(_inject_on_update)
        )
        
        if self.coordinator.data:
            async def _delayed_inject() -> None:
                await asyncio.sleep(ENTITY_REGISTRATION_DELAY_SECONDS)
                await self._async_inject_statistics()
            self.hass.async_create_task(_delayed_inject())
    
    def _parse_start_date_to_datetime(self, start_date_str: str) -> Optional[datetime]:
        if not start_date_str:
            return None
        
        try:
            date_obj = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            dt = datetime.combine(date_obj, time(0, 0, 0))
            return dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError, AttributeError):
            return None
    
    def _get_month_context(self, last_sync_date_obj: date) -> Dict[str, Any]:
        current_month = last_sync_date_obj.month
        current_year = last_sync_date_obj.year
        month_year_key = f"{current_month}.{current_year}"
        current_month_key = DateUtil.format_month_key(current_year, current_month)
        prev_year = current_year - 1
        prev_month_key = DateUtil.format_month_key(prev_year, current_month)
        
        return {
            "current_month": current_month,
            "current_year": current_year,
            "month_year_key": month_year_key,
            "current_month_key": current_month_key,
            "prev_month_key": prev_month_key,
            "prev_year": prev_year
        }
    
    def _get_previous_month_data(
        self,
        monthly_history_cache: Dict[str, Any],
        current_month: int,
        current_year: int
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(monthly_history_cache, dict):
            return None
        
        prev_month, prev_year = DateUtil.get_previous_month_from_date(
            date(current_year, current_month, 1)
        )
        prev_month_key = DateUtil.format_month_key(prev_year, prev_month)
        return monthly_history_cache.get(prev_month_key)
    
    def _get_device_start_value(
        self,
        device: Dict[str, Any],
        device_id: Any,
        current_month: int,
        current_year: int,
        monthly_history_cache: Dict[str, Any]
    ) -> Optional[float]:
        start_val = device.get("start")
        
        if start_val is not None:
            converted = DataUtil.safe_float(start_val)
            if converted is not None:
                return converted
            if current_month == 1:
                return DEFAULT_START_VALUE
            return None
        
        if current_month == 1:
            return DEFAULT_START_VALUE
        
        prev_month_data = self._get_previous_month_data(
            monthly_history_cache,
            current_month,
            current_year
        )
        
        if prev_month_data and isinstance(prev_month_data, dict):
            prev_devices = prev_month_data.get("devices", [])
            for prev_device in prev_devices:
                if not isinstance(prev_device, dict):
                    continue
                if str(prev_device.get("id")) == str(device_id):
                    prev_end = prev_device.get("end")
                    if prev_end is not None:
                        converted = DataUtil.safe_float(prev_end)
                        if converted is not None:
                            return converted
                    break
        
        return DEFAULT_START_VALUE
    
    def _calculate_total_usage(
        self,
        devices_list: List[Dict[str, Any]]
    ) -> Tuple[Optional[float], Optional[float]]:
        if not devices_list:
            return (None, None)
        
        start_values: List[float] = []
        end_values: List[float] = []
        
        for device in devices_list:
            if not isinstance(device, dict):
                continue
            
            start_val = DataUtil.safe_float(device.get("start"))
            if start_val is not None:
                start_values.append(start_val)
            
            end_val = DataUtil.safe_float(device.get("end"))
            if end_val is not None:
                end_values.append(end_val)
        
        total_usage_start = sum(start_values) if start_values else None
        total_usage_end = sum(end_values) if end_values else None
        
        return (total_usage_start, total_usage_end)
    
    def _process_device_entry(
        self,
        device: Dict[str, Any],
        device_id: Any,
        current_month: int,
        current_year: int,
        monthly_history_cache: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(device, dict):
            return None
        
        device_entry = device.copy()
        
        device_id_int = DataUtil.safe_int(device_id)
        if device_id_int is None:
            return None
        device_entry["id"] = device_id_int
        
        start_value = self._get_device_start_value(
            device,
            device_id,
            current_month,
            current_year,
            monthly_history_cache
        )
        device_entry["start"] = start_value
        
        end_val = device.get("end")
        end_value = DataUtil.safe_float(end_val)
        device_entry["end"] = end_value
        
        if start_value is not None and end_value is not None:
            device_entry["usage"] = end_value - start_value
        else:
            device_entry["usage"] = None
        
        return device_entry
    
    def _enrich_history_device(self, device: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(device, dict):
            return None
        
        device_entry = device.copy()
        device_id = device_entry.get("id")
        
        device_id_int = DataUtil.safe_int(device_id)
        if device_id_int is None:
            return None
        device_entry["id"] = device_id_int
        
        start_val = device.get("start")
        end_val = device.get("end")
        
        if start_val is not None and end_val is not None:
            start_float = DataUtil.safe_float(start_val)
            end_float = DataUtil.safe_float(end_val)
            if start_float is not None and end_float is not None:
                device_entry["usage"] = end_float - start_float
            else:
                device_entry["usage"] = None
        else:
            device_entry["usage"] = None
        
        return device_entry
    
    def _build_current_data(self) -> Optional[Dict[str, Any]]:
        data = self.coordinator.data
        if not data:
            return None
        
        filter_status = data.get('filter_status')
        if not isinstance(filter_status, list):
            return None
        
        last_update = data.get("last_update")
        last_sync_date_obj = DateUtil.parse_last_sync_date(last_update)
        if not last_sync_date_obj:
            return None
        
        month_context = self._get_month_context(last_sync_date_obj)
        current_month = month_context["current_month"]
        current_year = month_context["current_year"]
        month_year_key = month_context["month_year_key"]
        current_month_key = month_context["current_month_key"]
        prev_month_key = month_context["prev_month_key"]
        
        monthly_history_cache = data.get("monthly_history_cache", {})
        is_cache_dict = isinstance(monthly_history_cache, dict)
        
        prev_year_data = None
        if is_cache_dict:
            prev_year_data = monthly_history_cache.get(prev_month_key)
        
        last_year_usage = None
        last_year_average_usage = None
        if isinstance(prev_year_data, dict):
            last_year_usage = prev_year_data.get("total_usage")
            last_year_average_usage = prev_year_data.get("average_usage")
        
        start_date = DateUtil.get_first_day_of_month(current_month, current_year)
        start_date_str = DateUtil.format_date_for_api(start_date)
        last_day_of_month = DateUtil.get_last_day_of_month(current_month, current_year)
        end_date = min(last_sync_date_obj, last_day_of_month)
        end_date_str = DateUtil.format_date_for_api(end_date)
        last_update_date_str = DateUtil.format_date_for_api(last_sync_date_obj)
        days = DateUtil.calculate_days_between(start_date_str, end_date_str)
        
        devices_list: List[Dict[str, Any]] = []
        
        if is_cache_dict and current_month_key in monthly_history_cache:
            cached_devices = monthly_history_cache[current_month_key].get("devices", [])
            for device in cached_devices:
                device_id = device.get("id") if isinstance(device, dict) else None
                if device_id is None:
                    continue
                
                processed_device = self._process_device_entry(
                    device,
                    device_id,
                    current_month,
                    current_year,
                    monthly_history_cache
                )
                if processed_device:
                    devices_list.append(processed_device)
        else:
            end_readings_map = DataUtil.extract_device_readings_map(filter_status)
            
            for device_id_str, end_value in end_readings_map.items():
                device_dict = {
                    "id": device_id_str,
                    "end": end_value
                }
                
                processed_device = self._process_device_entry(
                    device_dict,
                    device_id_str,
                    current_month,
                    current_year,
                    monthly_history_cache
                )
                if processed_device:
                    devices_list.append(processed_device)
        
        if not devices_list and days is None:
            return None
        
        total_usage_start, total_usage_end = self._calculate_total_usage(devices_list)
        
        total_usage = None
        if is_cache_dict and current_month_key in monthly_history_cache:
            current_month_data = monthly_history_cache[current_month_key]
            if isinstance(current_month_data, dict):
                total_usage = current_month_data.get("total_usage")
        
        current_readings_dict: Dict[str, Any] = {
            "last_update_date": last_update_date_str,
            "month_id": month_year_key,
            "start_date": start_date_str,
            "end_date": end_date_str,
            "devices": devices_list
        }
        
        if days is not None:
            current_readings_dict["days"] = days
        if last_year_usage is not None:
            current_readings_dict["last_year_usage"] = last_year_usage
        if last_year_average_usage is not None:
            current_readings_dict["last_year_average_usage"] = last_year_average_usage
        if total_usage_start is not None:
            current_readings_dict["total_usage_start"] = total_usage_start
        if total_usage_end is not None:
            current_readings_dict["total_usage_end"] = total_usage_end
        if total_usage is not None:
            current_readings_dict["total_usage"] = total_usage
        
        return current_readings_dict
    
    def _build_history_data(self) -> List[Dict[str, Any]]:
        data = self.coordinator.data
        if not data:
            return []
        
        monthly_history_cache = data.get("monthly_history_cache", {})
        if not isinstance(monthly_history_cache, dict) or not monthly_history_cache:
            return []
        
        last_update = data.get("last_update")
        last_sync_date_obj = DateUtil.parse_last_sync_date(last_update)
        current_month_key = None
        if last_sync_date_obj:
            month_context = self._get_month_context(last_sync_date_obj)
            current_month_key = month_context["current_month_key"]
        
        def sort_key_func(key: str) -> Tuple[int, int]:
            try:
                parts = key.split("-")
                if len(parts) == 2:
                    return (int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                pass
            return (0, 0)
        
        month_keys = list(monthly_history_cache.keys())
        month_keys.sort(key=sort_key_func, reverse=True)
        
        historical_readings_list: List[Dict[str, Any]] = []
        
        for month_key in month_keys:
            if current_month_key and month_key == current_month_key:
                continue
            
            month_data = monthly_history_cache[month_key]
            if not isinstance(month_data, dict):
                continue
            
            year_value = DataUtil.safe_int(month_data.get("year"))
            month_value = DataUtil.safe_int(month_data.get("month"))
            
            devices_list = month_data.get("devices", [])
            enriched_devices = []
            for device in devices_list:
                enriched_device = self._enrich_history_device(device)
                if enriched_device:
                    enriched_devices.append(enriched_device)
            
            start_date_str = month_data.get("start_date", "")
            end_date_str = month_data.get("end_date", "")
            days = DateUtil.calculate_days_between(start_date_str, end_date_str)
            
            total_usage = month_data.get("total_usage")
            average_usage_per_day = None
            if total_usage is not None and days is not None and days > 0:
                total_usage_float = DataUtil.safe_float(total_usage)
                if total_usage_float is not None:
                    try:
                        average_usage_per_day = round(
                            total_usage_float / float(days),
                            CALCULATION_AVERAGE_PER_DAY_DECIMAL_PLACES
                        )
                    except (ValueError, TypeError, ZeroDivisionError):
                        pass
            
            total_usage_start, total_usage_end = self._calculate_total_usage(enriched_devices)
            
            month_entry: Dict[str, Any] = {
                "month_id": month_data.get("month_id", ""),
                "year": year_value,
                "month": month_value,
                "start_date": start_date_str,
                "end_date": end_date_str,
                "average_usage": month_data.get("average_usage"),
                "devices": enriched_devices
            }
            
            if days is not None:
                month_entry["days"] = days
            if average_usage_per_day is not None:
                month_entry["average_usage_per_day"] = average_usage_per_day
            if total_usage_start is not None:
                month_entry["total_usage_start"] = total_usage_start
            if total_usage_end is not None:
                month_entry["total_usage_end"] = total_usage_end
            if total_usage is not None:
                month_entry["total_usage"] = total_usage
            
            historical_readings_list.append(month_entry)
        
        return historical_readings_list

