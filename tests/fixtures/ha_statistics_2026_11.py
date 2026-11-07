# SPDX-License-Identifier: Apache-2.0
# Copyright The Home Assistant Authors.
"""Unmodified pure reducer functions from Home Assistant Core 2026.11.0.

Source: https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/components/recorder/statistics.py
License: https://github.com/home-assistant/core/blob/2026.11.0/LICENSE.md

Only imports/type aliases are supplied locally, allowing the actual reducer to
run without HA's database/runtime dependencies. Keep function bodies upstream.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from functools import lru_cache, partial
from itertools import chain
import math
from typing import Literal

from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.util import dt as dt_util

StatisticsRow = dict
StatisticMetaData = dict
DEG_TO_RAD = math.pi / 180
RAD_TO_DEG = 180 / math.pi


def mean(values):
    """Return the mean of a nonempty list (same helper as upstream)."""
    return sum(values) / len(values)


def weighted_circular_mean(values):
    """Return weighted circular mean and weight (same arithmetic as upstream)."""
    weighted_sin_sum, weighted_cos_sum = 0.0, 0.0
    for x, weight in values:
        rad_x = x * DEG_TO_RAD
        weighted_sin_sum += math.sin(rad_x) * weight
        weighted_cos_sum += math.cos(rad_x) * weight
    return (
        (RAD_TO_DEG * math.atan2(weighted_sin_sum, weighted_cos_sum)) % 360,
        math.sqrt(weighted_sin_sum**2 + weighted_cos_sum**2),
    )


def _reduce_statistic(
    statistic_id: str,
    stat_list: list[StatisticsRow],
    same_period: Callable[[float, float], bool],
    period_start_end: Callable[[float], tuple[float, float]],
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
    metadata: dict[str, tuple[int, StatisticMetaData]],
) -> list[StatisticsRow]:
    """Reduce the hourly statistics of one statistic to daily or monthly."""
    result: list[StatisticsRow] = []
    _want_mean = "mean" in types
    _want_min = "min" in types
    _want_max = "max" in types
    _want_last_reset = "last_reset" in types
    _want_state = "state" in types
    _want_sum = "sum" in types
    max_values: list[float] = []
    mean_values: list[tuple[float, float]] = []
    min_values: list[float] = []
    prev_stat: StatisticsRow = stat_list[0]
    # A fixed offset could land inside a period lengthened by DST
    fake_entry: StatisticsRow = {"start": period_start_end(stat_list[-1]["start"])[1]}

    # Loop over the hourly statistics + a fake entry to end the period
    for statistic in chain(stat_list, (fake_entry,)):
        if not same_period(prev_stat["start"], statistic["start"]):
            start, end = period_start_end(prev_stat["start"])
            # The previous statistic was the last entry of the period
            row: StatisticsRow = {
                "start": start,
                "end": end,
            }
            if _want_mean:
                row["mean"] = None
                row["mean_weight"] = None
                if mean_values:
                    match metadata[statistic_id][1]["mean_type"]:
                        case StatisticMeanType.ARITHMETIC:
                            row["mean"] = mean([x[0] for x in mean_values])
                        case StatisticMeanType.CIRCULAR:
                            row["mean"], row["mean_weight"] = weighted_circular_mean(
                                mean_values
                            )
                mean_values.clear()
            if _want_min:
                row["min"] = min(min_values) if min_values else None
                min_values.clear()
            if _want_max:
                row["max"] = max(max_values) if max_values else None
                max_values.clear()
            if _want_last_reset:
                row["last_reset"] = prev_stat.get("last_reset")
            if _want_state:
                row["state"] = prev_stat.get("state")
            if _want_sum:
                row["sum"] = prev_stat["sum"]
            result.append(row)
        if _want_max and (_max := statistic.get("max")) is not None:
            max_values.append(_max)
        if _want_mean:
            if (_mean := statistic.get("mean")) is not None:
                _mean_weight = statistic.get("mean_weight") or 0.0
                mean_values.append((_mean, _mean_weight))
        if _want_min and (_min := statistic.get("min")) is not None:
            min_values.append(_min)
        prev_stat = statistic

    return result


def _find_month_end_time(timestamp: datetime) -> datetime:
    """Return the end of the month (midnight at the first day of the next month)."""
    # We add 4 days to the end to make sure we are in the next month
    return (timestamp.replace(day=28) + timedelta(days=4)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )


def reduce_month_ts_factory() -> tuple[
    Callable[[float, float], bool],
    Callable[[float], tuple[float, float]],
]:
    """Return functions to match same month and month start end."""
    _lower_bound: float = 0
    _upper_bound: float = 0

    # We have to recreate _local_from_timestamp in the closure
    # in case the timezone changes
    _local_from_timestamp = partial(
        datetime.fromtimestamp, tz=dt_util.get_default_time_zone()
    )

    def _same_month_ts(time1: float, time2: float) -> bool:
        """Return True if time1 and time2 are in the same year and month."""
        nonlocal _lower_bound, _upper_bound
        if not _lower_bound <= time1 < _upper_bound:
            _lower_bound, _upper_bound = _month_start_end_ts_cached(time1)
        return _lower_bound <= time2 < _upper_bound

    def _month_start_end_ts(time: float) -> tuple[float, float]:
        """Return the start and end of the period (month) time is within."""
        start_local = _local_from_timestamp(time).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        end_local = _find_month_end_time(start_local)
        return (start_local.timestamp(), end_local.timestamp())

    # We create _month_start_end_ts_cached in the closure in case the timezone changes
    _month_start_end_ts_cached = lru_cache(maxsize=6)(_month_start_end_ts)

    return _same_month_ts, _month_start_end_ts_cached
