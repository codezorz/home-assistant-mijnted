"""Usage-related sensors for MijnTed integration."""
from typing import Any, Dict, Optional
from datetime import datetime
from homeassistant.components.sensor import SensorStateClass
from .base import MijnTedSensor
from ..utils import DataUtil
from ..const import UNIT_MIJNTED, YEAR_TRANSITION_MULTIPLIER


class MijnTedThisMonthUsageSensor(MijnTedSensor):
    """Sensor for this month's usage."""
    
    def __init__(self, coordinator):
        """Initialize the this month usage sensor."""
        super().__init__(coordinator, "energy_usage", "this month usage")
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_suggested_display_precision = 0

    def _find_latest_valid_month(self, usage_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find the most recent month with totalEnergyUsage > 0 and averageEnergyUseForBillingUnit != null."""
        if not isinstance(usage_data, dict):
            return None
        
        monthly_usages = usage_data.get("monthlyEnergyUsages", [])
        if not monthly_usages:
            return None
        
        # Parse monthYear format (e.g., "11.2025") and sort by date (most recent first)
        valid_months = []
        for month in monthly_usages:
            if not isinstance(month, dict):
                continue
            
            total_usage = month.get("totalEnergyUsage", 0)
            avg_usage = month.get("averageEnergyUseForBillingUnit")
            
            # Check if this month has valid data
            if (isinstance(total_usage, (int, float)) and float(total_usage) > 0 and 
                avg_usage is not None):
                month_year = month.get("monthYear", "")
                parsed = DataUtil.parse_month_year(month_year)
                if parsed:
                    month_num, year = parsed
                    # Create a sortable key (year * 100 + month)
                    sort_key = year * 100 + month_num
                    valid_months.append((sort_key, month))
        
        # Sort by date descending (most recent first) and return the first valid one
        if valid_months:
            valid_months.sort(key=lambda x: x[0], reverse=True)
            return valid_months[0][1]
        
        return None

    def _find_month_by_identifier(self, usage_data: Dict[str, Any], month_identifier: str) -> Optional[Dict[str, Any]]:
        """Find a specific month entry by monthYear identifier.
        
        Args:
            usage_data: Dictionary containing monthly energy usage data
            month_identifier: Month identifier in format "MM.YYYY"
            
        Returns:
            Month dictionary if found, None otherwise
        """
        if not isinstance(usage_data, dict):
            return None
        
        monthly_usages = usage_data.get("monthlyEnergyUsages", [])
        if not monthly_usages:
            return None
        
        for month in monthly_usages:
            if isinstance(month, dict) and month.get("monthYear") == month_identifier:
                return month
        
        return None


    def _calculate_measured_months_total(self, usage_data: Dict[str, Any], current_year: int) -> Optional[float]:
        """Calculate the sum of all measured months for the current year.
        
        Args:
            usage_data: Dictionary containing monthly energy usage data
            current_year: Year to calculate for
            
        Returns:
            Total usage for measured months, or None if no valid data
        """
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
            
            # Check if this month is for the current year
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
        # Get total usage from filter_status (sum of all device readings - cumulative)
        filter_status = self.coordinator.data.get('filter_status')
        total_usage = DataUtil.calculate_filter_status_total(filter_status)
        
        if total_usage is None:
            # Return last known value if available
            return self._last_known_value
        
        # Try to calculate using monthly breakdown (handles year transitions correctly)
        current_year = datetime.now().year
        energy_usage_data = self.coordinator.data.get("energy_usage_data", {})
        measured_months_total = self._calculate_measured_months_total(energy_usage_data, current_year)
        
        if measured_months_total is not None:
            # Use monthly breakdown: total - sum of measured months = unmeasured usage
            this_month_usage = total_usage - measured_months_total
            if this_month_usage >= 0:
                self._update_last_known_value(this_month_usage)
                return this_month_usage
        
        # Fallback: Use usage_insight (works during normal months, but breaks at year transition)
        # This is kept for backward compatibility and when monthly data isn't available
        this_year_usage = None
        usage_insight = self.coordinator.data.get("usage_insight", {})
        if isinstance(usage_insight, dict):
            usage = usage_insight.get("usage")
            if usage is not None:
                try:
                    this_year_usage = float(usage)
                except (ValueError, TypeError):
                    pass
        
        # Only use this calculation if we have valid data and it makes sense
        # At year transition, this_year_usage might be very low, causing incorrect high values
        # So we validate: if the difference is suspiciously large, don't trust it
        if this_year_usage is not None and this_year_usage > 0:
            this_month_usage = total_usage - this_year_usage
            # Sanity check: if difference is more than 2x this_year_usage, likely year transition issue
            # In that case, return last known value to wait for monthly data to be available
            if this_month_usage >= 0:
                if this_year_usage > 0 and this_month_usage > (this_year_usage * YEAR_TRANSITION_MULTIPLIER):
                    # Suspiciously large difference - likely year transition issue
                    # Return last known value to wait for monthly data to be available
                    return self._last_known_value
                self._update_last_known_value(this_month_usage)
                return this_month_usage
        
        # Return last known value if available
        return self._last_known_value

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL


    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing month data, averages, and last year comparisons
        """
        attributes: Dict[str, Any] = {}
        
        # Get current year usage data
        energy_usage_data = self.coordinator.data.get("energy_usage_data", {})
        if isinstance(energy_usage_data, dict):
            latest_month = self._find_latest_valid_month(energy_usage_data)
            if latest_month:
                # Add the month identifier
                month_year = latest_month.get("monthYear")
                if month_year:
                    attributes["month"] = month_year
                    
                    # Check if this is the current month or previous month
                    if not DataUtil.is_current_month(month_year):
                        attributes["data_for_previous_month"] = True
                    
                    # Extract month number to find same month in last year
                    month_num = DataUtil.extract_month_number(month_year)
                    
                    # Get last year usage data
                    usage_last_year = self.coordinator.data.get("usage_last_year", {})
                    if isinstance(usage_last_year, dict) and month_num:
                        # Find the same month in last year (e.g., if current is "11.2025", find "11.2024")
                        last_year = datetime.now().year - 1
                        last_year_month_identifier = f"{month_num}.{last_year}"
                        last_year_month = self._find_month_by_identifier(usage_last_year, last_year_month_identifier)
                        
                        if last_year_month:
                            # Add last year's average usage from the same month
                            last_year_avg = last_year_month.get("averageEnergyUseForBillingUnit")
                            if last_year_avg is not None:
                                try:
                                    attributes["last_year_average_usage"] = float(last_year_avg)
                                except (ValueError, TypeError):
                                    pass
                            
                            # Add last year's total usage from the same month
                            last_year_total = last_year_month.get("totalEnergyUsage")
                            if last_year_total is not None:
                                try:
                                    attributes["last_year_usage"] = float(last_year_total)
                                except (ValueError, TypeError):
                                    pass
                
                # Add average usage for billing unit from this month
                avg_usage = latest_month.get("averageEnergyUseForBillingUnit")
                if avg_usage is not None:
                    try:
                        attributes["average_usage"] = float(avg_usage)
                    except (ValueError, TypeError):
                        pass
        
        return attributes


class MijnTedTotalUsageSensor(MijnTedSensor):
    """Sensor for total device readings from all devices."""
    
    def __init__(self, coordinator):
        """Initialize the total usage sensor.
        
        Args:
            coordinator: Data update coordinator
        """
        super().__init__(coordinator, "filter", "total usage")
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_suggested_display_precision = 0

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor.
        
        Returns:
            Sum of all device readings, or last known value if unavailable
        """
        filter_status = self.coordinator.data.get('filter_status')
        total = DataUtil.calculate_filter_status_total(filter_status)
        if total is not None:
            self._update_last_known_value(total)
            return total
        
        # Return last known value if available
        return self._last_known_value

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant
        """
        return UNIT_MIJNTED
    
    def _calculate_last_year_total(self) -> Optional[float]:
        """Calculate total usage from last year's monthly data.
        
        Returns:
            Total usage for last year, or None if no valid data
        """
        usage_data = self.coordinator.data.get("usage_last_year", {})
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
        
        filter_status = self.coordinator.data.get('filter_status')
        if isinstance(filter_status, list):
            attributes["devices"] = filter_status
            attributes["device_count"] = len(filter_status)
        
        # Add last year's total usage
        last_year_total = self._calculate_last_year_total()
        if last_year_total is not None:
            attributes["last_year_usage"] = last_year_total
        
        return attributes


class MijnTedThisYearUsageSensor(MijnTedSensor):
    """Sensor for this year's total usage with month breakdown."""
    
    def __init__(self, coordinator):
        """Initialize the this year usage sensor."""
        super().__init__(coordinator, "this_year_usage", "this year usage")
        self._attr_icon = "mdi:chart-line"
        self._attr_suggested_display_precision = 0
    
    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor from usageInsight, or last known value if unavailable."""
        usage_insight = self.coordinator.data.get("usage_insight", {})
        value = DataUtil.extract_usage_from_insight(usage_insight)
        if value is not None:
            self._update_last_known_value(value)
            return value
        # Return last known value if available
        return self._last_known_value
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
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
        
        # Add all properties from usageInsight
        usage_insight = self.coordinator.data.get("usage_insight", {})
        attributes.update(DataUtil.extract_usage_insight_attributes(usage_insight))
        
        # Add monthly breakdown from residentialUnitUsage
        usage_data = self.coordinator.data.get("usage_this_year", {})
        month_breakdown = DataUtil.extract_monthly_breakdown(usage_data)
        if month_breakdown:
            attributes["monthly_breakdown"] = month_breakdown
        
        return attributes


class MijnTedLastYearUsageSensor(MijnTedSensor):
    """Sensor for last year's total usage with month breakdown."""
    
    def __init__(self, coordinator):
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
        usage_insight = self.coordinator.data.get("usage_insight_last_year", {})
        value = DataUtil.extract_usage_from_insight(usage_insight)
        if value is not None:
            self._update_last_known_value(value)
            return value
        # Return last known value if available
        return self._last_known_value
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL
    
    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UNIT_MIJNTED
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes from usageInsight and residentialUnitUsage."""
        attributes: Dict[str, Any] = {}
        
        # Add all properties from usageInsight
        usage_insight = self.coordinator.data.get("usage_insight_last_year", {})
        attributes.update(DataUtil.extract_usage_insight_attributes(usage_insight))
        
        # Add monthly breakdown from residentialUnitUsage
        usage_data = self.coordinator.data.get("usage_last_year", {})
        month_breakdown = DataUtil.extract_monthly_breakdown(usage_data)
        if month_breakdown:
            attributes["monthly_breakdown"] = month_breakdown
        
        return attributes

