from typing import Any


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

