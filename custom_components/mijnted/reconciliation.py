"""Reconcile published monthly totals with revisable per-device boundaries."""

import logging
import math
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from .const import BOUNDARY_RETRY_MAX_SECONDS, BOUNDARY_RETRY_SECONDS
from .sensors.models import (
    DeviceReading, MonthCacheEntry, MONTH_STATE_COMPLETE_READINGS,
)
from .utils import DateUtil
from .utils.readings import finite_usage, validated_readings

_LOGGER = logging.getLogger(__name__)


def published_usage(month: Dict[str, Any]) -> Optional[float]:
    """Recognize publication by a usable average, excluding placeholder zeroes."""
    if finite_usage(month.get("averageEnergyUseForBillingUnit")) is None:
        return None
    return finite_usage(month.get("totalEnergyUsage"))


def _defer(entry: MonthCacheEntry, now: datetime) -> None:
    """Persist bounded retry backoff without losing pending reconciliation."""
    entry.boundary_reconciled = False
    entry.boundary_retry_count = min(entry.boundary_retry_count + 1, 6)
    delay = min(BOUNDARY_RETRY_SECONDS * 2 ** (entry.boundary_retry_count - 1), BOUNDARY_RETRY_MAX_SECONDS)
    entry.boundary_retry_at = (now + timedelta(seconds=delay)).isoformat()


def _retry_due(entry: MonthCacheEntry, now: datetime) -> bool:
    """Determine whether pending boundary verification is due."""
    if not entry.boundary_retry_at:
        return True
    try:
        return datetime.fromisoformat(entry.boundary_retry_at).timestamp() <= now.timestamp()
    except (ValueError, TypeError):
        return True


async def _start_readings(api: Any, cache: Dict[str, MonthCacheEntry], entry: MonthCacheEntry,
                          ends: Dict[int, float], *, refresh: bool = False) -> Dict[int, float]:
    """Resolve real starts, fetching the preceding anchor when starts are missing."""
    if entry.month == 1:
        return {device_id: 0.0 for device_id in ends}
    starts = {device.id: device.start for device in entry.devices
              if finite_usage(device.start) is not None and not refresh}
    previous_month, previous_year = DateUtil.get_previous_month_from_date(
        DateUtil.get_first_day_of_month(entry.month, entry.year)
    )
    previous = cache.get(DateUtil.format_month_key(previous_year, previous_month))
    if previous and not refresh:
        for device in previous.devices:
            if finite_usage(device.end) is not None:
                starts.setdefault(device.id, device.end)
    if refresh or not ends.keys() <= starts.keys():
        rows = await api.get_device_statuses_for_date(DateUtil.get_last_day_of_month(previous_month, previous_year))
        refreshed = validated_readings(rows)
        starts.update(refreshed)
        if previous and any(device.id in refreshed and device.end != refreshed[device.id]
                            for device in previous.devices):
            previous.boundary_reconciled = False
            previous.boundary_retry_at = None
            previous.boundary_retry_count = 0
    return starts


def _repair_successor(cache: Dict[str, MonthCacheEntry], entry: MonthCacheEntry,
                      ends: Dict[int, float]) -> bool:
    """Carry verified closing readings into the next month's opening baseline."""
    next_date = DateUtil.get_last_day_of_month(entry.month, entry.year) + timedelta(days=1)
    if next_date.month == 1:
        return False  # Annual meter reset, not December's cumulative baseline.
    key = DateUtil.format_month_key(next_date.year, next_date.month)
    successor = cache.get(key)
    if not successor:
        return False
    existing = {device.id: device for device in successor.devices}
    devices = []
    for device_id in existing.keys() | ends.keys():
        old = existing.get(device_id)
        start = ends.get(device_id, old.start if old else None)
        end = old.end if old and old.end is not None else start
        if start is None or end is None:
            continue
        # Unobserved devices can still carry the earlier, stale closing value.
        end = max(start, end)
        devices.append(DeviceReading(id=device_id, start=start, end=end, usage=end - start))
    devices.sort(key=lambda device: device.id)
    changed = {device.id: device.start for device in devices} != {
        device.id: device.start for device in successor.devices
    }
    total = sum(device.usage for device in devices) if devices else None
    if total is None:
        total = successor.total_usage
    cache[key] = replace(
        successor, devices=devices, start_locked=True,
        total_usage=successor.published_usage if successor.published_usage is not None else total,
        boundary_reconciled=False if changed else successor.boundary_reconciled,
        boundary_retry_at=None if changed else successor.boundary_retry_at,
        boundary_retry_count=0 if changed else successor.boundary_retry_count,
    )
    return cache[key] != successor


