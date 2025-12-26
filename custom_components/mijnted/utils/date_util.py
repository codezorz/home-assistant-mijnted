from datetime import datetime


class DateUtil:
    """Utility class for date calculations."""
    
    @staticmethod
    def get_last_year() -> int:
        """Get the previous year.
        
        Returns:
            Previous year as integer (current year - 1)
        """
        return datetime.now().year - 1

