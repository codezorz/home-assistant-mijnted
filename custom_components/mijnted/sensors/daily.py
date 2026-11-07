"""Daily report projections and graph exports owned by Published usage."""

from datetime import date, datetime, time
from typing import Any, Dict

from homeassistant.components.recorder.models import StatisticData, StatisticMetaData, StatisticMeanType
from homeassistant.util import dt as dt_util

from .base import MijnTedSensor
from ..const import DOMAIN, UNIT_MIJNTED
from ..utils.readings import finite_usage


def reported_daily_values(data: Dict[str, Any]) -> Dict[str, float]:
    """Validate dated observations without projecting a lagging value onto today."""
    values = {}
    today = dt_util.now().date()
    for day, raw in data.get("daily_usage", {}).items():
        try:
            parsed = date.fromisoformat(day)
        except (ValueError, TypeError):
            continue
        value = finite_usage(raw)
        if parsed <= today and value is not None:
            values[day] = value
    return values


def daily_statistic_id(entry_id: str) -> str:
    """Return the report's stable daily statistic identity."""
    return f"{DOMAIN}:{entry_id.lower()}_reported_daily_usage"


async def async_import_daily_statistics(sensor: MijnTedSensor) -> None:
    """Upsert forward daily totals at local reading-date midnight, without an entity."""
    if not sensor._validate_statistics_injection():
        return
    values = reported_daily_values(sensor.coordinator.data or {})
    if not values:
        return
    metadata = StatisticMetaData(
        source=DOMAIN, statistic_id=daily_statistic_id(sensor._entry_id),
        name="Reported daily usage", mean_type=StatisticMeanType.ARITHMETIC,
        has_sum=False, unit_of_measurement=UNIT_MIJNTED, unit_class=None,
    )
    rows = [StatisticData(
        start=datetime.combine(date.fromisoformat(day), time.min, dt_util.get_default_time_zone()),
        mean=value,
    ) for day, value in sorted(values.items())]
    await sensor._async_safe_import_statistics(metadata, rows, external=True)
