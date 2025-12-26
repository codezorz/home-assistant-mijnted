from typing import Any, Dict, Optional
from datetime import datetime
from homeassistant.components.sensor import SensorStateClass
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .base import MijnTedSensor
from ..utils import DataUtil, DateUtil
from ..const import UNIT_MIJNTED, YEAR_TRANSITION_MULTIPLIER


class MijnTedThisMonthUsageSensor(MijnTedSensor):
    """Sensor for this month's usage."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the this month usage sensor."""
        super().__init__(coordinator, "this_month_usage", "this month usage")
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_suggested_display_precision = 0



    def _calculate_measured_months_total(self, usage_data: Dict[str, Any], current_year: int) -> Optional[float]:
        if not isinstance(usage_data, dict):
            return None
        
        monthly_usages = usage_data.get("monthlyEnergyUsages", [])
        if not monthly_usages:
            return None
        
        total = 0.0
        has_valid_data = False
        
        for month in monthly_usages:
            if not isinstance(month, dict):
                continue
            
            month_year = month.get("monthYear", "")
            if not month_year:
                continue
            
            parsed = DataUtil.parse_month_year(month_year)
            if parsed:
                _, year = parsed
                if year == current_year:
                    total_usage = month.get("totalEnergyUsage", 0)
                    if isinstance(total_usage, (int, float)) and float(total_usage) > 0:
                        total += float(total_usage)
                        has_valid_data = True
        
        return total if has_valid_data else None

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor.
        
        Returns:
            This month's usage calculated from total minus measured months, or last known value if unavailable
        """
        data = self.coordinator.data
        if not data:
            return self._last_known_value
        
        # Get total usage from filter_status (sum of all device readings - cumulative)
        filter_status = data.get('filter_status')
        total_usage = DataUtil.calculate_filter_status_total(filter_status)
        
        if total_usage is None:
            return self._last_known_value
        
        # Try to calculate using monthly breakdown (handles year transitions correctly)
        current_year = datetime.now().year
        energy_usage_data = data.get("energy_usage_data", {})
        measured_months_total = self._calculate_measured_months_total(energy_usage_data, current_year)
        
        if measured_months_total is not None:
            this_month_usage = total_usage - measured_months_total
            if this_month_usage >= 0:
                self._update_last_known_value(this_month_usage)
                return this_month_usage
        
        # Fallback: Use usage_insight (works during normal months, but breaks at year transition)
        # This is kept for backward compatibility and when monthly data isn't available
        this_year_usage = None
        usage_insight = data.get("usage_insight", {})
        if isinstance(usage_insight, dict):
            usage = usage_insight.get("usage")
            if usage is not None:
                try:
                    this_year_usage = float(usage)
                except (ValueError, TypeError):
                    pass
        
        # At year transition, this_year_usage might be very low, causing incorrect high values
        # So we validate: if the difference is suspiciously large, don't trust it
        if this_year_usage is not None and this_year_usage > 0:
            this_month_usage = total_usage - this_year_usage
            if this_month_usage >= 0:
                if this_year_usage > 0 and this_month_usage > (this_year_usage * YEAR_TRANSITION_MULTIPLIER):
                    return self._last_known_value
                self._update_last_known_value(this_month_usage)
                return this_month_usage
        
        return self._last_known_value

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant for MijnTed measurements
        """
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class.
        
        Returns:
            SensorStateClass.TOTAL for cumulative usage sensors
        """
        return SensorStateClass.TOTAL


    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing month data, averages, and last year comparisons
        """
        attributes: Dict[str, Any] = {}
        
        data = self.coordinator.data
        if not data:
            return attributes
        
        energy_usage_data = data.get("energy_usage_data", {})
        if isinstance(energy_usage_data, dict):
            latest_month = DataUtil.find_latest_valid_month(energy_usage_data)
            if latest_month:
                month_year = latest_month.get("monthYear")
                if month_year:
                    attributes["month"] = month_year
                    
                    if not DataUtil.is_current_month(month_year):
                        attributes["data_for_previous_month"] = True
                    
                    latest_month_total = latest_month.get("totalEnergyUsage")
                    if latest_month_total is not None:
                        try:
                            attributes["latest_month_usage"] = float(latest_month_total)
                        except (ValueError, TypeError):
                            pass
                    
                    month_num = DataUtil.extract_month_number(month_year)
                    
                    usage_last_year = data.get("usage_last_year", {})
                    if isinstance(usage_last_year, dict) and month_num:
                        # Find the same month in last year (e.g., if current is "11.2025", find "11.2024")
                        last_year = DateUtil.get_last_year()
                        last_year_month_identifier = f"{month_num}.{last_year}"
                        last_year_month = DataUtil.find_month_by_identifier(usage_last_year, last_year_month_identifier)
                        
                        if last_year_month:
                            last_year_avg = last_year_month.get("averageEnergyUseForBillingUnit")
                            if last_year_avg is not None:
                                try:
                                    attributes["latest_month_average_usage_last_year"] = float(last_year_avg)
                                except (ValueError, TypeError):
                                    pass
                            
                            last_year_total = last_year_month.get("totalEnergyUsage")
                            if last_year_total is not None:
                                try:
                                    attributes["latest_month_last_year_usage"] = float(last_year_total)
                                except (ValueError, TypeError):
                                    pass
                
                avg_usage = latest_month.get("averageEnergyUseForBillingUnit")
                if avg_usage is not None:
                    try:
                        attributes["latest_month_average_usage"] = float(avg_usage)
                    except (ValueError, TypeError):
                        pass
        
        return attributes


