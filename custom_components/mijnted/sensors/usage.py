from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import math
from homeassistant.components.sensor import SensorStateClass
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.components.recorder.models import StatisticData, StatisticMeanType
from homeassistant.util import dt as dt_util
from .base import MijnTedSensor
from .daily import async_import_daily_statistics, daily_statistic_id, reported_daily_values
from ..utils import DataUtil, DateUtil
from ..utils.readings import finite_usage
from ..const import DEFAULT_NAME, UNIT_MIJNTED, DEFAULT_START_VALUE


class MijnTedMonthlyUsageSensor(MijnTedSensor):
    """Sensor for monthly usage extracted from coordinator data.

    Displays the current month's energy usage calculated from total usage start/end.

    Args:
        coordinator: DataUpdateCoordinator providing MijnTed API data.
    """
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]], entry_id: str, config_name: str = DEFAULT_NAME) -> None:
        """Initialize the monthly usage sensor.
        
        Args:
            coordinator: Data update coordinator
            entry_id: Config entry ID used to scope entity identity
            config_name: User-configured device name
        """
        super().__init__(coordinator, "monthly_usage", "monthly_usage", entry_id, config_name=config_name)
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_suggested_display_precision = 0
        self._last_known_month: Optional[str] = None
        self._cancel_month_timer = None

    async def async_added_to_hass(self) -> None:
        """Refresh the calendar projection at local midnight without an API poll."""
        await super().async_added_to_hass()
        self._schedule_month_rollover()
        self.async_on_remove(self._remove_month_timer)

    def _remove_month_timer(self) -> None:
        """Cancel the outstanding local calendar callback on unload."""
        if self._cancel_month_timer:
            self._cancel_month_timer()
            self._cancel_month_timer = None

    def _schedule_month_rollover(self) -> None:
        """Schedule exactly the next HA-local month boundary."""
        self._remove_month_timer()
        now = dt_util.now()
        next_month = (now.replace(day=28) + timedelta(days=4)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0,
        )
        self._cancel_month_timer = async_track_point_in_time(self.hass, self._month_rollover, next_month)

    @callback
    def _month_rollover(self, now: datetime) -> None:
        """Write the new month's zero and import its provisional graph sample."""
        self._cancel_month_timer = None
        self.async_write_ha_state()
        self.hass.async_create_task(self._async_inject_statistics())
        self._schedule_month_rollover()

    @property
    def state(self) -> Optional[float]:
        """Return the state calculated from current data.
        
        Returns:
            Monthly usage value, or last known value if unavailable
        """
        now = dt_util.now()
        month_key = DateUtil.format_month_key(now.year, now.month)
        changed_month = self._last_known_month is not None and self._last_known_month != month_key
        if self._last_known_month != month_key:
            self._last_known_value = 0.0 if changed_month else None
            self._last_known_month = month_key
        data = self.coordinator.data or {}
        source_date = DateUtil.parse_last_sync_date(data.get("last_update"))
        if source_date and (source_date.year, source_date.month) < (now.year, now.month):
            self._update_last_known_value(0.0)
            return 0.0
        current = self._build_current_data()
        if not current:
            cached = data.get("monthly_history_cache", {}).get(month_key)
            cached_date = DateUtil.parse_last_sync_date(self._extract_value_from_cache_entry(cached, "end_date"))
            if cached_date and (cached_date.year, cached_date.month) < (now.year, now.month):
                self._update_last_known_value(0.0)
                return 0.0
            value = DataUtil.safe_float(self._extract_value_from_cache_entry(cached, "total_usage"))
            if (self._last_known_value is None or changed_month) and cached_date and cached_date <= now.date() and value is not None and math.isfinite(value) and value >= 0:
                self._update_last_known_value(value)
            return self._last_known_value
        
        if not current.last_update_date:
            return self._last_known_value
        
        data = self.coordinator.data
        filter_status = data.get("filter_status") if data is not None else None
        if not filter_status and self._last_known_value is not None:
            return self._last_known_value

        value = self._calculate_usage_from_start_end(
            current.total_usage_start,
            current.total_usage_end,
            current.month_id
        )
        
        if value is None and current.total_usage is not None:
            value = DataUtil.safe_float(current.total_usage)
        
        if value is None:
            return self._last_known_value

        if value == 0 and not filter_status and self._last_known_value is not None:
            return self._last_known_value

        self._update_last_known_value(value)
        return value

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant
        """
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class.
        
        Returns:
            SensorStateClass.TOTAL for cumulative measurements
        """
        return SensorStateClass.TOTAL

    async def _async_inject_statistics(self) -> None:
        """Import entity statistics and upsert consumption-month aggregates."""
        await self._async_inject_monthly_usage_statistics()
        await self._build_statistics_from_history(
            "total_usage", StatisticMeanType.NONE, include_current=True,
            current_value_calculator=lambda current: self.state,
        )
    

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing current data attributes
        """
        current = self._build_current_data()
        attributes = {"monthly_statistic_id": self._get_monthly_statistic_id()}
        if current:
            attributes.update(current.to_attributes_dict())
        else:
            now = dt_util.now()
            attributes["month_id"] = DateUtil.format_month_year_key(now.month, now.year)
        return attributes


class MijnTedPublishedUsageSensor(MijnTedSensor):
    """Show the latest available reading month's own usage and export report series."""

    _attr_translation_key = "published_usage"

    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]], entry_id: str,
                 config_name: str = DEFAULT_NAME) -> None:
        """Create the retrospective entity without automatic statistics collection."""
        super().__init__(coordinator, "published_usage", "published_usage", entry_id, config_name=config_name)
        self._attr_icon = "mdi:calendar-check"
        self._attr_suggested_display_precision = 0

    @property
    def state_class(self) -> None:
        """Keep publication-time observations outside monthly graph statistics."""
        return None

    async def _async_inject_statistics(self) -> None:
        """Export all reporting series independently of standalone view entities."""
        await self._async_inject_monthly_usage_statistics()
        await self._async_inject_monthly_usage_statistics(year_offset=1, series_key="last_year_monthly_usage")
        await self._async_inject_average_statistics(series_key="average_monthly_usage")
        await self._async_inject_average_statistics(year_offset=1, series_key="last_year_average_monthly_usage")
        await async_import_daily_statistics(self)

    @property
    def state(self) -> Optional[float]:
        """Return the coordinator's reading-month total without a calendar reset."""
        report = (self.coordinator.data or {}).get("reading_report") or {}
        return finite_usage(report.get("value"))

    @property
    def unit_of_measurement(self) -> str:
        """Return the same units as the current-month usage entity."""
        return UNIT_MIJNTED

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Expose own reading-period metadata and route independently selectable graphs."""
        attributes = {
            "monthly_statistic_id": self._get_monthly_statistic_id(),
            "daily_statistic_id": daily_statistic_id(self._entry_id),
        }
        report = (self.coordinator.data or {}).get("reading_report") or {}
        own_metadata = ("month_id", "reading_date", "start_date", "end_date",
                        "value_source", "start_locked", "boundary_reconciled")
        attributes.update({key: report[key] for key in own_metadata if key in report})
        daily = reported_daily_values(self.coordinator.data or {})
        if daily:
            latest = max(daily)
            attributes["reported_daily_date"] = latest
            attributes["reported_daily_usage"] = daily[latest]
        return attributes


class MijnTedLastYearMonthlyUsageSensor(MijnTedSensor):
    """Sensor for last year's monthly usage extracted from coordinator data.

    Displays the usage for the same month last year (e.g. March 2024 when current is March 2025).

    Args:
        coordinator: DataUpdateCoordinator providing MijnTed API data.
    """
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]], entry_id: str, config_name: str = DEFAULT_NAME) -> None:
        """Initialize the last year monthly usage sensor.
        
        Args:
            coordinator: Data update coordinator
            entry_id: Config entry ID used to scope entity identity
            config_name: User-configured device name
        """
        super().__init__(coordinator, "last_year_monthly_usage", "last_year_monthly_usage", entry_id, config_name=config_name)
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_suggested_display_precision = 0

    @property
    def state(self) -> Optional[float]:
        """Return the last year usage for the current month's corresponding month from last year.
        
        Returns:
            Last year's monthly usage value, or last known value if unavailable
        """
        return self._read_comparison_value("total_usage")

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant
        """
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class.
        
        Returns:
            SensorStateClass.TOTAL for cumulative measurements
        """
        return SensorStateClass.TOTAL

    async def _async_inject_statistics(self) -> None:
        """Import entity comparison states and external monthly comparison totals."""
        await self._async_inject_monthly_usage_statistics(year_offset=1)
        await self._async_inject_last_year_statistics("total_usage", "last_year_usage", StatisticMeanType.NONE)
    

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing month_id and last_year_month_id attributes
        """
        return {**self._build_month_id_attributes(), "monthly_statistic_id": self._get_monthly_statistic_id()}


