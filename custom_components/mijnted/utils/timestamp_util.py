import logging
from typing import Optional
from datetime import datetime, timezone

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

