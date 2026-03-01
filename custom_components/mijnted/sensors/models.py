"""Data models for sensor data structures."""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class DeviceReading:
    """Represents a single device reading with start, end, and calculated usage.

    Attributes:
        id: Device identifier.
        start: Meter reading at the start of the period.
        end: Meter reading at the end of the period.
        usage: Calculated usage (end - start), or None if not computable.
    """
    id: int
    start: float
    end: float
    usage: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary with id, start, end, and usage keys.
        """
        return {
            "id": self.id,
            "start": self.start,
            "end": self.end,
            "usage": self.usage
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["DeviceReading"]:
        """Create DeviceReading from dictionary representation.
        
        Args:
            data: Dictionary with id, start, end, and optionally usage keys.
        
        Returns:
            DeviceReading instance or None if required keys are missing or invalid.
        """
        device_id = data.get("id")
        start_val = data.get("start")
        end_val = data.get("end")
        
        if device_id is None or start_val is None or end_val is None:
            return None
        
        try:
            return cls(
                id=int(device_id),
                start=float(start_val),
                end=float(end_val),
                usage=data.get("usage")
            )
        except (ValueError, TypeError):
            return None


@dataclass
class CurrentData:
    """Represents current month's usage data.

    Attributes:
        last_update_date: Date of the last update.
        month_id: Identifier for the month.
        start_date: Start date of the period.
        end_date: End date of the period.
        devices: List of device readings for this period.
        days: Number of days in the period, or None.
        last_year_usage: Usage from the same period last year, or None.
        last_year_average_usage: Average usage from last year, or None.
        total_usage_start: Total meter reading at period start, or None.
        total_usage_end: Total meter reading at period end, or None.
        total_usage: Total usage for the period, or None.
        average_usage_per_day: Average usage per day, or None.
    """
    last_update_date: str
    month_id: str
    start_date: str
    end_date: str
    devices: List[DeviceReading] = field(default_factory=list)
    days: Optional[int] = None
    last_year_usage: Optional[float] = None
    last_year_average_usage: Optional[float] = None
    total_usage_start: Optional[float] = None
    total_usage_end: Optional[float] = None
    total_usage: Optional[float] = None
    average_usage_per_day: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation, recursively converting nested dataclasses.
        
        Returns:
            Dictionary with all CurrentData fields including nested device readings.
        """
        return {
            "last_update_date": self.last_update_date,
            "month_id": self.month_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "devices": [device.to_dict() for device in self.devices],
            "days": self.days,
            "last_year_usage": self.last_year_usage,
            "last_year_average_usage": self.last_year_average_usage,
            "total_usage_start": self.total_usage_start,
            "total_usage_end": self.total_usage_end,
            "total_usage": self.total_usage,
            "average_usage_per_day": self.average_usage_per_day
        }
    
    def to_attributes_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation for sensor attributes, filtering out None values.
        
        Returns only the fields typically used in sensor attributes: month_id, start_date, end_date, days.
        None values are excluded to match the behavior of manual attribute extraction.
        """
        attributes: Dict[str, Any] = {}
        
        if self.month_id:
            attributes["month_id"] = self.month_id
        
        if self.start_date:
            attributes["start_date"] = self.start_date
        
        if self.end_date:
            attributes["end_date"] = self.end_date
        
        if self.days is not None:
            attributes["days"] = self.days
        
        return attributes


@dataclass
class HistoryData:
    """Represents historical month's usage data.

    Attributes:
        month_id: Identifier for the month.
        year: Year of the period.
        month: Month of the period.
        start_date: Start date of the period.
        end_date: End date of the period.
        average_usage: Average usage for the period, or None.
        devices: List of device readings for this period.
        days: Number of days in the period, or None.
        total_usage: Total usage for the period, or None.
        total_usage_start: Total meter reading at period start, or None.
        total_usage_end: Total meter reading at period end, or None.
        average_usage_per_day: Average usage per day, or None.
    """
    month_id: str
    year: int
    month: int
    start_date: str
    end_date: str
    average_usage: Optional[float]
    devices: List[DeviceReading] = field(default_factory=list)
    days: Optional[int] = None
    average_usage_per_day: Optional[float] = None
    total_usage_start: Optional[float] = None
    total_usage_end: Optional[float] = None
    total_usage: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation, recursively converting nested dataclasses.
        
        Returns:
            Dictionary with all HistoryData fields including nested device readings.
        """
        return {
            "month_id": self.month_id,
            "year": self.year,
            "month": self.month,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "average_usage": self.average_usage,
            "devices": [device.to_dict() for device in self.devices],
            "days": self.days,
            "average_usage_per_day": self.average_usage_per_day,
            "total_usage_start": self.total_usage_start,
            "total_usage_end": self.total_usage_end,
            "total_usage": self.total_usage
        }
    
    def to_attributes_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation for sensor attributes, filtering out None/empty values.
        
        Returns only the month_id field typically used in sensor attributes.
        None/empty values are excluded to match the behavior of manual attribute extraction.
        """
        attributes: Dict[str, Any] = {}
        
        if self.month_id:
            attributes["month_id"] = self.month_id
        
        return attributes


@dataclass
class StatisticsTracking:
    """Tracks the last injected month key per sensor type for statistics injection.

    Attributes:
        monthly_usage: Last injected month key for monthly usage sensor, or None.
        last_year_monthly_usage: Last injected month key for last year monthly usage, or None.
        average_monthly_usage: Last injected month key for average monthly usage, or None.
        last_year_average_monthly_usage: Last injected month key for last year average, or None.
        total_usage: Last injected month key for total usage sensor, or None.
    """
    monthly_usage: Optional[str] = None
    last_year_monthly_usage: Optional[str] = None
    average_monthly_usage: Optional[str] = None
    last_year_average_monthly_usage: Optional[str] = None
    total_usage: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary with all StatisticsTracking keys.
        """
        return {
            "monthly_usage": self.monthly_usage,
            "last_year_monthly_usage": self.last_year_monthly_usage,
            "average_monthly_usage": self.average_monthly_usage,
            "last_year_average_monthly_usage": self.last_year_average_monthly_usage,
            "total_usage": self.total_usage
        }


