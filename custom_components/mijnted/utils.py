"""Utility functions for MijnTed integration."""
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timezone
from homeassistant.core import HomeAssistant
from .const import YEAR_MONTH_SORT_MULTIPLIER
import logging

_LOGGER = logging.getLogger(__name__)


class TimestampUtil:
    """Utility class for timestamp formatting."""
    
    @staticmethod
    def parse_date_to_timestamp(date_str: str) -> Optional[str]:
        """Convert date string to ISO 8601 timestamp.
        
        Args:
            date_str: Date string in DD/MM/YYYY format or ISO 8601 format
            
        Returns:
            ISO 8601 timestamp string (YYYY-MM-DDTHH:MM:SSZ) or None if parsing fails
        """
        if not date_str or not isinstance(date_str, str):
            return None
        
        date_str = date_str.strip()
        if not date_str:
            return None
        
        # Check if already in ISO 8601 format
        if "T" in date_str or date_str.count("-") >= 2:
            try:
                # Try to parse as ISO format
                if date_str.endswith("Z"):
                    return date_str
                # Try parsing various ISO formats
                for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"]:
                    try:
                        parsed = datetime.strptime(date_str, fmt)
                        return parsed.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
                    except ValueError:
                        continue
            except (ValueError, AttributeError):
                pass
        
        # Try DD/MM/YYYY format
        try:
            date_obj = datetime.strptime(date_str, "%d/%m/%Y")
            # Convert to ISO 8601 format (midnight UTC)
            return date_obj.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
        except (ValueError, AttributeError):
            _LOGGER.debug(
                "Failed to parse date string: %s",
                date_str,
                extra={"date_string": date_str, "date_length": len(date_str) if date_str else 0}
            )
            return None
    
    @staticmethod
    def format_datetime_to_timestamp(dt: datetime) -> str:
        """Convert datetime object to ISO 8601 timestamp string.
        
        Args:
            dt: Datetime object (timezone-aware or naive)
            
        Returns:
            ISO 8601 timestamp string (YYYY-MM-DDTHH:MM:SSZ)
        """
        # Convert to UTC if timezone-aware, then make naive
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.replace(microsecond=0).isoformat() + "Z"


class ApiUtil:
    """Utility class for API response parsing."""
    
    @staticmethod
    def extract_value(data: Any, default: Any = None) -> Any:
        """Extract value from API response that may be wrapped in {"value": "..."} format.
        
        Args:
            data: API response data (dict, string, or other)
            default: Default value to return if extraction fails
            
        Returns:
            Extracted value or default
        """
        if isinstance(data, dict):
            return data.get("value", default)
        if data is not None:
            return str(data) if data else default
        return default


class DataUtil:
    """Utility class for data parsing and extraction."""
    
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
            if len(parts) == 2:
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
            # Sum all currentReadingValue from all devices
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
            
            # Store all available fields
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
                    # Create a sortable key (year * YEAR_MONTH_SORT_MULTIPLIER + month)
                    sort_key = year * YEAR_MONTH_SORT_MULTIPLIER + month_num
                    valid_months.append((sort_key, month))
        
        # Sort by date descending (most recent first) and return the first valid one
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


class TranslationUtil:
    """Utility class for translations."""
    
    @staticmethod
    async def async_translate_room_code(room_code: str, hass: Optional[HomeAssistant] = None) -> str:
        """Translate room codes to full room names using Home Assistant's translation system.
        
        Args:
            room_code: Room code to translate (e.g., "KA", "W")
            hass: Home Assistant instance for translations (optional)
            
        Returns:
            Translated room name or original code if translation not found
        """
        if hass:
            try:
                # Use Home Assistant's translation system
                from homeassistant.helpers import translation
                
                # Get the current language
                language = hass.config.language or "en"
                
                # Load translations for the integration
                # Use the domain name for translation loading
                from .const import DOMAIN
                translations = await translation.async_get_translations(
                    hass, "entity", language, [DOMAIN]
                )
                
                # Try to get translation from integration translation files
                # Format: "component.mijnted.room_codes.KA" or similar
                translation_key = f"room_codes.{room_code}"
                if translation_key in translations:
                    translated = translations[translation_key]
                    if translated and translated != translation_key:
                        return translated
                
                # Also try direct access to room_codes in translations
                if "room_codes" in translations:
                    room_translations = translations.get("room_codes", {})
                    if isinstance(room_translations, dict) and room_code in room_translations:
                        return room_translations[room_code]
            except Exception:
                # Fall through to fallback translations
                pass
        
        # Fallback to hardcoded translations
        room_translations = {
            "KA": "bedroom",
            "W": "living room",
        }
        return room_translations.get(room_code, room_code)
    
    @staticmethod
    def translate_room_code(room_code: str, hass: Optional[HomeAssistant] = None) -> str:
        """Translate room codes to full room names using Home Assistant's translation system.
        
        This is a synchronous version that uses already-loaded translations from hass.data.
        For async contexts where translations may need to be loaded, use async_translate_room_code().
        
        Args:
            room_code: Room code to translate (e.g., "KA", "W")
            hass: Home Assistant instance for translations (optional)
            
        Returns:
            Translated room name or original code if translation not found
        """
        if hass:
            try:
                from .const import DOMAIN
                
                # Get the current language
                language = hass.config.language or "en"
                
                # Try to get translations from already-loaded translation data
                # Check frontend_translations first (most common)
                translations_data = hass.data.get("frontend_translations", {})
                if language in translations_data:
                    translations = translations_data[language]
                    
                    # Try various translation key formats
                    translation_keys = [
                        f"component.{DOMAIN}.entity.sensor.room_codes.{room_code}",
                        f"component.{DOMAIN}.room_codes.{room_code}",
                        f"room_codes.{room_code}",
                    ]
                    
                    for key in translation_keys:
                        if key in translations:
                            translated = translations[key]
                            if translated and translated != key:
                                return translated
                    
                    # Also try direct access to room_codes
                    if "room_codes" in translations:
                        room_translations = translations.get("room_codes", {})
                        if isinstance(room_translations, dict) and room_code in room_translations:
                            return room_translations[room_code]
                
                # Try entity_translations
                entity_translations = hass.data.get("entity_translations", {})
                if language in entity_translations:
                    domain_translations = entity_translations[language].get(DOMAIN, {})
                    if "room_codes" in domain_translations:
                        room_translations = domain_translations["room_codes"]
                        if isinstance(room_translations, dict) and room_code in room_translations:
                            return room_translations[room_code]
            except Exception:
                # Fall through to fallback translations
                pass
        
        # Fallback to hardcoded translations
        room_translations = {
            "KA": "bedroom",
            "W": "living room",
        }
        return room_translations.get(room_code, room_code)


class DateUtil:
    """Utility class for date calculations."""
    
    @staticmethod
    def get_last_year() -> int:
        """Get the previous year.
        
        Returns:
            Previous year as integer (current year - 1)
        """
        return datetime.now().year - 1


class ListUtil:
    """Utility class for list operations."""
    
    @staticmethod
    def get_first_item(items: Any) -> Optional[Any]:
        """Safely get the first item from a list.
        
        Args:
            items: List or any other type
            
        Returns:
            First item if items is a non-empty list, None otherwise
        """
        if isinstance(items, list) and len(items) > 0:
            return items[0]
        return None
