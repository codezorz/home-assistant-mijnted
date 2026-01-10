from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime, timezone, time, date
import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.recorder.models import StatisticMetaData, StatisticData, StatisticMeanType
from homeassistant.components.recorder.statistics import async_import_statistics
from ..const import DOMAIN, DEFAULT_START_VALUE, CALCULATION_AVERAGE_PER_DAY_DECIMAL_PLACES, UNIT_MIJNTED
from ..utils import DateUtil, DataUtil
from .models import DeviceReading, CurrentData, HistoryData, StatisticsTracking, MonthCacheEntry

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

    @staticmethod
    def _build_device_info(data: Optional[Dict[str, Any]]) -> DeviceInfo:
        """Build device information from coordinator data.
        
        Args:
            data: Coordinator data dictionary containing residential unit information
            
        Returns:
            DeviceInfo object with device identifiers and details
        """
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
    def device_info(self) -> DeviceInfo:
        """Return device information.
        
        Returns:
            DeviceInfo object with device identifiers and details
        """
        return self._build_device_info(self.coordinator.data)

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
    
    @staticmethod
    def _get_month_cache_entry_dict(entry: Any) -> Optional[Dict[str, Any]]:
        """Convert cache entry to dictionary format.
        
        Args:
            entry: MonthCacheEntry instance or dict
            
        Returns:
            Dictionary representation of the entry, or None if invalid
        """
        if isinstance(entry, MonthCacheEntry):
            return entry.to_dict()
        if isinstance(entry, dict):
            return entry
        return None
    
    @staticmethod
    def _get_devices_from_cache_entry(entry: Any) -> List[Dict[str, Any]]:
        """Extract devices list from a cache entry.
        
        Args:
            entry: MonthCacheEntry instance or dict
            
        Returns:
            List of device dictionaries
        """
        if isinstance(entry, MonthCacheEntry):
            return [device.to_dict() for device in entry.devices]
        if isinstance(entry, dict):
            return entry.get("devices", [])
        return []
    
    @staticmethod
    def _extract_value_from_cache_entry(entry: Any, field_name: str) -> Optional[Any]:
        """Extract a value from a cache entry (MonthCacheEntry or dict).
        
        Args:
            entry: MonthCacheEntry instance or dict
            field_name: Name of the field to extract
            
        Returns:
            Extracted value or None if not found
        """
        if isinstance(entry, MonthCacheEntry):
            return getattr(entry, field_name, None)
        if isinstance(entry, dict):
            return entry.get(field_name)
        return None
    
    def _get_last_successful_sync(self) -> Optional[str]:
        data = self.coordinator.data
        if not data:
            return None
        return data.get("last_successful_sync")
    
    def _update_last_known_value(self, value: Any) -> None:
        if value is not None:
            self._last_known_value = value
    
    def _build_month_id_attributes(self) -> Dict[str, str]:
        attributes: Dict[str, str] = {}
        
        current = self._build_current_data()
        if current:
            current_attributes = current.to_attributes_dict()
            if "month_id" in current_attributes:
                attributes["month_id"] = current_attributes["month_id"]
        
        if "month_id" not in attributes:
            now = datetime.now()
            attributes["month_id"] = f"{now.month}.{now.year}"
        
        current_month_id = attributes.get("month_id", "")
        if current_month_id:
            parsed = DataUtil.parse_month_year(current_month_id)
            if parsed:
                current_month, current_year = parsed
                attributes["last_year_month_id"] = f"{current_month}.{current_year - 1}"
        
        return attributes
    
    def _calculate_usage_from_start_end(
        self,
        total_usage_start: Optional[float],
        total_usage_end: Optional[float],
        month_id: Optional[str]
    ) -> Optional[float]:
        start = DataUtil.safe_float(total_usage_start, DEFAULT_START_VALUE)
        end = DataUtil.safe_float(total_usage_end, DEFAULT_START_VALUE)
        
        if start is None or end is None:
            return None
        
        parsed = DataUtil.parse_month_year(month_id) if month_id else None
        if parsed and parsed[0] == 1:
            return end
        return end - start
    
    def _validate_statistics_injection(self) -> bool:
        if not self.entity_id:
            return False
        if not self.hass:
            return False
        if "recorder" not in self.hass.config.components:
            return False
        return True
    
    def _compare_month_keys(self, month_key1: Optional[str], month_key2: Optional[str]) -> bool:
        if not month_key1 or not month_key2:
            return False
        
        parsed1 = DataUtil.parse_month_year(month_key1)
        parsed2 = DataUtil.parse_month_year(month_key2)
        
        if not parsed1 or not parsed2:
            return False
        
        month1, year1 = parsed1
        month2, year2 = parsed2
        
        if year1 < year2:
            return True
        if year1 > year2:
            return False
        return month1 <= month2
    
    def _get_tracking_field_name(self) -> Optional[str]:
        sensor_type = getattr(self, 'sensor_type', None)
        if not sensor_type:
            return None
        mapping = {
            "monthly_usage": "monthly_usage",
            "last_year_monthly_usage": "last_year_monthly_usage",
            "average_monthly_usage": "average_monthly_usage",
            "last_year_average_monthly_usage": "last_year_average_monthly_usage",
            "total_usage": "total_usage"
        }
        return mapping.get(sensor_type.lower())
    
    def _update_statistics_tracking(self, month_key: str) -> None:
        data = self.coordinator.data if hasattr(self, 'coordinator') else None
        if not data:
            return
        
        statistics_tracking = data.get("statistics_tracking")
        if not isinstance(statistics_tracking, StatisticsTracking):
            return
        
        tracking_field = self._get_tracking_field_name()
        if not tracking_field:
            return
        
        current_value = getattr(statistics_tracking, tracking_field, None)
        
        if current_value is None:
            setattr(statistics_tracking, tracking_field, month_key)
        elif not self._compare_month_keys(month_key, current_value):
            setattr(statistics_tracking, tracking_field, month_key)
    
    async def _has_already_injected_period(self, start_time: datetime) -> bool:
        month_key = f"{start_time.month}.{start_time.year}"
        
        data = self.coordinator.data if hasattr(self, 'coordinator') else None
        if not data:
            return False
        
        statistics_tracking = data.get("statistics_tracking")
        if not isinstance(statistics_tracking, StatisticsTracking):
            return False
        
        tracking_field = self._get_tracking_field_name()
        if not tracking_field:
            return False
        
        last_injected = getattr(statistics_tracking, tracking_field, None)
        if not last_injected:
            return False
        
        return self._compare_month_keys(month_key, last_injected)
    
    def _create_statistics_metadata(self, mean_type: StatisticMeanType, has_sum: bool = False) -> StatisticMetaData:
        """Create statistics metadata for recorder.
        
        Args:
            mean_type: Type of mean calculation for statistics
            has_sum: Whether statistics should include sum values
            
        Returns:
            StatisticMetaData object configured for this sensor
        """
        return StatisticMetaData(
            has_mean=False,
            has_sum=has_sum,
            name=self.name,
            source="recorder",
            statistic_id=self.entity_id,
            unit_of_measurement=UNIT_MIJNTED,
            mean_type=mean_type,
            unit_class=None
        )
    
    def _update_max_month_key(self, stat_time: datetime, max_month_key: Optional[str]) -> Optional[str]:
        month_key = f"{stat_time.month}.{stat_time.year}"
        if not max_month_key or not self._compare_month_keys(month_key, max_month_key):
            return month_key
        return max_month_key
    
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
            self.hass.async_create_task(self._async_inject_statistics())
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass, set up statistics injection if needed."""
        await super().async_added_to_hass()
        if hasattr(self, '_async_inject_statistics'):
            await self._setup_statistics_injection()
    
    async def _add_statistic_if_valid(
        self,
        statistics: List[StatisticData],
        injected_periods: set[str],
        month_id: Optional[str],
        start_date: Optional[str],
        value: Optional[Any],
        max_month_key: Optional[str]
    ) -> Optional[str]:
        if not month_id or month_id in injected_periods:
            return max_month_key
        
        stat_time = self._parse_start_date_to_datetime(start_date) if start_date else None
        if not stat_time:
            return max_month_key
        
        if await self._has_already_injected_period(stat_time):
            injected_periods.add(month_id)
            return max_month_key
        
        usage_value = DataUtil.safe_float(value)
        if usage_value is None:
            return max_month_key
        
        statistics.append(StatisticData(start=stat_time, state=usage_value))
        injected_periods.add(month_id)
        return self._update_max_month_key(stat_time, max_month_key)
    
    async def _finalize_statistics_injection(
        self,
        statistics: List[StatisticData],
        mean_type: StatisticMeanType,
        max_month_key: Optional[str],
        has_sum: bool = False
    ) -> None:
        if not statistics:
            return
        
        metadata = self._create_statistics_metadata(mean_type, has_sum=has_sum)
        await self._async_safe_import_statistics(metadata, statistics)
        
        if max_month_key:
            self._update_statistics_tracking(max_month_key)
    
    async def _async_inject_last_year_statistics(
        self,
        cache_field_name: str,
        current_field_name: str,
        mean_type: StatisticMeanType
    ) -> None:
        if not self._validate_statistics_injection():
            return
        
        data = self.coordinator.data
        if not data:
            return
        
        monthly_history_cache = data.get("monthly_history_cache", {})
        if not isinstance(monthly_history_cache, dict):
            return
        
        history = self._build_history_data()
        current = self._build_current_data()
        
        injected_periods: set[str] = set()
        statistics = []
        max_month_key = None
        
        for entry in history:
            if not entry.month_id:
                continue
            
            parsed = DataUtil.parse_month_year(entry.month_id)
            if not parsed:
                continue
            
            month_num, year = parsed
            last_year = year - 1
            last_year_month_key = DateUtil.format_month_key(last_year, month_num)
            
            last_year_data = monthly_history_cache.get(last_year_month_key)
            if not last_year_data:
                continue
            
            last_year_value = self._extract_value_from_cache_entry(last_year_data, cache_field_name)
            if last_year_value is None:
                continue
            
            last_year_value = DataUtil.safe_float(last_year_value)
            if last_year_value is None:
                continue
            
            max_month_key = await self._add_statistic_if_valid(
                statistics,
                injected_periods,
                entry.month_id,
                entry.start_date,
                last_year_value,
                max_month_key
            )
        
        current_field_value = getattr(current, current_field_name, None) if current else None
        if current and current.month_id and current_field_value is not None:
            max_month_key = await self._add_statistic_if_valid(
                statistics,
                injected_periods,
                current.month_id,
                current.start_date,
                current_field_value,
                max_month_key
            )
        
        await self._finalize_statistics_injection(statistics, mean_type, max_month_key)
    
    async def _build_statistics_from_history(
        self,
        history_field: str,
        mean_type: StatisticMeanType,
        include_current: bool = False,
        current_value_calculator: Optional[Callable[[CurrentData], Optional[float]]] = None
    ) -> None:
        history = self._build_history_data()
        if not history:
            return
        
        if not self._validate_statistics_injection():
            return
        
        injected_periods: set[str] = set()
        statistics = []
        max_month_key = None
        
        for entry in history:
            value = getattr(entry, history_field, None)
            if value is None:
                continue
            max_month_key = await self._add_statistic_if_valid(
                statistics,
                injected_periods,
                entry.month_id,
                entry.start_date,
                value,
                max_month_key
            )
        
        if include_current:
            current = self._build_current_data()
            if current and current.month_id:
                if current_value_calculator:
                    usage_value = current_value_calculator(current)
                else:
                    usage_value = getattr(current, history_field, None)
                
                if usage_value is not None:
                    max_month_key = await self._add_statistic_if_valid(
                        statistics,
                        injected_periods,
                        current.month_id,
                        current.start_date,
                        usage_value,
                        max_month_key
                    )
        
        await self._finalize_statistics_injection(statistics, mean_type, max_month_key)
    
    def _parse_start_date_to_datetime(self, start_date_str: str) -> Optional[datetime]:
        """Parse start date string to datetime object.
        
        Args:
            start_date_str: Date string in "YYYY-MM-DD" format
            
        Returns:
            Datetime object with UTC timezone, or None if parsing fails
        """
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
        prev_month_data = monthly_history_cache.get(prev_month_key)
        
        if isinstance(prev_month_data, MonthCacheEntry):
            return prev_month_data.to_dict()
        return prev_month_data
    
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
        devices_list: List[DeviceReading]
    ) -> Tuple[Optional[float], Optional[float]]:
        if not devices_list:
            return (None, None)
        
        start_values: List[float] = []
        end_values: List[float] = []
        
        for device in devices_list:
            if isinstance(device, DeviceReading):
                if device.start is not None:
                    start_values.append(device.start)
                if device.end is not None:
                    end_values.append(device.end)
            elif isinstance(device, dict):
                start_val = DataUtil.safe_float(device.get("start"))
                if start_val is not None:
                    start_values.append(start_val)
                end_val = DataUtil.safe_float(device.get("end"))
                if end_val is not None:
                    end_values.append(end_val)
        
        total_usage_start = sum(start_values) if start_values else None
        total_usage_end = sum(end_values) if end_values else None
        
        return (total_usage_start, total_usage_end)
    
    @staticmethod
    def _calculate_average_per_day(total_usage: Optional[float], days: Optional[int]) -> Optional[float]:
        if total_usage is None or days is None or days <= 0:
            return None
        
        total_usage_float = DataUtil.safe_float(total_usage)
        if total_usage_float is None:
            return None
        
        try:
            return round(
                total_usage_float / float(days),
                CALCULATION_AVERAGE_PER_DAY_DECIMAL_PLACES
            )
        except (ValueError, TypeError, ZeroDivisionError):
            return None
    
    def _enrich_device_entry(
        self,
        device: Dict[str, Any],
        device_id: Any,
        current_month: int,
        current_year: int,
        monthly_history_cache: Dict[str, Any],
        use_month_transition: bool = False
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(device, dict):
            return None
        
        device_entry = device.copy()
        
        device_id_int = DataUtil.safe_int(device_id)
        if device_id_int is None:
            return None
        device_entry["id"] = device_id_int
        
        if use_month_transition:
            start_value = self._get_device_start_value(
                device,
                device_id,
                current_month,
                current_year,
                monthly_history_cache
            )
        else:
            start_val = device.get("start")
            start_value = DataUtil.safe_float(start_val) if start_val is not None else None
        
        device_entry["start"] = start_value
        
        end_val = device.get("end")
        end_value = DataUtil.safe_float(end_val)
        device_entry["end"] = end_value
        
        if start_value is not None and end_value is not None:
            device_entry["usage"] = end_value - start_value
        else:
            device_entry["usage"] = None
        
        return device_entry
    
    def _convert_dict_to_device_reading(self, device_dict: Dict[str, Any]) -> Optional[DeviceReading]:
        if not isinstance(device_dict, dict):
            return None
        
        device_id = DataUtil.safe_int(device_dict.get("id"))
        if device_id is None:
            return None
        
        start_val = DataUtil.safe_float(device_dict.get("start"))
        end_val = DataUtil.safe_float(device_dict.get("end"))
        
        if start_val is None or end_val is None:
            return None
        
        usage_val = DataUtil.safe_float(device_dict.get("usage"))
        return DeviceReading(
            id=device_id,
            start=start_val,
            end=end_val,
            usage=usage_val
        )
    
    def _enrich_history_device(self, device: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        device_id = device.get("id") if isinstance(device, dict) else None
        return self._enrich_device_entry(
            device,
            device_id,
            0,
            0,
            {},
            use_month_transition=False
        )
    
    def _build_current_data(self) -> Optional[CurrentData]:
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
        
        last_year_usage = self._extract_value_from_cache_entry(prev_year_data, "total_usage")
        last_year_average_usage = self._extract_value_from_cache_entry(prev_year_data, "average_usage")
        
        start_date = DateUtil.get_first_day_of_month(current_month, current_year)
        start_date_str = DateUtil.format_date_for_api(start_date)
        last_day_of_month = DateUtil.get_last_day_of_month(current_month, current_year)
        end_date = min(last_sync_date_obj, last_day_of_month)
        end_date_str = DateUtil.format_date_for_api(end_date)
        last_update_date_str = DateUtil.format_date_for_api(last_sync_date_obj)
        days = DateUtil.calculate_days_between(start_date_str, end_date_str)
        
        devices_dict_list: List[Dict[str, Any]] = []
        
        end_readings_map = DataUtil.extract_device_readings_map(filter_status)
        
        if is_cache_dict and current_month_key in monthly_history_cache:
            current_month_cache = monthly_history_cache[current_month_key]
            cached_devices = self._get_devices_from_cache_entry(current_month_cache)
            
            cached_devices_map: Dict[str, Dict[str, Any]] = {}
            for device in cached_devices:
                if isinstance(device, dict):
                    device_id = device.get("id")
                    if device_id is not None:
                        cached_devices_map[str(device_id)] = device
            
            for device_id_str, end_value in end_readings_map.items():
                cached_device = cached_devices_map.get(device_id_str)
                
                if cached_device:
                    device_dict = cached_device.copy()
                    device_dict["end"] = end_value
                else:
                    device_dict = {
                        "id": device_id_str,
                        "end": end_value
                    }
                
                processed_device = self._enrich_device_entry(
                    device_dict,
                    device_id_str,
                    current_month,
                    current_year,
                    monthly_history_cache,
                    use_month_transition=True
                )
                if processed_device:
                    devices_dict_list.append(processed_device)
        else:
            for device_id_str, end_value in end_readings_map.items():
                device_dict = {
                    "id": device_id_str,
                    "end": end_value
                }
                
                processed_device = self._enrich_device_entry(
                    device_dict,
                    device_id_str,
                    current_month,
                    current_year,
                    monthly_history_cache,
                    use_month_transition=True
                )
                if processed_device:
                    devices_dict_list.append(processed_device)
        
        devices_list: List[DeviceReading] = []
        for device_dict in devices_dict_list:
            device_reading = self._convert_dict_to_device_reading(device_dict)
            if device_reading:
                devices_list.append(device_reading)
        
        if not devices_list and days is None:
            return None
        
        total_usage_start, _ = self._calculate_total_usage(devices_list)
        total_usage_end = DataUtil.calculate_filter_status_total(filter_status)
        
        total_usage = None
        if is_cache_dict and current_month_key in monthly_history_cache:
            current_month_data = monthly_history_cache[current_month_key]
            total_usage = self._extract_value_from_cache_entry(current_month_data, "total_usage")
        
        if total_usage is None and total_usage_start is not None and total_usage_end is not None:
            if total_usage_end < total_usage_start:
                total_usage = total_usage_end
            else:
                total_usage = total_usage_end - total_usage_start
        
        average_usage_per_day = self._calculate_average_per_day(total_usage, days)
        
        return CurrentData(
            last_update_date=last_update_date_str,
            month_id=month_year_key,
            start_date=start_date_str,
            end_date=end_date_str,
            devices=devices_list,
            days=days,
            last_year_usage=last_year_usage,
            last_year_average_usage=last_year_average_usage,
            total_usage_start=total_usage_start,
            total_usage_end=total_usage_end,
            total_usage=total_usage,
            average_usage_per_day=average_usage_per_day
        )
    
    def _build_history_data(self) -> List[HistoryData]:
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
        
        historical_readings_list: List[HistoryData] = []
        
        for month_key in month_keys:
            if current_month_key and month_key == current_month_key:
                continue
            
            month_data = monthly_history_cache[month_key]
            month_data = self._get_month_cache_entry_dict(month_data)
            if not month_data:
                continue
            
            year_value = DataUtil.safe_int(month_data.get("year"))
            month_value = DataUtil.safe_int(month_data.get("month"))
            
            devices_dict_list = month_data.get("devices", [])
            enriched_devices_dict = []
            for device in devices_dict_list:
                enriched_device = self._enrich_history_device(device)
                if enriched_device:
                    enriched_devices_dict.append(enriched_device)
            
            devices_list: List[DeviceReading] = []
            for device_dict in enriched_devices_dict:
                device_reading = self._convert_dict_to_device_reading(device_dict)
                if device_reading:
                    devices_list.append(device_reading)
            
            start_date_str = month_data.get("start_date", "")
            end_date_str = month_data.get("end_date", "")
            days = DateUtil.calculate_days_between(start_date_str, end_date_str)
            
            total_usage = month_data.get("total_usage")
            average_usage_per_day = self._calculate_average_per_day(total_usage, days)
            
            total_usage_start, total_usage_end = self._calculate_total_usage(devices_list)
            
            if year_value is None or month_value is None:
                continue
            
            historical_readings_list.append(HistoryData(
                month_id=month_data.get("month_id", ""),
                year=year_value,
                month=month_value,
                start_date=start_date_str,
                end_date=end_date_str,
                average_usage=month_data.get("average_usage"),
                devices=devices_list,
                days=days,
                average_usage_per_day=average_usage_per_day,
                total_usage_start=total_usage_start,
                total_usage_end=total_usage_end,
                total_usage=total_usage
            ))
        
        return historical_readings_list

