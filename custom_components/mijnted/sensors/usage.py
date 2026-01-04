from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import logging
from homeassistant.components.sensor import SensorStateClass
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.components.recorder.models import StatisticMetaData, StatisticData, StatisticMeanType
from .base import MijnTedSensor
from ..utils import DataUtil, DateUtil
from ..const import UNIT_MIJNTED, DOMAIN, DEFAULT_START_VALUE, ENTITY_REGISTRATION_DELAY_SECONDS

_LOGGER = logging.getLogger(__name__)


class MijnTedMonthlyUsageSensor(MijnTedSensor):
    """Sensor for monthly usage extracted from coordinator data."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the monthly usage sensor."""
        super().__init__(coordinator, "monthly_usage", "monthly usage")
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_suggested_display_precision = 0
        self._injected_periods: set[str] = set()

    @property
    def state(self) -> Optional[float]:
        """Return the state calculated from current data."""
        current = self._build_current_data()
        if not current:
            return self._last_known_value
        
        last_update_date = current.get("last_update_date", "")
        if not last_update_date:
            return self._last_known_value
        
        total_usage_start = current.get("total_usage_start", 0)
        total_usage_end = current.get("total_usage_end", 0)
        current_month = current.get("month_id", "")
        
        try:
            start = float(total_usage_start) if total_usage_start is not None else DEFAULT_START_VALUE
            end = float(total_usage_end) if total_usage_end is not None else DEFAULT_START_VALUE
            
            parsed = DataUtil.parse_month_year(current_month) if current_month else None
            if parsed and parsed[0] == 1:
                value = end
            else:
                value = end - start
            
            self._update_last_known_value(value)
            return value
        except (ValueError, TypeError):
            pass
        
        return self._last_known_value

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL

    async def _async_inject_statistics(self) -> None:
        """Inject statistics for monthly usage - inject each month's total usage value."""
        history = self._build_history_data()
        if not history:
            return
        
        if not self._validate_statistics_injection():
            return
        
        statistics = []
        
        for entry in history:
            total_usage = entry.get("total_usage")
            if total_usage is None:
                continue
            
            start_date = entry.get("start_date", "")
            month_id = entry.get("month_id", "")
            
            if month_id in self._injected_periods:
                continue
            
            stat_time = self._parse_start_date_to_datetime(start_date)
            if not stat_time:
                continue
            
            try:
                usage_value = float(total_usage)
            except (ValueError, TypeError):
                continue
            
            statistics.append(
                StatisticData(
                    start=stat_time,
                    state=usage_value
                )
            )
            self._injected_periods.add(month_id)
        
        current = self._build_current_data()
        if current:
            current_month_id = current.get("month_id", "")
            if current_month_id and current_month_id not in self._injected_periods:
                total_usage_start = current.get("total_usage_start", 0)
                total_usage_end = current.get("total_usage_end", 0)
                start_date = current.get("start_date", "")
                
                try:
                    start = float(total_usage_start) if total_usage_start is not None else DEFAULT_START_VALUE
                    end = float(total_usage_end) if total_usage_end is not None else DEFAULT_START_VALUE
                    
                    parsed = DataUtil.parse_month_year(current_month_id) if current_month_id else None
                    if parsed and parsed[0] == 1:
                        usage_value = end
                    else:
                        usage_value = end - start
                    
                    stat_time = self._parse_start_date_to_datetime(start_date)
                    if stat_time:
                        statistics.append(
                            StatisticData(
                                start=stat_time,
                                state=usage_value
                            )
                        )
                        self._injected_periods.add(current_month_id)
                except (ValueError, TypeError):
                    pass
        
        if not statistics:
            return
        
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=False,
            name=self.name,
            source="recorder",
            statistic_id=self.entity_id,
            unit_of_measurement=UNIT_MIJNTED,
            mean_type=StatisticMeanType.NONE,
            unit_class=None
        )
        
        await self._async_safe_import_statistics(metadata, statistics)
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass, set up statistics injection."""
        await super().async_added_to_hass()
        await self._setup_statistics_injection()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        attributes: Dict[str, Any] = {}
        
        current = self._build_current_data()
        if current:
            month_year = current.get("month_id", "")
            if month_year:
                attributes["month_id"] = month_year
            
            start_date = current.get("start_date")
            if start_date:
                attributes["start_date"] = start_date
            
            end_date = current.get("end_date")
            if end_date:
                attributes["end_date"] = end_date
            
            days = current.get("days")
            if days is not None:
                attributes["days"] = days
        
        return attributes


class MijnTedLastYearMonthlyUsageSensor(MijnTedSensor):
    """Sensor for last year's monthly usage extracted from coordinator data."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the last year monthly usage sensor."""
        super().__init__(coordinator, "last_year_monthly_usage", "last year monthly usage")
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_suggested_display_precision = 0
        self._injected_periods: set[str] = set()

    @property
    def state(self) -> Optional[float]:
        """Return the last year usage for the current month's corresponding month from last year."""
        current = self._build_current_data()
        if current:
            last_year_usage = current.get("last_year_usage")
            if last_year_usage is not None:
                try:
                    value = float(last_year_usage)
                    self._update_last_known_value(value)
                    return value
                except (ValueError, TypeError):
                    pass
        
        return self._last_known_value

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL

    async def _async_inject_statistics(self) -> None:
        """Inject statistics for current month's last year data (single data point)."""
        current = self._build_current_data()
        if not current:
            return
        
        last_year_usage = current.get("last_year_usage")
        if last_year_usage is None:
            return
        
        current_month_id = current.get("month_id", "")
        if current_month_id in self._injected_periods:
            return
        
        start_date = current.get("start_date", "")
        if not start_date:
            return
        
        stat_time = self._parse_start_date_to_datetime(start_date)
        if not stat_time:
            return
        
        try:
            usage_value = float(last_year_usage)
        except (ValueError, TypeError):
            return
        
        if not self._validate_statistics_injection():
            return
        
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=False,
            name=self.name,
            source="recorder",
            statistic_id=self.entity_id,
            unit_of_measurement=UNIT_MIJNTED,
            mean_type=StatisticMeanType.NONE,
            unit_class=None
        )
        
        statistics = [
            StatisticData(
                start=stat_time,
                state=usage_value
            )
        ]
        
        await self._async_safe_import_statistics(metadata, statistics)
        self._injected_periods.add(current_month_id)
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass, set up statistics injection."""
        await super().async_added_to_hass()
        await self._setup_statistics_injection()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        attributes: Dict[str, Any] = {}
        
        current = self._build_current_data()
        if current:
            month_year = current.get("month_id", "")
            if month_year:
                attributes["month_id"] = month_year
        
        if "month_id" not in attributes:
            now = datetime.now()
            attributes["month_id"] = f"{now.month}.{now.year}"
        
        current_month_id = attributes.get("month_id", "")
        if current_month_id:
            parsed = DataUtil.parse_month_year(current_month_id)
            if parsed:
                current_month, current_year = parsed
                last_year_month_id = f"{current_month}.{current_year - 1}"
                attributes["last_year_month_id"] = last_year_month_id
        
        return attributes


class MijnTedAverageMonthlyUsageSensor(MijnTedSensor):
    """Sensor for average monthly usage extracted from coordinator history data."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the average monthly usage sensor."""
        super().__init__(coordinator, "average_monthly_usage", "average monthly usage")
        self._attr_icon = "mdi:chart-line"
        self._attr_suggested_display_precision = 0
        self._injected_periods: set[str] = set()

    @property
    def state(self) -> Optional[float]:
        """Return the latest available average from history."""
        history = self._build_history_data()
        
        for entry in history:
            avg_usage = entry.get("average_usage")
            if avg_usage is not None:
                try:
                    return float(avg_usage)
                except (ValueError, TypeError):
                    continue
        
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.MEASUREMENT

    async def _async_inject_statistics(self) -> None:
        """Inject statistics with period-end dates from history."""
        history = self._build_history_data()
        if not history:
            return
        
        if not self._validate_statistics_injection():
            return
        
        statistics = []
        
        for entry in history:
            avg_usage = entry.get("average_usage")
            if avg_usage is None:
                continue
            
            start_date = entry.get("start_date", "")
            month_id = entry.get("month_id", "")
            
            if month_id in self._injected_periods:
                continue
            
            stat_time = self._parse_start_date_to_datetime(start_date)
            if not stat_time:
                continue
            
            try:
                avg_value = float(avg_usage)
            except (ValueError, TypeError):
                continue
            
            statistics.append(
                StatisticData(
                    start=stat_time,
                    state=avg_value
                )
            )
            self._injected_periods.add(month_id)
        
        if not statistics:
            return
        
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=False,
            name=self.name,
            source="recorder",
            statistic_id=self.entity_id,
            unit_of_measurement=UNIT_MIJNTED,
            mean_type=StatisticMeanType.ARITHMETIC,
            unit_class=None
        )
        
        await self._async_safe_import_statistics(metadata, statistics)
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass, set up statistics injection."""
        await super().async_added_to_hass()
        await self._setup_statistics_injection()
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        attributes: Dict[str, Any] = {}
        
        history = self._build_history_data()
        if history:
            for entry in history:
                avg_usage = entry.get("average_usage")
                if avg_usage is not None:
                    month_id = entry.get("month_id", "")
                    if month_id:
                        attributes["month_id"] = month_id
                    break
        
        return attributes


class MijnTedLastYearAverageMonthlyUsageSensor(MijnTedSensor):
    """Sensor for last year's average monthly usage extracted from coordinator data."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the last year average monthly usage sensor."""
        super().__init__(coordinator, "last_year_average_monthly_usage", "last year average monthly usage")
        self._attr_icon = "mdi:chart-line-variant"
        self._attr_suggested_display_precision = 0
        self._injected_periods: set[str] = set()

    @property
    def state(self) -> Optional[float]:
        """Return the last year average usage for the current month's corresponding month from last year."""
        current = self._build_current_data()
        if current:
            last_year_average_usage = current.get("last_year_average_usage")
            if last_year_average_usage is not None:
                try:
                    value = float(last_year_average_usage)
                    self._update_last_known_value(value)
                    return value
                except (ValueError, TypeError):
                    pass
        
        return self._last_known_value

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.MEASUREMENT

    async def _async_inject_statistics(self) -> None:
        """Inject statistics for current month's last year average data (single data point)."""
        current = self._build_current_data()
        if not current:
            return
        
        last_year_average_usage = current.get("last_year_average_usage")
        if last_year_average_usage is None:
            return
        
        current_month_id = current.get("month_id", "")
        if current_month_id in self._injected_periods:
            return
        
        start_date = current.get("start_date", "")
        if not start_date:
            return
        
        stat_time = self._parse_start_date_to_datetime(start_date)
        if not stat_time:
            return
        
        try:
            avg_value = float(last_year_average_usage)
        except (ValueError, TypeError):
            return
        
        if not self._validate_statistics_injection():
            return
        
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=False,
            name=self.name,
            source="recorder",
            statistic_id=self.entity_id,
            unit_of_measurement=UNIT_MIJNTED,
            mean_type=StatisticMeanType.ARITHMETIC,
            unit_class=None
        )
        
        statistics = [
            StatisticData(
                start=stat_time,
                state=avg_value
            )
        ]
        
        await self._async_safe_import_statistics(metadata, statistics)
        self._injected_periods.add(current_month_id)
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass, set up statistics injection."""
        await super().async_added_to_hass()
        await self._setup_statistics_injection()
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        attributes: Dict[str, Any] = {}
        
        current = self._build_current_data()
        if current:
            month_year = current.get("month_id", "")
            if month_year:
                attributes["month_id"] = month_year
        
        if "month_id" not in attributes:
            now = datetime.now()
            attributes["month_id"] = f"{now.month}.{now.year}"
        
        current_month_id = attributes.get("month_id", "")
        if current_month_id:
            parsed = DataUtil.parse_month_year(current_month_id)
            if parsed:
                current_month, current_year = parsed
                last_year_month_id = f"{current_month}.{current_year - 1}"
                attributes["last_year_month_id"] = last_year_month_id
        
        return attributes


class MijnTedTotalUsageSensor(MijnTedSensor):
    """Sensor for total device readings from all devices."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the total usage sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "total_usage", "total usage")
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_suggested_display_precision = 0
        self._injected_periods: set[str] = set()

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor.
        
        Returns:
            Sum of all device readings, or last known value if unavailable
        """
        data = self.coordinator.data
        if not data:
            return self._last_known_value
        
        filter_status = data.get('filter_status')
        total = DataUtil.calculate_filter_status_total(filter_status)
        if total is not None:
            self._update_last_known_value(total)
            return total
        
        return self._last_known_value

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant
        """
        return UNIT_MIJNTED
    
    async def _async_inject_statistics(self) -> None:
        """Inject statistics into Home Assistant recorder for history graphs."""
        history = self._build_history_data()
        if not history:
            return
        
        if not self._validate_statistics_injection():
            return
        
        entries_to_inject = []
        for entry in history:
            total_usage_end = entry.get("total_usage_end")
            if total_usage_end is None:
                continue
            
            start_date = entry.get("start_date", "")
            month_id = entry.get("month_id", "")
            
            if not start_date or not month_id:
                continue
            
            if month_id in self._injected_periods:
                continue
            
            stat_time = self._parse_start_date_to_datetime(start_date)
            if not stat_time:
                continue
            
            try:
                usage_value = float(total_usage_end)
            except (ValueError, TypeError):
                continue
            
            month_num = entry.get("month")
            if not isinstance(month_num, int):
                try:
                    parsed = DataUtil.parse_month_year(month_id)
                    if parsed:
                        month_num = parsed[0]
                    else:
                        month_num = None
                except (ValueError, TypeError):
                    month_num = None
            
            entries_to_inject.append({
                "stat_time": stat_time,
                "state": usage_value,
                "month_id": month_id,
                "month": month_num
            })
        
        if not entries_to_inject:
            return
        
        entries_to_inject.sort(key=lambda x: x["stat_time"])
        
        cumulative_sum = DEFAULT_START_VALUE
        previous_total_usage_end = None
        statistics = []
        
        for entry in entries_to_inject:
            current_total_usage_end = entry["state"]
            
            if entry["month"] == 1:
                delta = current_total_usage_end
            elif previous_total_usage_end is not None:
                delta = current_total_usage_end - previous_total_usage_end
            else:
                delta = current_total_usage_end
            
            cumulative_sum += delta
            
            statistics.append(
                StatisticData(
                    start=entry["stat_time"],
                    state=current_total_usage_end,
                    sum=cumulative_sum
                )
            )
            self._injected_periods.add(entry["month_id"])
            previous_total_usage_end = current_total_usage_end
        
        if not statistics:
            return
        
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name=self.name,
            source="recorder",
            statistic_id=self.entity_id,
            unit_of_measurement=UNIT_MIJNTED,
            mean_type=StatisticMeanType.NONE,
            unit_class=None
        )
        
        await self._async_safe_import_statistics(metadata, statistics)
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass, set up statistics injection."""
        await super().async_added_to_hass()
        await self._setup_statistics_injection()
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        attributes: Dict[str, Any] = {}
        
        current_readings_dict = self._build_current_data()
        historical_readings_list = self._build_history_data()
        
        if current_readings_dict is not None:
            attributes["current"] = current_readings_dict
        if historical_readings_list:
            attributes["history"] = historical_readings_list
        
        return attributes