class MijnTedLatestMonthLastYearUsageSensor(MijnTedSensor):
    """Sensor for last year's usage for the latest month."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the latest month last year usage sensor."""
        super().__init__(coordinator, "latest_month_last_year_usage", "latest month last year usage")
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_suggested_display_precision = 0

    @property
    def state(self) -> Optional[float]:
        """Return the last year usage for the latest month."""
        data = self.coordinator.data
        if not data:
            return None
        
        energy_usage_data = data.get("energy_usage_data", {})
        if not isinstance(energy_usage_data, dict):
            return None
        
        latest_month = DataUtil.find_latest_valid_month(energy_usage_data)
        if not latest_month:
            return None
        
        month_year = latest_month.get("monthYear")
        if not month_year:
            return None
        
        # Extract month number to find same month in last year
        month_num = DataUtil.extract_month_number(month_year)
        if not month_num:
            return None
        
        # Get last year usage data
        usage_last_year = data.get("usage_last_year", {})
        if not isinstance(usage_last_year, dict):
            return None
        
        # Find the same month in last year
        last_year = DateUtil.get_last_year()
        last_year_month_identifier = f"{month_num}.{last_year}"
        last_year_month = DataUtil.find_month_by_identifier(usage_last_year, last_year_month_identifier)
        
        if last_year_month:
            last_year_total = last_year_month.get("totalEnergyUsage")
            if last_year_total is not None:
                try:
                    return float(last_year_total)
                except (ValueError, TypeError):
                    pass
        
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant for MijnTed measurements
        """
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing month identifier and related data
        """
        attributes: Dict[str, Any] = {}
        
        data = self.coordinator.data
        if not data:
            return attributes
        
        energy_usage_data = data.get("energy_usage_data", {})
        if isinstance(energy_usage_data, dict):
            latest_month = DataUtil.find_latest_valid_month(energy_usage_data)
            if latest_month:
                month_year = latest_month.get("monthYear")
                if month_year:
                    attributes["month"] = month_year
        
        return attributes


