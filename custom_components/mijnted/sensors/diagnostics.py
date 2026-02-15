from typing import Any, Dict, Optional, Tuple
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .base import MijnTedSensor
from .models import StatisticsTracking
from ..utils import TimestampUtil, ListUtil, DataUtil, DateUtil
from ..const import CALCULATION_YEAR_MONTH_SORT_MULTIPLIER


class MijnTedLastUpdateSensor(MijnTedSensor):
    """Sensor for last update timestamp."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the last update sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "last_update", "last update")
        self._attr_icon = "mdi:clock-outline"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> Optional[str]:
        """Return the last update timestamp.
        
        Returns:
            ISO timestamp string of last sync date, or None if not available
        """
        data = self.coordinator.data
        if not data:
            return None
        
        last_update = data.get('last_update')
        if isinstance(last_update, dict):
            date_str = last_update.get("lastSyncDate") or last_update.get("date")
        else:
            date_str = str(last_update) if last_update else None
        
        if date_str:
            return TimestampUtil.parse_date_to_timestamp(date_str)
        return None


class MijnTedActiveModelSensor(MijnTedSensor):
    """Sensor for active model information."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the active model sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "active_model", "active model")
        self._attr_icon = "mdi:tag"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor.
        
        Returns:
            Active model string, or None if not available
        """
        data = self.coordinator.data
        if not data:
            return None
        return data.get("active_model")


class MijnTedDeliveryTypesSensor(MijnTedSensor):
    """Sensor for delivery types."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the delivery types sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "delivery_types", "delivery type")
        self._attr_icon = "mdi:package-variant"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor.
        
        Returns:
            Comma-separated list of delivery types, or None if empty
        """
        data = self.coordinator.data
        if not data:
            return None
        
        delivery_types = data.get("delivery_types", [])
        if not delivery_types:
            return None
        return ", ".join(str(dt) for dt in delivery_types)


class MijnTedResidentialUnitDetailSensor(MijnTedSensor):
    """Sensor for residential unit details."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the residential unit detail sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "residential_unit_detail", "residential unit")
        self._attr_icon = "mdi:home"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor.
        
        Returns:
            Residential unit identifier, or None if not available
        """
        data = self.coordinator.data
        if not data:
            return None
        return data.get("residential_unit")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing all residential unit detail data
        """
        data = self.coordinator.data
        if not data:
            return {}
        return data.get("residential_unit_detail", {})


