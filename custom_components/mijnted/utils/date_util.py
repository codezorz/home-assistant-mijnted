from calendar import monthrange
from datetime import date, datetime
from typing import Any, List, Optional, Tuple

from ..const import (
    API_DATE_FORMAT,
    API_LAST_SYNC_DATE_FORMAT,
    DISPLAY_MONTH_YEAR_FORMAT,
)


class DateUtil:
    """Utility class for date calculations."""
    
    @staticmethod
    def get_last_year() -> int:
        """Get the previous year.
        
        Returns:
            Previous year as integer (current year - 1)
        """
        return datetime.now().year - 1
    
    @staticmethod
    def get_previous_month() -> Tuple[int, int]:
        """Get the previous month (month before current month).
        
        Returns:
            Tuple of (month, year) for the previous month
        """
        now = datetime.now()
        if now.month == 1:
            return (12, now.year - 1)
        return (now.month - 1, now.year)
    
    @staticmethod
    def get_first_day_of_month(month: int, year: int) -> date:
        """Get the first day of a specific month.
        
        Args:
            month: Month number (1-12)
            year: Year number
            
        Returns:
            Date object for the 1st of the specified month
        """
        return date(year, month, 1)
    
    @staticmethod
    def get_last_day_of_month(month: int, year: int) -> date:
        """Get the last day of a specific month.
        
        Args:
            month: Month number (1-12)
            year: Year number
            
        Returns:
            Date object for the last day of the specified month
        """
        _, last_day = monthrange(year, month)
        return date(year, month, last_day)
    
    @staticmethod
    def format_date_for_api(target_date: date) -> str:
        """Format a date object as YYYY-MM-DD string for API calls.
        
        Args:
            target_date: Date object to format
            
        Returns:
            Date string in YYYY-MM-DD format
        """
        return target_date.strftime(API_DATE_FORMAT)
    
    @staticmethod
    def get_last_n_months(n: int) -> List[Tuple[int, int]]:
        """Get list of (month, year) tuples for the last N months from today.
        
        Args:
            n: Number of months to retrieve
            
        Returns:
            List of (month, year) tuples, most recent first
        """
        now = datetime.now()
        months = []
        current_month = now.month
        current_year = now.year
        
        for i in range(n):
            month = current_month - i
            year = current_year
            
            while month <= 0:
                month += 12
                year -= 1
            
            months.append((month, year))
        
        return months
    
    @staticmethod
    def get_last_n_months_from_date(n: int, from_date: date) -> List[Tuple[int, int]]:
        """Get list of (month, year) tuples for the last N months from a specific date.
        
        Args:
            n: Number of months to retrieve
            from_date: Date to calculate backwards from
            
        Returns:
            List of (month, year) tuples, most recent first
        """
        months = []
        current_month = from_date.month
        current_year = from_date.year
        
        for i in range(n):
            month = current_month - i
            year = current_year
            
            while month <= 0:
                month += 12
                year -= 1
            
            months.append((month, year))
        
        return months
    
    @staticmethod
    def is_current_month(month: int, year: int) -> bool:
        """Return True if the given month and year are the current month and year."""
        now = datetime.now()
        return month == now.month and year == now.year

    @staticmethod
    def get_previous_month_from_date(from_date: date) -> Tuple[int, int]:
        """Get the previous month (month before) from a specific date.
        
        Args:
            from_date: Date to calculate previous month from
            
        Returns:
            Tuple of (month, year) for the previous month
        """
        if from_date.month == 1:
            return (12, from_date.year - 1)
        return (from_date.month - 1, from_date.year)
    
    @staticmethod
    def format_month_key(year: int, month: int) -> str:
        """Format year and month as "YYYY-MM" key string.
        
        Args:
            year: Year number
            month: Month number (1-12)
            
        Returns:
            Month key string in "YYYY-MM" format
        """
        return f"{year}-{month:02d}"
    
    @staticmethod
    def parse_last_sync_date(last_update: Any) -> Optional[date]:
        """Parse last_sync_date from API response to date object.
        
        Args:
            last_update: Last update data from API (dict, string, or other)
            
        Returns:
            Date object if parsing successful, None otherwise
        """
        if not last_update:
            return None
        
        date_str = None
        if isinstance(last_update, dict):
            date_str = last_update.get("lastSyncDate") or last_update.get("date")
        elif isinstance(last_update, str):
            date_str = last_update
        
        if not date_str:
            return None
        
        try:
            return datetime.strptime(date_str, API_LAST_SYNC_DATE_FORMAT).date()
        except (ValueError, TypeError):
            pass
        
        try:
            return datetime.strptime(date_str, API_DATE_FORMAT).date()
        except (ValueError, TypeError):
            pass
        
        return None
    
    @staticmethod
    def calculate_days_between(start_date_str: str, end_date_str: str) -> Optional[int]:
        """Calculate number of days between two date strings (inclusive).
        
        Args:
            start_date_str: Start date string in YYYY-MM-DD format
            end_date_str: End date string in YYYY-MM-DD format
            
        Returns:
            Number of days (inclusive, so includes both start and end days), or None if parsing fails
        """
        if not start_date_str or not end_date_str:
            return None
        
        try:
            start_date_obj = datetime.strptime(start_date_str, API_DATE_FORMAT).date()
            end_date_obj = datetime.strptime(end_date_str, API_DATE_FORMAT).date()
            days = (end_date_obj - start_date_obj).days + 1
            return days if days > 0 else None
        except (ValueError, TypeError, AttributeError):
            return None
    
    @staticmethod
    def format_month_name(month: int, year: int) -> Optional[str]:
        """Format month and year as "MonthName YYYY" (e.g., "November 2025").
        
        Args:
            month: Month number (1-12)
            year: Year number
            
        Returns:
            Formatted string like "November 2025", or None if invalid
        """
        if not (1 <= month <= 12) or not year:
            return None
        
        try:
            month_date = datetime(year, month, 1)
            return month_date.strftime(DISPLAY_MONTH_YEAR_FORMAT)
        except (ValueError, TypeError):
            return None