class MijnTedAverageMonthlyUsageSensor(MijnTedSensor):
    """Sensor for average monthly usage extracted from coordinator history data.

    Displays the latest available average from history, skipping current month if average is None.

    Args:
        coordinator: DataUpdateCoordinator providing MijnTed API data.
    """
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]], entry_id: str, config_name: str = DEFAULT_NAME) -> None:
        """Initialize the average monthly usage sensor.
        
        Args:
            coordinator: Data update coordinator
            entry_id: Config entry ID used to scope entity identity
            config_name: User-configured device name
        """
        super().__init__(coordinator, "average_monthly_usage", "average_monthly_usage", entry_id, config_name=config_name)
        self._attr_icon = "mdi:chart-line"
        self._attr_suggested_display_precision = 0

    @property
    def state(self) -> Optional[float]:
        """Return the latest available average from history, skipping current month if average is None.
        
        Returns:
            Average monthly usage value, or None if not available
        """
        history = self._build_history_data()
        
        for entry in history:
            avg_usage = entry.average_usage
            if avg_usage is not None:
                value = DataUtil.safe_float(avg_usage)
                if value is not None:
                    return value
        
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant
        """
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> None:
        """Disable automatic statistics for this retrospective live value."""
        return None

    async def _async_inject_statistics(self) -> None:
        """Backfill and correct monthly averages in their external series."""
        await self._async_inject_average_statistics()
    
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Monthly graph statistic ID and attributes of the latest average period
        """
        attributes = {"monthly_statistic_id": self._get_average_statistic_id()}
        history = self._build_history_data()
        for entry in history:
            if entry.average_usage is not None:
                attributes.update(entry.to_attributes_dict())
                break
        return attributes