class MijnTedUnitOfMeasuresSensor(MijnTedSensor):
    """Sensor for unit of measures information."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the unit of measures sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "unit_of_measures", "unit of measures")
        self._attr_icon = "mdi:ruler"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor.
        
        Returns:
            Display name of first unit of measure, or last known value if unavailable (e.g. timeout)
        """
        data = self.coordinator.data
        if not data:
            return self._last_known_value

        unit_of_measures = data.get("unit_of_measures", [])
        first_item = ListUtil.get_first_item(unit_of_measures)
        if first_item is not None and isinstance(first_item, dict):
            display_name = first_item.get("displayName")
            if display_name is not None:
                self._update_last_known_value(display_name)
                return display_name
        return self._last_known_value

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing unit of measures list
        """
        data = self.coordinator.data
        if not data:
            return {}
        
        unit_of_measures = data.get("unit_of_measures", [])
        if isinstance(unit_of_measures, list):
            return {"unit_of_measures": unit_of_measures}
        return {}


class MijnTedLastSuccessfulSyncSensor(MijnTedSensor):
    """Sensor for the timestamp of the last successful data sync."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the last successful sync sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "last_successful_sync", "last successful sync")
        self._attr_icon = "mdi:clock-check"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
    
    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor.
        
        Returns:
            ISO timestamp string of last successful sync, or None if not available
        """
        return self._get_last_successful_sync()


class MijnTedLatestAvailableInsightSensor(MijnTedSensor):
    """Diagnostic sensor displaying the month with the last available insight data including average."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the latest available insight sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "latest_available_insight", "latest available insight")
        self._attr_icon = "mdi:calendar-month"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_native_unit_of_measurement = None
    
    def _find_latest_month_with_average_from_energy_data(
        self, energy_data: Dict[str, Any]
    ) -> Tuple[Optional[int], Optional[int]]:
        """Find the latest month with average usage from energy data.
        
        Args:
            energy_data: Energy usage data dictionary
            
        Returns:
            Tuple of (month_num, year) for latest month with average, or (None, None) if not found
        """
        if not isinstance(energy_data, dict):
            return None, None
        
        latest_sort_key = 0
        latest_month_num = None
        latest_year = None
        
        monthly_usages = energy_data.get("monthlyEnergyUsages", [])
        for month in monthly_usages:
            if not isinstance(month, dict):
                continue
            
            avg_usage = month.get("averageEnergyUseForBillingUnit")
            if avg_usage is not None:
                month_year = month.get("monthYear", "")
                parsed = DataUtil.parse_month_year(month_year)
                if parsed:
                    month_num, year = parsed
                    sort_key = year * CALCULATION_YEAR_MONTH_SORT_MULTIPLIER + month_num
                    if sort_key > latest_sort_key:
                        latest_sort_key = sort_key
                        latest_month_num = month_num
                        latest_year = year
        
        return latest_month_num, latest_year
    
    def _find_latest_month_with_average_from_cache(
        self, monthly_history_cache: Dict[str, Any]
    ) -> Tuple[Optional[int], Optional[int]]:
        """Find the latest month with average usage from monthly history cache.
        
        Args:
            monthly_history_cache: Monthly history cache dictionary
            
        Returns:
            Tuple of (month_num, year) for latest month with average, or (None, None) if not found
        """
        if not isinstance(monthly_history_cache, dict) or not monthly_history_cache:
            return None, None
        
        month_keys = list(monthly_history_cache.keys())
        month_keys.sort(key=lambda k: (int(k.split("-")[0]), int(k.split("-")[1])), reverse=True)
        
        for month_key in month_keys:
            month_data = monthly_history_cache[month_key]
            if isinstance(month_data, dict):
                if month_data.get("average_usage") is not None:
                    month_num = month_data.get("month")
                    year = month_data.get("year")
                    if month_num is not None and year is not None:
                        try:
                            return int(month_num), int(year)
                        except (ValueError, TypeError):
                            pass
        
        return None, None
    
    @property
    def state(self) -> Optional[str]:
        """Return the month name (e.g., "November 2025") for the latest available insight with average.
        
        Returns:
            Month name string in format "MonthName YYYY" for the latest month with average_usage,
            or None if not available
        """
        data = self.coordinator.data
        if not data:
            return None
        
        latest_month_num, latest_year = self._find_latest_month_with_average_from_energy_data(
            data.get("energy_usage_data", {})
        )
        
        usage_last_year = data.get("usage_last_year", {})
        if isinstance(usage_last_year, dict):
            last_year_month_num, last_year_year = self._find_latest_month_with_average_from_energy_data(
                usage_last_year
            )
            if last_year_month_num is not None and last_year_year is not None:
                last_year_sort_key = last_year_year * CALCULATION_YEAR_MONTH_SORT_MULTIPLIER + last_year_month_num
                if latest_month_num is None or latest_year is None:
                    latest_month_num, latest_year = last_year_month_num, last_year_year
                else:
                    current_sort_key = latest_year * CALCULATION_YEAR_MONTH_SORT_MULTIPLIER + latest_month_num
                    if last_year_sort_key > current_sort_key:
                        latest_month_num, latest_year = last_year_month_num, last_year_year
        
        if latest_month_num is not None and latest_year is not None:
            formatted = DateUtil.format_month_name(latest_month_num, latest_year)
            if formatted:
                return formatted
        
        cache_month_num, cache_year = self._find_latest_month_with_average_from_cache(
            data.get("monthly_history_cache", {})
        )
        if cache_month_num is not None and cache_year is not None:
            formatted = DateUtil.format_month_name(cache_month_num, cache_year)
            if formatted:
                return formatted
        
        return None
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes with all available month data.
        
        Returns:
            Dictionary containing:
            - month_id: Month identifier (MM.YYYY)
            - usage_unit: Unit for energy values (e.g. Eenheden)
            - has_average: Whether average data is available
        """
        attributes: Dict[str, Any] = {}
        
        data = self.coordinator.data
        if not data:
            return attributes
        
        statistics_tracking = data.get("statistics_tracking")
        if isinstance(statistics_tracking, StatisticsTracking):
            attributes["statistics"] = statistics_tracking.to_dict()
        
        energy_usage_data = data.get("energy_usage_data", {})
        if not isinstance(energy_usage_data, dict):
            return attributes
        
        latest_month = DataUtil.find_latest_valid_month(energy_usage_data)
        has_average = latest_month is not None
        if not latest_month:
            latest_month = DataUtil.find_latest_month_with_data(energy_usage_data)
        
        if not latest_month:
            return attributes
        
        month_year = latest_month.get("monthYear")
        if month_year:
            attributes["month_id"] = month_year
            attributes["has_average"] = has_average
        
        usage_unit = latest_month.get("unitOfMeasurement")
        if usage_unit:
            attributes["usage_unit"] = usage_unit
        
        return attributes

