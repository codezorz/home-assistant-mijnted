from typing import Any, Dict, Optional, Tuple, List
from datetime import datetime
from ..const import CALCULATION_YEAR_MONTH_SORT_MULTIPLIER, MONTH_YEAR_PARTS_COUNT


class DataUtil:
    """Utility class for data parsing and extraction."""
    
    @staticmethod
    def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
        """Safely convert a value to float.
        
        Args:
            value: Value to convert to float
            default: Default value to return if conversion fails or value is None
            
        Returns:
            Float value if conversion succeeds, default value otherwise
        """
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
        """Safely convert a value to int.
        
        Args:
            value: Value to convert to int
            default: Default value to return if conversion fails or value is None
            
        Returns:
            Integer value if conversion succeeds, default value otherwise
        """
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def parse_month_year(month_year: str) -> Optional[Tuple[int, int]]:
        """Parse month year string in format "MM.YYYY".
        
        Args:
            month_year: Month year string in format "MM.YYYY"
            
        Returns:
            Tuple of (month, year) if valid, None otherwise
        """
        try:
            parts = month_year.split(".")
            if len(parts) == MONTH_YEAR_PARTS_COUNT:
                return (int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            pass
        return None
    
    @staticmethod
    def extract_month_number(month_year: str) -> Optional[int]:
        """Extract month number from monthYear format.
        
        Args:
            month_year: Month year string in format "MM.YYYY"
            
        Returns:
            Month number (1-12) if valid, None otherwise
        """
        parsed = DataUtil.parse_month_year(month_year)
        return parsed[0] if parsed else None
    
    @staticmethod
    def is_current_month(month_year: str) -> bool:
        """Check if the given month_year string represents the current month.
        
        Args:
            month_year: Month year string in format "MM.YYYY"
            
        Returns:
            True if the month_year represents the current month, False otherwise
        """
        parsed = DataUtil.parse_month_year(month_year)
        if parsed:
            month_num, year = parsed
            now = datetime.now()
            return month_num == now.month and year == now.year
        return False
    
    @staticmethod
    def extract_usage_from_insight(usage_insight: Dict[str, Any]) -> Optional[float]:
        """Extract usage value from usage insight dictionary.
        
        Args:
            usage_insight: Dictionary containing usage insight data
            
        Returns:
            Usage value as float if available, None otherwise
        """
        if isinstance(usage_insight, dict):
            usage = usage_insight.get("usage")
            if usage is not None:
                try:
                    return float(usage)
                except (ValueError, TypeError):
                    pass
        return None
    
    @staticmethod
    def calculate_filter_status_total(filter_status: Any) -> Optional[float]:
        """Calculate total from filter_status data.
        
        Args:
            filter_status: Filter status data (list, dict, or number)
            
        Returns:
            Total value as float if valid, None otherwise
        """
        if isinstance(filter_status, list):
            total = sum(
                float(device.get("currentReadingValue", 0))
                for device in filter_status
                if isinstance(device, dict)
            )
            return total if total > 0 else None
        elif isinstance(filter_status, dict):
            value = filter_status.get("filterStatus") or filter_status.get("status")
            if value is not None:
                try:
                    value = float(value)
                    return value if value > 0 else None
                except (ValueError, TypeError):
                    pass
        elif isinstance(filter_status, (int, float)):
            value = float(filter_status)
            return value if value > 0 else None
        return None
    
    @staticmethod
    def extract_monthly_breakdown(usage_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Extract monthly breakdown from usage data.
        
        Args:
            usage_data: Dictionary containing monthlyEnergyUsages list
        
        Returns:
            Dictionary with monthYear as key and month data as value
            
        Example:
            Input: {"monthlyEnergyUsages": [{"monthYear": "11.2025", ...}]}
            Output: {"11.2025": {"total_energy_usage": 100.0, ...}}
        """
        month_breakdown: Dict[str, Dict[str, Any]] = {}
        
        if not isinstance(usage_data, dict):
            return month_breakdown
        
        monthly_usages = usage_data.get("monthlyEnergyUsages", [])
        if not monthly_usages:
            return month_breakdown
        
        for month in monthly_usages:
            if not isinstance(month, dict):
                continue
            
            month_year = month.get("monthYear")
            if not month_year:
                continue
            
            month_data: Dict[str, Any] = {}
            
            if "totalEnergyUsage" in month:
                total_usage = month.get("totalEnergyUsage")
                if total_usage is not None:
                    try:
                        month_data["total_energy_usage"] = float(total_usage)
                    except (ValueError, TypeError):
                        pass
            
            if "unitOfMeasurement" in month:
                month_data["unit_of_measurement"] = month.get("unitOfMeasurement")
            
            if "averageEnergyUseForBillingUnit" in month:
                avg_usage = month.get("averageEnergyUseForBillingUnit")
                if avg_usage is not None:
                    try:
                        month_data["average_energy_use_for_billing_unit"] = float(avg_usage)
                    except (ValueError, TypeError):
                        pass
            
            if month_data:
                month_breakdown[month_year] = month_data
        
        return month_breakdown
    
    @staticmethod
    def extract_usage_insight_attributes(usage_insight: Dict[str, Any]) -> Dict[str, Any]:
        """Extract attributes from usage insight data.
        
        Args:
            usage_insight: Dictionary containing usage insight data
        
        Returns:
            Dictionary of extracted attributes with snake_case keys
            
        Example:
            Input: {"unitType": "heat", "billingUnitAverageUsage": 50.0}
            Output: {"unit_type": "heat", "billing_unit_average_usage": 50.0}
        """
        attributes: Dict[str, Any] = {}
        
        if not isinstance(usage_insight, dict):
            return attributes
        
        if "unitType" in usage_insight:
            attributes["unit_type"] = usage_insight.get("unitType")
        
        if "billingUnitAverageUsage" in usage_insight:
            billing_avg = usage_insight.get("billingUnitAverageUsage")
            if billing_avg is not None:
                try:
                    attributes["billing_unit_average_usage"] = float(billing_avg)
                except (ValueError, TypeError):
                    pass
        
        if "usageDifference" in usage_insight:
            usage_diff = usage_insight.get("usageDifference")
            if usage_diff is not None:
                try:
                    attributes["usage_difference"] = float(usage_diff)
                except (ValueError, TypeError):
                    pass
        
        if "deviceModel" in usage_insight:
            attributes["device_model"] = usage_insight.get("deviceModel")
        
        return attributes
    
    @staticmethod
    def find_latest_valid_month(usage_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find the most recent month with totalEnergyUsage > 0 and averageEnergyUseForBillingUnit != null.
        
        Args:
            usage_data: Dictionary containing monthly energy usage data
            
        Returns:
            Most recent valid month dictionary if found, None otherwise
        """
        if not isinstance(usage_data, dict):
            return None
        
        monthly_usages = usage_data.get("monthlyEnergyUsages", [])
        if not monthly_usages:
            return None
        
        valid_months = []
        for month in monthly_usages:
            if not isinstance(month, dict):
                continue
            
            total_usage = month.get("totalEnergyUsage", 0)
            avg_usage = month.get("averageEnergyUseForBillingUnit")
            
            if (isinstance(total_usage, (int, float)) and float(total_usage) > 0 and 
                avg_usage is not None):
                month_year = month.get("monthYear", "")
                parsed = DataUtil.parse_month_year(month_year)
                if parsed:
                    month_num, year = parsed
                    sort_key = year * CALCULATION_YEAR_MONTH_SORT_MULTIPLIER + month_num
                    valid_months.append((sort_key, month))
        
        if valid_months:
            valid_months.sort(key=lambda x: x[0], reverse=True)
            return valid_months[0][1]
        
        return None
    
    @staticmethod
    def find_latest_month_with_data(usage_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find the most recent month with totalEnergyUsage > 0 (relaxed requirement).
        
        This is a fallback when find_latest_valid_month returns None because
        averageEnergyUseForBillingUnit is null (month not yet finalized).
        This method only requires totalEnergyUsage > 0, making it useful when
        months exist but haven't been finalized yet.
        
        Args:
            usage_data: Dictionary containing monthly energy usage data
            
        Returns:
            Most recent month with usage data if found, None otherwise
        """
        if not isinstance(usage_data, dict):
            return None
        
        monthly_usages = usage_data.get("monthlyEnergyUsages", [])
        if not monthly_usages:
            return None
        
        valid_months = []
        for month in monthly_usages:
            if not isinstance(month, dict):
                continue
            
            total_usage = month.get("totalEnergyUsage", 0)
            
            if isinstance(total_usage, (int, float)) and float(total_usage) > 0:
                month_year = month.get("monthYear", "")
                parsed = DataUtil.parse_month_year(month_year)
                if parsed:
                    month_num, year = parsed
                    sort_key = year * CALCULATION_YEAR_MONTH_SORT_MULTIPLIER + month_num
                    valid_months.append((sort_key, month))
        
        if valid_months:
            valid_months.sort(key=lambda x: x[0], reverse=True)
            return valid_months[0][1]
        
        return None
    
    @staticmethod
    def find_month_by_identifier(usage_data: Dict[str, Any], month_identifier: str) -> Optional[Dict[str, Any]]:
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
    
    @staticmethod
    def extract_device_readings_map(device_statuses: List[Dict[str, Any]]) -> Dict[str, float]:
        """Extract device readings as a map of deviceNumber to currentReadingValue.
        
        Args:
            device_statuses: List of device status dictionaries
            
        Returns:
            Dictionary mapping deviceNumber (string) to currentReadingValue (float)
            Returns empty dict on error or if no devices found
        """
        readings_map: Dict[str, float] = {}
        
        if not isinstance(device_statuses, list):
            return readings_map
        
        for device in device_statuses:
            if not isinstance(device, dict):
                continue
            
            device_number = device.get("deviceNumber")
            reading_value = device.get("currentReadingValue")
            
            if device_number is not None and reading_value is not None:
                try:
                    device_id = str(device_number)
                    reading = float(reading_value)
                    readings_map[device_id] = reading
                except (ValueError, TypeError):
                    continue
        
        return readings_map
    
    @staticmethod
    def calculate_per_device_usage(start_readings: Dict[str, float], end_readings: Dict[str, float]) -> List[Dict[str, Any]]:
        """Calculate per-device usage from start and end readings.
        
        Args:
            start_readings: Dictionary mapping deviceNumber to reading at start
            end_readings: Dictionary mapping deviceNumber to reading at end
            
        Returns:
            List of device dictionaries with id, start, and end readings
            Handles missing devices gracefully (only includes devices present in both)
        """
        devices_list: List[Dict[str, Any]] = []
        
        if not isinstance(start_readings, dict) or not isinstance(end_readings, dict):
            return devices_list
        
        all_device_ids = set(start_readings.keys()) | set(end_readings.keys())
        
        for device_id in all_device_ids:
            start_value = start_readings.get(device_id)
            end_value = end_readings.get(device_id)
            
            if start_value is not None and end_value is not None:
                try:
                    devices_list.append({
                        "id": device_id,
                        "start": float(start_value),
                        "end": float(end_value)
                    })
                except (ValueError, TypeError):
                    continue
        
        return devices_list

