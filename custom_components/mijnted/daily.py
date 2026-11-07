"""Forward-only dated consumption derived from newly received meter readings."""

import logging
from datetime import date, datetime
from typing import Any, Dict

from homeassistant.helpers.storage import Store

from .const import DAILY_HISTORY_DAYS, DOMAIN, STORAGE_VERSION
from .utils.readings import finite_usage, validated_readings
from .utils import DateUtil

_LOGGER = logging.getLogger(__name__)


class DailyUsageTracker:
    """Persist two dated checkpoints and the daily results observed since setup.

    No historical endpoint is queried. A first observation or a gap only seeds a
    checkpoint; a daily result requires consecutive dates and matching devices.
    """

    def __init__(self, hass: Any, entry_id: str) -> None:
        """Use entry-scoped storage separate from resettable monthly cache."""
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_daily_{entry_id}")
        self._loaded = False
        self._dirty = False
        self._checkpoints: Dict[str, Dict[int, float]] = {}
        self._results: Dict[str, float] = {}

    async def _async_load(self) -> bool:
        """Restore only validated forward observations and daily values."""
        if self._loaded:
            return True
        try:
            stored = await self._store.async_load()
            if stored is None:
                self._loaded = True
                return True
            if not isinstance(stored, dict):
                _LOGGER.warning("Could not restore daily usage (invalid payload)")
                return False
            checkpoints = {}
            results = {}
            for day, readings in stored.get("checkpoints", {}).items():
                date.fromisoformat(day)
                rows = [{"deviceNumber": key, "currentReadingValue": value}
                        for key, value in readings.items()]
                values = validated_readings(rows)
                if values:
                    checkpoints[day] = values
            for day, total in stored.get("results", {}).items():
                date.fromisoformat(day)
                value = finite_usage(total)
                if value is not None:
                    results[day] = value
            self._checkpoints = checkpoints
            self._results = results
            self._prune()
            self._loaded = True
            return True
        except Exception as err:
            _LOGGER.warning("Could not restore daily usage (%s)", type(err).__name__)
            return False

    def _prune(self) -> None:
        """Bound persisted observations and the import window."""
        self._checkpoints = {day: self._checkpoints[day] for day in sorted(self._checkpoints)[-2:]}
        self._results = {day: self._results[day] for day in sorted(self._results)[-DAILY_HISTORY_DAYS:]}

    def _payload(self) -> Dict[str, float]:
        """Return a detached snapshot so recorder listeners cannot mutate tracking."""
        return dict(self._results)

    async def _async_result(self) -> Dict[str, float]:
        """Retry unsaved observations even when the API response is unchanged."""
        if self._dirty:
            try:
                checkpoints = {day: {str(device_id): value for device_id, value in readings.items()}
                               for day, readings in self._checkpoints.items()}
                await self._store.async_save({"checkpoints": checkpoints, "results": self._results})
                self._dirty = False
            except Exception as err:
                _LOGGER.warning("Could not persist daily usage (%s)", type(err).__name__)
        return self._payload()

    @property
    def reading_snapshot(self) -> Dict[str, Any]:
        """Expose the latest complete dated observation for reading-month reporting."""
        if not self._checkpoints:
            return {}
        latest = max(self._checkpoints)
        return {"date": latest, "readings": dict(self._checkpoints[latest])}

    async def async_update(self, last_update: Any, rows: Any, now: datetime,
                           expected_devices: set[int]) -> Dict[str, float]:
        """Record a complete new dated observation, or a revision to its latest date."""
        if not await self._async_load():
            return self._payload()
        day = DateUtil.parse_last_sync_date(last_update)
        readings = validated_readings(rows)
        if not day or day > now.date() or not readings or not expected_devices <= readings.keys():
            return await self._async_result()
        key = day.isoformat()
        latest = max(self._checkpoints, default="")
        if latest and not self._checkpoints[latest].keys() <= readings.keys():
            # Keep a known meter from disappearing just because the monthly
            # endpoint/cache is also unavailable during a partial outage.
            return await self._async_result()
        if key < latest or self._checkpoints.get(key) == readings:
            return await self._async_result()
        if key == latest:
            if readings.keys() != self._checkpoints[key].keys():
                return await self._async_result()
            older = [value for old_key, value in self._checkpoints.items() if old_key < key]
            if older and not (day.month == 1 and day.day == 1):
                previous = older[0]
                if readings.keys() == previous.keys() and any(readings[device_id] < value for device_id, value in previous.items()):
                    return await self._async_result()
        self._checkpoints[key] = readings
        self._prune()
        if len(self._checkpoints) == 2:
            previous_key, current_key = sorted(self._checkpoints)
            previous = self._checkpoints[previous_key]
            current = self._checkpoints[current_key]
            consecutive = (date.fromisoformat(current_key) - date.fromisoformat(previous_key)).days == 1
            if consecutive and previous.keys() == current.keys():
                is_year_reset = day.month == 1 and day.day == 1
                deltas = [end if is_year_reset else end - previous[device_id]
                          for device_id, end in current.items()]
                if all(value >= 0 for value in deltas):
                    self._results[current_key] = sum(deltas)
        self._prune()
        self._dirty = True
        return await self._async_result()