class MijnTedLatestMonthAverageUsageSensor(MijnTedSensor):
    """Sensor for latest month's average usage."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the latest month average usage sensor."""
        super().__init__(coordinator, "latest_month_average_usage", "latest month average usage")
        self._attr_icon = "mdi:chart-line"
        self._attr_suggested_display_precision = 0

    @property
    def state(self) -> Optional[float]:
        """Return the average usage for the latest month."""
        data = self.coordinator.data
        if not data:
            return None
        
        energy_usage_data = data.get("energy_usage_data", {})
        if not isinstance(energy_usage_data, dict):
            return None
        
        latest_month = DataUtil.find_latest_valid_month(energy_usage_data)
        if not latest_month:
            return None
        
        avg_usage = latest_month.get("averageEnergyUseForBillingUnit")
        if avg_usage is not None:
            try:
                return float(avg_usage)
            except (ValueError, TypeError):
                pass
        
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant for MijnTed measurements
        """
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class.
        
        Returns:
            SensorStateClass.MEASUREMENT for average/measurement sensors
        """
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing month identifier and related data
        """
        attributes: Dict[str, Any] = {}
        
        data = self.coordinator.data
        if not data:
            return attributes
        
        energy_usage_data = data.get("energy_usage_data", {})
        if isinstance(energy_usage_data, dict):
            latest_month = DataUtil.find_latest_valid_month(energy_usage_data)
            if latest_month:
                month_year = latest_month.get("monthYear")
                if month_year:
                    attributes["month"] = month_year
        
        return attributes


class MijnTedLatestMonthLastYearAverageUsageSensor(MijnTedSensor):
    """Sensor for last year's average usage for the latest month."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the latest month last year average usage sensor."""
        super().__init__(coordinator, "latest_month_average_last_year_usage", "latest month last year average usage")
        self._attr_icon = "mdi:chart-line-variant"
        self._attr_suggested_display_precision = 0

    @property
    def state(self) -> Optional[float]:
        """Return the last year average usage for the latest month."""
        data = self.coordinator.data
        if not data:
            return None
        
        energy_usage_data = data.get("energy_usage_data", {})
        if not isinstance(energy_usage_data, dict):
            return None
        
        latest_month = DataUtil.find_latest_valid_month(energy_usage_data)
        if not latest_month:
            return None
        
        month_year = latest_month.get("monthYear")
        if not month_year:
            return None
        
        # Extract month number to find same month in last year
        month_num = DataUtil.extract_month_number(month_year)
        if not month_num:
            return None
        
        # Get last year usage data
        usage_last_year = data.get("usage_last_year", {})
        if not isinstance(usage_last_year, dict):
            return None
        
        # Find the same month in last year
        last_year = DateUtil.get_last_year()
        last_year_month_identifier = f"{month_num}.{last_year}"
        last_year_month = DataUtil.find_month_by_identifier(usage_last_year, last_year_month_identifier)
        
        if last_year_month:
            last_year_avg = last_year_month.get("averageEnergyUseForBillingUnit")
            if last_year_avg is not None:
                try:
                    return float(last_year_avg)
                except (ValueError, TypeError):
                    pass
        
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant for MijnTed measurements
        """
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class.
        
        Returns:
            SensorStateClass.MEASUREMENT for average/measurement sensors
        """
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing month identifier and related data
        """
        attributes: Dict[str, Any] = {}
        
        data = self.coordinator.data
        if not data:
            return attributes
        
        energy_usage_data = data.get("energy_usage_data", {})
        if isinstance(energy_usage_data, dict):
            latest_month = DataUtil.find_latest_valid_month(energy_usage_data)
            if latest_month:
                month_year = latest_month.get("monthYear")
                if month_year:
                    attributes["month"] = month_year
        
        return attributes


class MijnTedLatestMonthUsageSensor(MijnTedSensor):
    """Sensor for latest month's actual usage."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the latest month usage sensor."""
        super().__init__(coordinator, "latest_month_usage", "latest month usage")
        self._attr_icon = "mdi:chart-line"
        self._attr_suggested_display_precision = 0

    @property
    def state(self) -> Optional[float]:
        """Return the usage for the latest month."""
        data = self.coordinator.data
        if not data:
            return None
        
        energy_usage_data = data.get("energy_usage_data", {})
        if not isinstance(energy_usage_data, dict):
            return None
        
        latest_month = DataUtil.find_latest_valid_month(energy_usage_data)
        if not latest_month:
            return None
        
        total_usage = latest_month.get("totalEnergyUsage")
        if total_usage is not None:
            try:
                return float(total_usage)
            except (ValueError, TypeError):
                pass
        
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant for MijnTed measurements
        """
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class.
        
        Returns:
            SensorStateClass.MEASUREMENT for average/measurement sensors
        """
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing month identifier and related data
        """
        attributes: Dict[str, Any] = {}
        
        data = self.coordinator.data
        if not data:
            return attributes
        
        energy_usage_data = data.get("energy_usage_data", {})
        if isinstance(energy_usage_data, dict):
            latest_month = DataUtil.find_latest_valid_month(energy_usage_data)
            if latest_month:
                month_year = latest_month.get("monthYear")
                if month_year:
                    attributes["month"] = month_year
        
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
        self._attr_state_class = SensorStateClass.TOTAL
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
    
    def _calculate_last_year_total(self) -> Optional[float]:
        data = self.coordinator.data
        if not data:
            return None
        
        usage_data = data.get("usage_last_year", {})
        # API returns {"monthlyEnergyUsages": [...], "averageEnergyUseForBillingUnit": 0}
        if isinstance(usage_data, dict):
            monthly_usages = usage_data.get("monthlyEnergyUsages", [])
            if monthly_usages:
                total = sum(
                    float(month.get("totalEnergyUsage", 0))
                    for month in monthly_usages
                    if isinstance(month, dict)
                )
                return total if total > 0 else None
            return float(usage_data.get("total", 0)) if usage_data.get("total") else None
        return float(usage_data) if isinstance(usage_data, (int, float)) else None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing device list and last year usage
        """
        attributes: Dict[str, Any] = {}
        
        data = self.coordinator.data
        if not data:
            return attributes
        
        filter_status = data.get('filter_status')
        if isinstance(filter_status, list):
            attributes["devices"] = filter_status
            attributes["device_count"] = len(filter_status)
        
        last_year_total = self._calculate_last_year_total()
        if last_year_total is not None:
            attributes["last_year_usage"] = last_year_total
        
        return attributes


