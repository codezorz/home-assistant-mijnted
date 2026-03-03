"""Tests for sensors/models.py dataclasses."""
import pytest

from custom_components.mijnted.sensors.models import (
    MONTH_STATE_COMPLETE_READINGS,
    MONTH_STATE_FINALIZED,
    MONTH_STATE_OPEN,
    VALID_MONTH_STATES,
    CurrentData,
    DeviceReading,
    HistoryData,
    MonthCacheEntry,
    StatisticsTracking,
)


# ---------------------------------------------------------------------------
# DeviceReading
# ---------------------------------------------------------------------------

class TestDeviceReading:
    def test_to_dict(self):
        dr = DeviceReading(id=1, start=100.0, end=150.0, usage=50.0)
        assert dr.to_dict() == {"id": 1, "start": 100.0, "end": 150.0, "usage": 50.0}

    def test_to_dict_usage_none(self):
        dr = DeviceReading(id=2, start=0.0, end=10.0)
        assert dr.to_dict()["usage"] is None

    def test_from_dict_valid(self):
        dr = DeviceReading.from_dict({"id": 3, "start": 10, "end": 20, "usage": 10})
        assert dr is not None
        assert dr.id == 3
        assert dr.start == 10.0
        assert dr.end == 20.0
        assert dr.usage == 10

    def test_from_dict_without_usage(self):
        dr = DeviceReading.from_dict({"id": 1, "start": 5, "end": 15})
        assert dr is not None
        assert dr.usage is None

    def test_from_dict_missing_id(self):
        assert DeviceReading.from_dict({"start": 0, "end": 1}) is None

    def test_from_dict_missing_start(self):
        assert DeviceReading.from_dict({"id": 1, "end": 1}) is None

    def test_from_dict_missing_end(self):
        assert DeviceReading.from_dict({"id": 1, "start": 0}) is None

    def test_from_dict_invalid_types(self):
        assert DeviceReading.from_dict({"id": "abc", "start": "x", "end": "y"}) is None

    def test_from_dict_empty(self):
        assert DeviceReading.from_dict({}) is None

    def test_roundtrip(self):
        original = DeviceReading(id=7, start=200.0, end=250.0, usage=50.0)
        restored = DeviceReading.from_dict(original.to_dict())
        assert restored is not None
        assert restored.id == original.id
        assert restored.start == original.start
        assert restored.end == original.end
        assert restored.usage == original.usage


# ---------------------------------------------------------------------------
# CurrentData
# ---------------------------------------------------------------------------

class TestCurrentData:
    def _make(self, **overrides):
        defaults = dict(
            last_update_date="2025-11-15",
            month_id="2025-11",
            start_date="2025-11-01",
            end_date="2025-11-15",
        )
        defaults.update(overrides)
        return CurrentData(**defaults)

    def test_to_dict_minimal(self):
        cd = self._make()
        d = cd.to_dict()
        assert d["last_update_date"] == "2025-11-15"
        assert d["month_id"] == "2025-11"
        assert d["devices"] == []
        assert d["total_usage"] is None

    def test_to_dict_with_devices(self):
        cd = self._make(devices=[DeviceReading(id=1, start=0, end=10)])
        d = cd.to_dict()
        assert len(d["devices"]) == 1
        assert d["devices"][0]["id"] == 1

    def test_to_attributes_dict_all_populated(self):
        cd = self._make(days=15)
        attrs = cd.to_attributes_dict()
        assert attrs == {
            "month_id": "2025-11",
            "start_date": "2025-11-01",
            "end_date": "2025-11-15",
            "days": 15,
        }

    def test_to_attributes_dict_omits_none(self):
        cd = self._make()
        attrs = cd.to_attributes_dict()
        assert "days" not in attrs

    def test_to_attributes_dict_omits_empty_strings(self):
        cd = self._make(month_id="", start_date="", end_date="")
        assert cd.to_attributes_dict() == {}


# ---------------------------------------------------------------------------
# HistoryData
# ---------------------------------------------------------------------------

class TestHistoryData:
    def _make(self, **overrides):
        defaults = dict(
            month_id="2025-10",
            year=2025,
            month=10,
            start_date="2025-10-01",
            end_date="2025-10-31",
            average_usage=5.5,
        )
        defaults.update(overrides)
        return HistoryData(**defaults)

    def test_to_dict(self):
        hd = self._make(total_usage=120.0)
        d = hd.to_dict()
        assert d["year"] == 2025
        assert d["month"] == 10
        assert d["total_usage"] == 120.0
        assert d["devices"] == []

    def test_to_attributes_dict_with_id(self):
        assert self._make().to_attributes_dict() == {"month_id": "2025-10"}

    def test_to_attributes_dict_empty_id(self):
        assert self._make(month_id="").to_attributes_dict() == {}


# ---------------------------------------------------------------------------
# StatisticsTracking
# ---------------------------------------------------------------------------

