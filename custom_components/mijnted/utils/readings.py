"""Validated meter readings for published monthly reconciliation."""

import math
from typing import Any, Dict, Optional

from .data_util import DataUtil


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
