from typing import Any, Dict, Optional
from homeassistant.components.sensor import SensorStateClass
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.components.recorder.models import StatisticData, StatisticMeanType
from .base import MijnTedSensor
from ..utils import DataUtil
from ..const import UNIT_MIJNTED, DEFAULT_START_VALUE
from .models import CurrentData


class MijnTedMonthlyUsageSensor(MijnTedSensor):
    """Sensor for monthly usage extracted from coordinator data."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the monthly usage sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "monthly_usage", "monthly usage")
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_suggested_display_precision = 0

    @property
    def state(self) -> Optional[float]:
        """Return the state calculated from current data.
        
        Returns:
            Monthly usage value, or last known value if unavailable
        """
        current = self._build_current_data()
        if not current:
            return self._last_known_value
        
        if not current.last_update_date:
            return self._last_known_value
        
        value = self._calculate_usage_from_start_end(
            current.total_usage_start,
            current.total_usage_end,
            current.month_id
        )
        
        if value is None and current.total_usage is not None:
            value = DataUtil.safe_float(current.total_usage)
        
        if value is None:
            return self._last_known_value
        
        self._update_last_known_value(value)
        return value

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant
        """
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class.
        
        Returns:
            SensorStateClass.TOTAL for cumulative measurements
        """
        return SensorStateClass.TOTAL

    async def _async_inject_statistics(self) -> None:
        def calculate_current_value(current: CurrentData) -> Optional[float]:
            return self._calculate_usage_from_start_end(
                current.total_usage_start,
                current.total_usage_end,
                current.month_id
            )
        
        await self._build_statistics_from_history(
            "total_usage",
            StatisticMeanType.NONE,
            include_current=True,
            current_value_calculator=calculate_current_value
        )
    

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing current data attributes
        """
        current = self._build_current_data()
        if current:
            return current.to_attributes_dict()
        return {}


class MijnTedLastYearMonthlyUsageSensor(MijnTedSensor):
    """Sensor for last year's monthly usage extracted from coordinator data."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the last year monthly usage sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "last_year_monthly_usage", "last year monthly usage")
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_suggested_display_precision = 0

    @property
    def state(self) -> Optional[float]:
        """Return the last year usage for the current month's corresponding month from last year.
        
        Returns:
            Last year's monthly usage value, or last known value if unavailable
        """
        current = self._build_current_data()
        if current:
            last_year_usage = current.last_year_usage
            if last_year_usage is not None:
                value = DataUtil.safe_float(last_year_usage)
                if value is not None:
                    self._update_last_known_value(value)
                    return value
        
        return self._last_known_value

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant
        """
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class.
        
        Returns:
            SensorStateClass.TOTAL for cumulative measurements
        """
        return SensorStateClass.TOTAL

    async def _async_inject_statistics(self) -> None:
        await self._async_inject_last_year_statistics("total_usage", "last_year_usage", StatisticMeanType.NONE)
    

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing month_id and last_year_month_id attributes
        """
        return self._build_month_id_attributes()


class MijnTedAverageMonthlyUsageSensor(MijnTedSensor):
    """Sensor for average monthly usage extracted from coordinator history data."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the average monthly usage sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "average_monthly_usage", "average monthly usage")
        self._attr_icon = "mdi:chart-line"
        self._attr_suggested_display_precision = 0

    @property
    def state(self) -> Optional[float]:
        """Return the latest available average from history, skipping current month if average is None.
        
        Returns:
            Average monthly usage value, or None if not available
        """
        history = self._build_history_data()
        current = self._build_current_data()
        
        current_month_id = current.month_id if current else None
        
        for entry in history:
            avg_usage = entry.average_usage
            if avg_usage is not None:
                value = DataUtil.safe_float(avg_usage)
                if value is not None:
                    return value
        
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant
        """
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class.
        
        Returns:
            SensorStateClass.TOTAL for historical tracking
        """
        return SensorStateClass.TOTAL

    async def _async_inject_statistics(self) -> None:
        await self._build_statistics_from_history(
            "average_usage",
            StatisticMeanType.ARITHMETIC,
            include_current=False
        )
    
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        history = self._build_history_data()
        for entry in history:
            if entry.average_usage is not None:
                return entry.to_attributes_dict()
        return {}


class MijnTedLastYearAverageMonthlyUsageSensor(MijnTedSensor):
    """Sensor for last year's average monthly usage extracted from coordinator data."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the last year average monthly usage sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "last_year_average_monthly_usage", "last year average monthly usage")
        self._attr_icon = "mdi:chart-line-variant"
        self._attr_suggested_display_precision = 0

    @property
    def state(self) -> Optional[float]:
        """Return the last year average usage for the current month's corresponding month from last year.
        
        Returns:
            Last year's average monthly usage value, or last known value if unavailable
        """
        current = self._build_current_data()
        if current:
            last_year_average_usage = current.last_year_average_usage
            if last_year_average_usage is not None:
                value = DataUtil.safe_float(last_year_average_usage)
                if value is not None:
                    self._update_last_known_value(value)
                    return value
        
        return self._last_known_value

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant
        """
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class.
        
        Returns:
            SensorStateClass.TOTAL for historical tracking
        """
        return SensorStateClass.TOTAL

    async def _async_inject_statistics(self) -> None:
        await self._async_inject_last_year_statistics("average_usage", "last_year_average_usage", StatisticMeanType.ARITHMETIC)
    

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing month_id and last_year_month_id attributes
        """
        return self._build_month_id_attributes()


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
        history = self._build_history_data()
        if not history:
            return
        
        if not self._validate_statistics_injection():
            return
        
        injected_periods: set[str] = set()
        entries_to_inject = []
        for entry in history:
            total_usage_end = entry.total_usage_end
            if total_usage_end is None:
                continue
            
            start_date = entry.start_date
            month_id = entry.month_id
            
            if not start_date or not month_id:
                continue
            
            if month_id in injected_periods:
                continue
            
            stat_time = self._parse_start_date_to_datetime(start_date)
            if not stat_time:
                continue
            
            usage_value = DataUtil.safe_float(total_usage_end)
            if usage_value is None:
                continue
            
            month_num = entry.month
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
        max_month_key = None
        
        for entry in entries_to_inject:
            current_total_usage_end = entry["state"]
            
            if entry["month"] == 1:
                delta = current_total_usage_end
            elif previous_total_usage_end is not None:
                delta = current_total_usage_end - previous_total_usage_end
            else:
                delta = current_total_usage_end
            
            cumulative_sum += delta
            
            stat_time = entry["stat_time"]
            statistics.append(
                StatisticData(
                    start=stat_time,
                    state=current_total_usage_end,
                    sum=cumulative_sum
                )
            )
            injected_periods.add(entry["month_id"])
            previous_total_usage_end = current_total_usage_end
            max_month_key = self._update_max_month_key(stat_time, max_month_key)
        
        await self._finalize_statistics_injection(statistics, StatisticMeanType.NONE, max_month_key, has_sum=True)
    

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing current and historical usage data
        """
        attributes: Dict[str, Any] = {}
        
        current_readings = self._build_current_data()
        historical_readings_list = self._build_history_data()
        
        if current_readings is not None:
            attributes["current"] = current_readings.to_dict()
        if historical_readings_list:
            attributes["history"] = [entry.to_dict() for entry in historical_readings_list]
        
        return attributes