class TestStatisticsTracking:
    def test_default_all_none(self):
        st = StatisticsTracking()
        d = st.to_dict()
        assert all(v is None for v in d.values())
        assert len(d) == 5

    def test_to_dict_with_values(self):
        st = StatisticsTracking(monthly_usage="2025-11", total_usage="2025-10")
        d = st.to_dict()
        assert d["monthly_usage"] == "2025-11"
        assert d["total_usage"] == "2025-10"
        assert d["average_monthly_usage"] is None


# ---------------------------------------------------------------------------
# MonthCacheEntry
# ---------------------------------------------------------------------------

class TestMonthCacheEntry:
    def _make(self, **overrides):
        defaults = dict(
            month_id="2025-10",
            year=2025,
            month=10,
            start_date="2025-10-01",
            end_date="2025-10-31",
            total_usage=100.0,
            average_usage=3.3,
        )
        defaults.update(overrides)
        return MonthCacheEntry(**defaults)

    def test_to_dict(self):
        entry = self._make(finalized=True, state=MONTH_STATE_FINALIZED)
        d = entry.to_dict()
        assert d["finalized"] is True
        assert d["state"] == MONTH_STATE_FINALIZED
        assert d["start_locked"] is False

    def test_to_dict_with_devices(self):
        entry = self._make(devices=[DeviceReading(id=1, start=0, end=5)])
        assert len(entry.to_dict()["devices"]) == 1

    # -- from_dict ---------------------------------------------------------

    def test_from_dict_minimal(self):
        entry = MonthCacheEntry.from_dict({
            "month_id": "2025-09",
            "year": 2025,
            "month": 9,
            "start_date": "2025-09-01",
            "end_date": "2025-09-30",
            "total_usage": 80.0,
            "average_usage": 2.7,
        })
        assert entry.month_id == "2025-09"
        assert entry.finalized is False
        assert entry.state == MONTH_STATE_OPEN
        assert entry.start_locked is False

    def test_from_dict_finalized_overrides_state(self):
        """When finalized=True, state should be forced to FINALIZED."""
        entry = MonthCacheEntry.from_dict({
            "month_id": "x", "year": 2025, "month": 1,
            "start_date": "", "end_date": "",
            "total_usage": None, "average_usage": None,
            "finalized": True,
            "state": MONTH_STATE_OPEN,
        })
        assert entry.finalized is True
        assert entry.state == MONTH_STATE_FINALIZED

    def test_from_dict_valid_state_preserved(self):
        entry = MonthCacheEntry.from_dict({
            "month_id": "x", "year": 2025, "month": 2,
            "start_date": "", "end_date": "",
            "total_usage": None, "average_usage": None,
            "finalized": False,
            "state": MONTH_STATE_COMPLETE_READINGS,
        })
        assert entry.state == MONTH_STATE_COMPLETE_READINGS

    def test_from_dict_invalid_state_defaults_to_open(self):
        entry = MonthCacheEntry.from_dict({
            "month_id": "x", "year": 2025, "month": 3,
            "start_date": "", "end_date": "",
            "total_usage": None, "average_usage": None,
            "state": "BOGUS",
        })
        assert entry.state == MONTH_STATE_OPEN

    def test_from_dict_with_devices(self):
        entry = MonthCacheEntry.from_dict({
            "month_id": "x", "year": 2025, "month": 4,
            "start_date": "", "end_date": "",
            "total_usage": None, "average_usage": None,
            "devices": [
                {"id": 1, "start": 10, "end": 20},
                {"id": 2, "start": 30, "end": 40, "usage": 10},
            ],
        })
        assert len(entry.devices) == 2
        assert entry.devices[0].id == 1
        assert entry.devices[1].usage == 10

    def test_from_dict_skips_invalid_devices(self):
        entry = MonthCacheEntry.from_dict({
            "month_id": "x", "year": 2025, "month": 5,
            "start_date": "", "end_date": "",
            "total_usage": None, "average_usage": None,
            "devices": [
                {"id": 1, "start": 0, "end": 5},
                "not a dict",
                {"bad": "keys"},
            ],
        })
        assert len(entry.devices) == 1

    def test_from_dict_start_locked(self):
        entry = MonthCacheEntry.from_dict({
            "month_id": "x", "year": 2025, "month": 6,
            "start_date": "", "end_date": "",
            "total_usage": None, "average_usage": None,
            "start_locked": True,
        })
        assert entry.start_locked is True

    def test_roundtrip(self):
        original = self._make(
            finalized=True,
            state=MONTH_STATE_FINALIZED,
            start_locked=True,
            devices=[DeviceReading(id=1, start=10, end=20, usage=10)],
        )
        restored = MonthCacheEntry.from_dict(original.to_dict())
        assert restored.month_id == original.month_id
        assert restored.finalized == original.finalized
        assert restored.state == original.state
        assert restored.start_locked == original.start_locked
        assert len(restored.devices) == 1
        assert restored.devices[0].id == 1


# ---------------------------------------------------------------------------
# Month state constants
# ---------------------------------------------------------------------------

class TestMonthStateConstants:
    def test_valid_states_set(self):
        assert VALID_MONTH_STATES == {
            MONTH_STATE_OPEN,
            MONTH_STATE_COMPLETE_READINGS,
            MONTH_STATE_FINALIZED,
        }
