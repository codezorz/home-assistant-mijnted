"""Data models for sensor data structures."""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class DeviceReading:
    """Represents a single device reading with start, end, and calculated usage."""
    id: int
    start: float
    end: float
    usage: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "start": self.start,
            "end": self.end,
            "usage": self.usage
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["DeviceReading"]:
        """Create DeviceReading from dictionary representation."""
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
    """Represents current month's usage data."""
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
        """Convert to dictionary representation, recursively converting nested dataclasses."""
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
    """Represents historical month's usage data."""
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
        """Convert to dictionary representation, recursively converting nested dataclasses."""
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
    """Represents statistics tracking data - last month key injected per sensor type."""
    monthly_usage: Optional[str] = None
    last_year_monthly_usage: Optional[str] = None
    average_monthly_usage: Optional[str] = None
    last_year_average_monthly_usage: Optional[str] = None
    total_usage: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "monthly_usage": self.monthly_usage,
            "last_year_monthly_usage": self.last_year_monthly_usage,
            "average_monthly_usage": self.average_monthly_usage,
            "last_year_average_monthly_usage": self.last_year_average_monthly_usage,
            "total_usage": self.total_usage
        }


@dataclass
class MonthCacheEntry:
    """Represents a month's cache entry for persistent storage."""
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
        """Convert to dictionary representation for storage."""
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
        """Create MonthCacheEntry from dictionary representation."""
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