class MijnTedThisYearUsageSensor(MijnTedSensor):
    """Sensor for this year's total usage with month breakdown."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the this year usage sensor."""
        super().__init__(coordinator, "this_year_usage", "this year usage")
        self._attr_icon = "mdi:chart-line"
        self._attr_suggested_display_precision = 0
    
    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor from usageInsight, or last known value if unavailable."""
        data = self.coordinator.data
        if not data:
            return self._last_known_value
        
        usage_insight = data.get("usage_insight", {})
        value = DataUtil.extract_usage_from_insight(usage_insight)
        if value is not None:
            self._update_last_known_value(value)
            return value
        return self._last_known_value
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class.
        
        Returns:
            SensorStateClass.TOTAL for cumulative usage sensors
        """
        return SensorStateClass.TOTAL
    
    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant
        """
        return UNIT_MIJNTED
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes from usageInsight and residentialUnitUsage.
        
        Returns:
            Dictionary containing usage insight data and monthly breakdown
        """
        attributes: Dict[str, Any] = {}
        
        data = self.coordinator.data
        if not data:
            return attributes
        
        usage_insight = data.get("usage_insight", {})
        attributes.update(DataUtil.extract_usage_insight_attributes(usage_insight))
        
        usage_data = data.get("usage_this_year", {})
        month_breakdown = DataUtil.extract_monthly_breakdown(usage_data)
        if month_breakdown:
            attributes["monthly_breakdown"] = month_breakdown
        
        return attributes


class MijnTedLastYearUsageSensor(MijnTedSensor):
    """Sensor for last year's total usage with month breakdown."""
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]]) -> None:
        """Initialize the last year usage sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "last_year_usage", "last year usage")
        self._attr_icon = "mdi:chart-line"
        self._attr_suggested_display_precision = 0
    
    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor from usageInsight, or last known value if unavailable.
        
        Returns:
            Total usage for last year, or last known value if unavailable
        """
        data = self.coordinator.data
        if not data:
            return self._last_known_value
        
        usage_insight = data.get("usage_insight_last_year", {})
        value = DataUtil.extract_usage_from_insight(usage_insight)
        if value is not None:
            self._update_last_known_value(value)
            return value
        return self._last_known_value
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class.
        
        Returns:
            SensorStateClass.TOTAL for cumulative usage sensors
        """
        return SensorStateClass.TOTAL
    
    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant for MijnTed measurements
        """
        return UNIT_MIJNTED
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes from usageInsight and residentialUnitUsage.
        
        Returns:
            Dictionary containing usage insight attributes and residential unit usage data
        """
        attributes: Dict[str, Any] = {}
        
        data = self.coordinator.data
        if not data:
            return attributes
        
        # Add all properties from usageInsight
        usage_insight = data.get("usage_insight_last_year", {})
        attributes.update(DataUtil.extract_usage_insight_attributes(usage_insight))
        
        # Add monthly breakdown from residentialUnitUsage
        usage_data = data.get("usage_last_year", {})
        month_breakdown = DataUtil.extract_monthly_breakdown(usage_data)
        if month_breakdown:
            attributes["monthly_breakdown"] = month_breakdown
        
        return attributes