@dataclass
class MonthCacheEntry:
    """Represents a month's cache entry for persistent storage.

    Attributes:
        month_id: Identifier for the month.
        year: Year of the period.
        month: Month of the period.
        start_date: Start date of the period.
        end_date: End date of the period.
        total_usage: Total usage for the period, or None.
        average_usage: Average usage for the period, or None.
        devices: List of device readings (stored as dicts when serialized).
        finalized: Whether the month's data is finalized.
    """
    month_id: str
    year: int
    month: int
    start_date: str
    end_date: str
    total_usage: Optional[float]
    average_usage: Optional[float]
    devices: List[DeviceReading] = field(default_factory=list)
    finalized: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation for storage.
        
        Returns:
            Dictionary with month_id, year, month, dates, usage, devices, finalized.
        """
        return {
            "month_id": self.month_id,
            "year": self.year,
            "month": self.month,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_usage": self.total_usage,
            "average_usage": self.average_usage,
            "devices": [device.to_dict() for device in self.devices],
            "finalized": self.finalized
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MonthCacheEntry":
        """Create MonthCacheEntry from dictionary representation.
        
        Args:
            data: Dictionary with month_id, year, month, dates, usage, devices, finalized.
        
        Returns:
            MonthCacheEntry instance.
        """
        devices = []
        devices_data = data.get("devices", [])
        if isinstance(devices_data, list):
            for device_dict in devices_data:
                if isinstance(device_dict, dict):
                    device = DeviceReading.from_dict(device_dict)
                    if device:
                        devices.append(device)
        
        return cls(
            month_id=data.get("month_id", ""),
            year=data.get("year", 0),
            month=data.get("month", 0),
            start_date=data.get("start_date", ""),
            end_date=data.get("end_date", ""),
            total_usage=data.get("total_usage"),
            average_usage=data.get("average_usage"),
            devices=devices,
            finalized=data.get("finalized", False)
        )