async def async_reconcile_boundaries(api: Any, cache: Dict[str, MonthCacheEntry],
                                      last_update: Any, now: datetime) -> bool:
    """Reconcile historical boundaries from compatible dated readings."""
    source_date = DateUtil.parse_last_sync_date(last_update)
    if not source_date:
        return False
    modified = False
    for key in sorted(cache):
        entry = cache[key]
        if not isinstance(entry, MonthCacheEntry) or (entry.year, entry.month) >= (now.year, now.month):
            continue
        last_day = DateUtil.get_last_day_of_month(entry.month, entry.year)
        if source_date < last_day:
            continue
        if entry.boundary_reconciled:
            ends = {device.id: device.end for device in entry.devices
                    if finite_usage(device.end) is not None}
            if ends and _repair_successor(cache, entry, ends):
                modified = True
            continue
        if not _retry_due(entry, now):
            continue
        try:
            ends = validated_readings(await api.get_device_statuses_for_date(last_day))
            expected_devices = {device.id for device in entry.devices}
            if not ends or not expected_devices <= ends.keys():
                _defer(entry, now)
                modified = True
                continue
            starts = await _start_readings(api, cache, entry, ends)
            if not ends.keys() <= starts.keys():
                _defer(entry, now)
                modified = True
                continue
            calculated = sum(ends.values()) - sum(starts[device_id] for device_id in ends)
            invalid_opening = any(ends[device_id] < starts[device_id] for device_id in ends)
            publication_mismatch = entry.published_usage is not None and not math.isclose(
                calculated, entry.published_usage, rel_tol=0, abs_tol=1e-6,
            )
            if invalid_opening or publication_mismatch:
                starts = await _start_readings(api, cache, entry, ends, refresh=True)
                calculated = sum(ends.values()) - sum(starts.get(device_id, math.inf) for device_id in ends)
            if (any(ends[device_id] < starts.get(device_id, math.inf) for device_id in ends)
                    or (entry.published_usage is not None and not math.isclose(calculated, entry.published_usage, rel_tol=0, abs_tol=1e-6))):
                _defer(entry, now)
                modified = True
                continue
            devices = [DeviceReading(id=device_id, start=starts[device_id], end=ends[device_id],
                                     usage=ends[device_id] - starts[device_id]) for device_id in sorted(ends)]
            cache[key] = replace(
                entry, devices=devices, total_usage=entry.published_usage if entry.published_usage is not None else calculated,
                state=entry.state if entry.finalized else MONTH_STATE_COMPLETE_READINGS,
                boundary_reconciled=entry.published_usage is not None,
                boundary_retry_count=0, boundary_retry_at=None,
            )
            _repair_successor(cache, cache[key], ends)
            if entry.published_usage is None:
                # Keep provisional boundaries revisable while waiting for publication.
                cache[key].boundary_retry_at = (now + timedelta(seconds=BOUNDARY_RETRY_SECONDS)).isoformat()
            modified = True
        except Exception as err:
            _LOGGER.warning("Deferred boundary reconciliation for %s (%s)", key, type(err).__name__)
            _defer(entry, now)
            modified = True
    return modified
