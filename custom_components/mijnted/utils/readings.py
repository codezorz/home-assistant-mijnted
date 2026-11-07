"""Validation shared by monthly reconciliation and forward daily tracking."""

import math
from typing import Any, Dict, Optional

from .data_util import DataUtil
from .date_util import DateUtil


def finite_usage(value: Any) -> Optional[float]:
    """Return a finite, nonnegative usage or reading, including valid zero."""
    number = DataUtil.safe_float(value)
    return number if number is not None and math.isfinite(number) and number >= 0 else None


def validated_readings(rows: Any) -> Dict[int, float]:
    """Reject malformed, nonfinite, or duplicate devices in a reading response."""
    if not isinstance(rows, list) or not rows:
        return {}
    readings: Dict[int, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            return {}
        device_id = DataUtil.safe_int(row.get("deviceNumber"))
        value = finite_usage(row.get("currentReadingValue"))
        if device_id is None or value is None or device_id in readings:
            return {}
        readings[device_id] = value
    return readings


def build_reading_report(snapshot: Dict[str, Any], month: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Resolve a dated month-to-date report from a complete received observation.

    The reporting month follows the reading date, never the calendar date. At a
    month's last day, a published monthly total supersedes provisional readings.
    """
    reading_date = DateUtil.parse_last_sync_date(snapshot.get("date"))
    if not reading_date:
        return None
    raw_readings = snapshot.get("readings", {})
    ends = validated_readings([
        {"deviceNumber": key, "currentReadingValue": value} for key, value in raw_readings.items()
    ])
    if not ends:
        return None
    if month and (month.get("year"), month.get("month")) != (reading_date.year, reading_date.month):
        return None
    starts = {}
    expected = set()
    for device in month.get("devices", []):
        device_id = DataUtil.safe_int(device.get("id"))
        if device_id is None:
            continue
        expected.add(device_id)
        start = finite_usage(device.get("start"))
        if start is not None:
            starts[device_id] = start
    if not expected <= ends.keys():
        return None
    if reading_date.month == 1:
        starts = {device_id: 0.0 for device_id in ends}
    published = finite_usage(month.get("published_usage"))
    is_month_end = reading_date == DateUtil.get_last_day_of_month(reading_date.month, reading_date.year)
    if published is not None and is_month_end:
        value, source = published, "published"
    else:
        if not ends.keys() <= starts.keys() or any(ends[key] < starts[key] for key in ends):
            return None
        value = sum(ends.values()) - sum(starts[key] for key in ends)
        source = "reported"
    return {
        "value": value,
        "month_id": DateUtil.format_month_year_key(reading_date.month, reading_date.year),
        "reading_date": reading_date.isoformat(),
        "start_date": reading_date.replace(day=1).isoformat(),
        "end_date": reading_date.isoformat(),
        "value_source": source,
        "start_locked": bool(month.get("start_locked", False)) or reading_date.month == 1,
        "boundary_reconciled": bool(month.get("boundary_reconciled", False)),
    }