class MijnTedLastYearAverageMonthlyUsageSensor(MijnTedSensor):
    """Sensor for last year's average monthly usage extracted from coordinator data.

    Displays the average usage for the same month last year.

    Args:
        coordinator: DataUpdateCoordinator providing MijnTed API data.
    """
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]], entry_id: str, config_name: str = DEFAULT_NAME) -> None:
        """Initialize the last year average monthly usage sensor.
        
        Args:
            coordinator: Data update coordinator
            entry_id: Config entry ID used to scope entity identity
            config_name: User-configured device name
        """
        super().__init__(coordinator, "last_year_average_monthly_usage", "last_year_average_monthly_usage", entry_id, config_name=config_name)
        self._attr_icon = "mdi:chart-line-variant"
        self._attr_suggested_display_precision = 0

    @property
    def state(self) -> Optional[float]:
        """Return the last year average usage for the current month's corresponding month from last year.
        
        Returns:
            Last year's average monthly usage value, or last known value if unavailable
        """
        return self._read_comparison_value("average_usage")

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant
        """
        return UNIT_MIJNTED
    
    @property
    def state_class(self) -> None:
        """Disable automatic statistics for this retrospective live value."""
        return None

    async def _async_inject_statistics(self) -> None:
        """Backfill and correct last-year averages in their external series."""
        await self._async_inject_average_statistics(year_offset=1)
    

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Monthly graph statistic ID, month_id and last_year_month_id attributes
        """
        return {
            **self._build_month_id_attributes(),
            "monthly_statistic_id": self._get_average_statistic_id(),
        }


class MijnTedTotalUsageSensor(MijnTedSensor):
    """Sensor for total device readings from all devices.

    Displays the sum of current reading values from all devices in filter_status.

    Args:
        coordinator: DataUpdateCoordinator providing MijnTed API data.
    """
    
    def __init__(self, coordinator: DataUpdateCoordinator[Dict[str, Any]], entry_id: str, config_name: str = DEFAULT_NAME) -> None:
        """Initialize the total usage sensor.
        
        Args:
            coordinator: Data update coordinator
            entry_id: Config entry ID used to scope entity identity
            config_name: User-configured device name
        """
        super().__init__(coordinator, "total_usage", "total_usage", entry_id, config_name=config_name)
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_suggested_display_precision = 0

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor.
        
        Returns:
            Sum of all device readings, or last known value if unavailable
        """
        data = self.coordinator.data
        if not data:
            return self._last_known_value
        
        filter_status = data.get('filter_status')
        total = DataUtil.calculate_filter_status_total(filter_status)
        if total is not None:
            self._update_last_known_value(total)
            return total
        
        return self._last_known_value

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement.
        
        Returns:
            Unit string constant
        """
        return UNIT_MIJNTED
    
    def _collect_total_usage_entries(self, history: List[Any]) -> List[Dict[str, Any]]:
        """Collect and validate history entries for total usage statistics injection."""
        seen_periods: set[str] = set()
        entries = []
        for entry in history:
            total_usage_end = entry.total_usage_end
            if total_usage_end is None:
                continue

            start_date = entry.start_date
            month_id = entry.month_id

            if not start_date or not month_id:
                continue

            if month_id in seen_periods:
                continue

            stat_time = self._parse_start_date_to_datetime(start_date)
            if not stat_time:
                continue

            usage_value = DataUtil.safe_float(total_usage_end)
            if usage_value is None:
                continue

            month_num = entry.month
            if not isinstance(month_num, int):
                try:
                    parsed = DataUtil.parse_month_year(month_id)
                    month_num = parsed[0] if parsed else None
                except (ValueError, TypeError):
                    month_num = None

            seen_periods.add(month_id)
            entries.append({
                "stat_time": stat_time,
                "state": usage_value,
                "month_id": month_id,
                "month": month_num
            })

        entries.sort(key=lambda x: x["stat_time"])
        return entries

    async def _async_inject_statistics(self) -> None:
        """Inject total usage statistics into recorder from history."""
        history = self._build_history_data()
        if not history:
            return

        if not self._validate_statistics_injection():
            return

        entries_to_inject = self._collect_total_usage_entries(history)
        if not entries_to_inject:
            return

        cumulative_sum = DEFAULT_START_VALUE
        previous_total_usage_end = None
        statistics = []
        max_month_key = None

        for entry in entries_to_inject:
            current_total_usage_end = entry["state"]

            if entry["month"] == 1:
                delta = current_total_usage_end
            elif previous_total_usage_end is not None:
                delta = current_total_usage_end - previous_total_usage_end
            else:
                delta = current_total_usage_end

            cumulative_sum += delta

            stat_time = entry["stat_time"]
            statistics.append(
                StatisticData(
                    start=stat_time,
                    state=current_total_usage_end,
                    sum=cumulative_sum
                )
            )
            previous_total_usage_end = current_total_usage_end
            max_month_key = self._update_max_month_key(stat_time, max_month_key)

        await self._finalize_statistics_injection(statistics, StatisticMeanType.NONE, max_month_key, has_sum=True)
    

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes.
        
        Returns:
            Dictionary containing aligned current/history month payloads
        """
        attributes: Dict[str, Any] = {}
        
        current_readings = self._build_current_data()
        historical_readings_list = self._build_history_data()
        
        if current_readings is not None:
            attributes["current"] = current_readings.to_month_payload()
        if historical_readings_list:
            attributes["history"] = [entry.to_month_payload() for entry in historical_readings_list]
        
        return attributes
