"""Tests for utils/data_util.py."""
from datetime import datetime
from unittest.mock import patch

import pytest

from custom_components.mijnted.utils.data_util import DataUtil


# ---------------------------------------------------------------------------
# safe_float / safe_int
# ---------------------------------------------------------------------------

class TestSafeFloat:
    def test_int_input(self):
        assert DataUtil.safe_float(42) == 42.0

    def test_float_input(self):
        assert DataUtil.safe_float(3.14) == 3.14

    def test_string_number(self):
        assert DataUtil.safe_float("2.5") == 2.5

    def test_none_returns_default(self):
        assert DataUtil.safe_float(None) is None

    def test_none_with_explicit_default(self):
        assert DataUtil.safe_float(None, default=0.0) == 0.0

    def test_bad_string(self):
        assert DataUtil.safe_float("abc") is None

    def test_bad_string_with_default(self):
        assert DataUtil.safe_float("abc", default=-1.0) == -1.0


class TestSafeInt:
    def test_int_input(self):
        assert DataUtil.safe_int(7) == 7

    def test_float_input(self):
        assert DataUtil.safe_int(7.9) == 7

    def test_string_number(self):
        assert DataUtil.safe_int("10") == 10

    def test_none_returns_default(self):
        assert DataUtil.safe_int(None) is None

    def test_none_with_default(self):
        assert DataUtil.safe_int(None, default=0) == 0

    def test_bad_string(self):
        assert DataUtil.safe_int("xyz") is None


# ---------------------------------------------------------------------------
# parse_month_year
# ---------------------------------------------------------------------------

class TestParseMonthYear:
    def test_valid(self):
        assert DataUtil.parse_month_year("11.2025") == (11, 2025)

    def test_single_digit_month(self):
        assert DataUtil.parse_month_year("3.2025") == (3, 2025)

    def test_invalid_format(self):
        assert DataUtil.parse_month_year("2025-11") is None

    def test_too_many_parts(self):
        assert DataUtil.parse_month_year("1.2.3") is None

    def test_empty(self):
        assert DataUtil.parse_month_year("") is None

    def test_non_numeric(self):
        assert DataUtil.parse_month_year("jan.2025") is None


# ---------------------------------------------------------------------------
# extract_month_number
# ---------------------------------------------------------------------------

class TestExtractMonthNumber:
    def test_valid(self):
        assert DataUtil.extract_month_number("11.2025") == 11

    def test_invalid(self):
        assert DataUtil.extract_month_number("bad") is None


# ---------------------------------------------------------------------------
# is_current_month
# ---------------------------------------------------------------------------

class TestIsCurrentMonth:
    @patch("custom_components.mijnted.utils.date_util.datetime")
    def test_current(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 11, 15)
        assert DataUtil.is_current_month("11.2025") is True

    @patch("custom_components.mijnted.utils.date_util.datetime")
    def test_not_current(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 11, 15)
        assert DataUtil.is_current_month("10.2025") is False

    def test_invalid_format(self):
        assert DataUtil.is_current_month("invalid") is False


# ---------------------------------------------------------------------------
# extract_usage_from_insight
# ---------------------------------------------------------------------------

class TestExtractUsageFromInsight:
    def test_valid_dict(self):
        assert DataUtil.extract_usage_from_insight({"usage": 42.5}) == 42.5

    def test_string_number(self):
        assert DataUtil.extract_usage_from_insight({"usage": "10"}) == 10.0

    def test_none_usage(self):
        assert DataUtil.extract_usage_from_insight({"usage": None}) is None

    def test_missing_usage_key(self):
        assert DataUtil.extract_usage_from_insight({"other": 1}) is None

    def test_non_dict(self):
        assert DataUtil.extract_usage_from_insight("not a dict") is None

    def test_invalid_usage_value(self):
        assert DataUtil.extract_usage_from_insight({"usage": "bad"}) is None


# ---------------------------------------------------------------------------
# calculate_filter_status_total
# ---------------------------------------------------------------------------

class TestCalculateFilterStatusTotal:
    def test_list_of_devices(self):
        devices = [
            {"currentReadingValue": 10},
            {"currentReadingValue": 20},
        ]
        assert DataUtil.calculate_filter_status_total(devices) == 30.0

    def test_list_with_zero_total(self):
        assert DataUtil.calculate_filter_status_total([{"currentReadingValue": 0}]) is None

    def test_list_skips_non_dicts(self):
        assert DataUtil.calculate_filter_status_total(["bad", {"currentReadingValue": 5}]) == 5.0

    def test_dict_with_filterStatus(self):
        assert DataUtil.calculate_filter_status_total({"filterStatus": 42}) == 42.0

    def test_dict_with_status(self):
        assert DataUtil.calculate_filter_status_total({"status": 7}) == 7.0

    def test_dict_zero_value(self):
        assert DataUtil.calculate_filter_status_total({"filterStatus": 0}) is None

    def test_dict_non_numeric(self):
        assert DataUtil.calculate_filter_status_total({"filterStatus": "abc"}) is None

    def test_numeric_positive(self):
        assert DataUtil.calculate_filter_status_total(15) == 15.0

    def test_numeric_zero(self):
        assert DataUtil.calculate_filter_status_total(0) is None

    def test_none_input(self):
        assert DataUtil.calculate_filter_status_total(None) is None


# ---------------------------------------------------------------------------
# extract_monthly_breakdown
# ---------------------------------------------------------------------------

class TestExtractMonthlyBreakdown:
    def test_basic(self):
        data = {
            "monthlyEnergyUsages": [
                {
                    "monthYear": "11.2025",
                    "totalEnergyUsage": 100,
                    "unitOfMeasurement": "kWh",
                    "averageEnergyUseForBillingUnit": 3.5,
                },
            ]
        }
        result = DataUtil.extract_monthly_breakdown(data)
        assert "11.2025" in result
        assert result["11.2025"]["total_energy_usage"] == 100.0
        assert result["11.2025"]["unit_of_measurement"] == "kWh"
        assert result["11.2025"]["average_energy_use_for_billing_unit"] == 3.5

    def test_empty_list(self):
        assert DataUtil.extract_monthly_breakdown({"monthlyEnergyUsages": []}) == {}

    def test_missing_key(self):
        assert DataUtil.extract_monthly_breakdown({"other": 1}) == {}

    def test_non_dict_input(self):
        assert DataUtil.extract_monthly_breakdown("bad") == {}

    def test_skips_entries_without_monthYear(self):
        data = {"monthlyEnergyUsages": [{"totalEnergyUsage": 50}]}
        assert DataUtil.extract_monthly_breakdown(data) == {}

    def test_skips_non_dict_entries(self):
        data = {"monthlyEnergyUsages": ["bad", {"monthYear": "1.2025", "totalEnergyUsage": 10}]}
        result = DataUtil.extract_monthly_breakdown(data)
        assert len(result) == 1

    def test_invalid_total_energy_usage(self):
        data = {"monthlyEnergyUsages": [{"monthYear": "1.2025", "totalEnergyUsage": "bad"}]}
        result = DataUtil.extract_monthly_breakdown(data)
        assert "1.2025" not in result


# ---------------------------------------------------------------------------
# extract_usage_insight_attributes
# ---------------------------------------------------------------------------

class TestExtractUsageInsightAttributes:
    def test_full_data(self):
        insight = {
            "unitType": "heat",
            "billingUnitAverageUsage": 50.0,
            "usageDifference": -5.0,
            "deviceModel": "ABC-123",
        }
        attrs = DataUtil.extract_usage_insight_attributes(insight)
        assert attrs["unit_type"] == "heat"
        assert attrs["billing_unit_average_usage"] == 50.0
        assert attrs["usage_difference"] == -5.0
        assert attrs["device_model"] == "ABC-123"

    def test_empty_dict(self):
        assert DataUtil.extract_usage_insight_attributes({}) == {}

    def test_non_dict(self):
        assert DataUtil.extract_usage_insight_attributes("bad") == {}

    def test_non_numeric_billing(self):
        attrs = DataUtil.extract_usage_insight_attributes({"billingUnitAverageUsage": "abc"})
        assert "billing_unit_average_usage" not in attrs


# ---------------------------------------------------------------------------
# find_latest_valid_month
# ---------------------------------------------------------------------------

class TestFindLatestValidMonth:
    def test_selects_latest(self):
        data = {
            "monthlyEnergyUsages": [
                {"monthYear": "9.2025", "totalEnergyUsage": 80, "averageEnergyUseForBillingUnit": 2.5},
                {"monthYear": "11.2025", "totalEnergyUsage": 100, "averageEnergyUseForBillingUnit": 3.5},
                {"monthYear": "10.2025", "totalEnergyUsage": 90, "averageEnergyUseForBillingUnit": 3.0},
            ]
        }
        result = DataUtil.find_latest_valid_month(data)
        assert result["monthYear"] == "11.2025"

    def test_skips_zero_usage(self):
        data = {
            "monthlyEnergyUsages": [
                {"monthYear": "11.2025", "totalEnergyUsage": 0, "averageEnergyUseForBillingUnit": 3.0},
                {"monthYear": "10.2025", "totalEnergyUsage": 90, "averageEnergyUseForBillingUnit": 3.0},
            ]
        }
        result = DataUtil.find_latest_valid_month(data)
        assert result["monthYear"] == "10.2025"

    def test_skips_null_average(self):
        data = {
            "monthlyEnergyUsages": [
                {"monthYear": "11.2025", "totalEnergyUsage": 100, "averageEnergyUseForBillingUnit": None},
                {"monthYear": "10.2025", "totalEnergyUsage": 80, "averageEnergyUseForBillingUnit": 2.5},
            ]
        }
        result = DataUtil.find_latest_valid_month(data)
        assert result["monthYear"] == "10.2025"

    def test_empty_list(self):
        assert DataUtil.find_latest_valid_month({"monthlyEnergyUsages": []}) is None

    def test_non_dict(self):
        assert DataUtil.find_latest_valid_month("bad") is None

    def test_no_valid_months(self):
        data = {
            "monthlyEnergyUsages": [
                {"monthYear": "11.2025", "totalEnergyUsage": 0, "averageEnergyUseForBillingUnit": None},
            ]
        }
        assert DataUtil.find_latest_valid_month(data) is None


# ---------------------------------------------------------------------------
# find_latest_month_with_data
# ---------------------------------------------------------------------------

class TestFindLatestMonthWithData:
    def test_selects_latest_with_usage(self):
        data = {
            "monthlyEnergyUsages": [
                {"monthYear": "9.2025", "totalEnergyUsage": 50},
                {"monthYear": "11.2025", "totalEnergyUsage": 100},
            ]
        }
        result = DataUtil.find_latest_month_with_data(data)
        assert result["monthYear"] == "11.2025"

    def test_ignores_average_requirement(self):
        """Unlike find_latest_valid_month, this should accept null averageEnergyUseForBillingUnit."""
        data = {
            "monthlyEnergyUsages": [
                {"monthYear": "11.2025", "totalEnergyUsage": 100},
            ]
        }
        result = DataUtil.find_latest_month_with_data(data)
        assert result is not None

    def test_skips_zero_usage(self):
        data = {
            "monthlyEnergyUsages": [
                {"monthYear": "11.2025", "totalEnergyUsage": 0},
                {"monthYear": "10.2025", "totalEnergyUsage": 50},
            ]
        }
        result = DataUtil.find_latest_month_with_data(data)
        assert result["monthYear"] == "10.2025"

    def test_non_dict(self):
        assert DataUtil.find_latest_month_with_data(42) is None


# ---------------------------------------------------------------------------
# find_month_by_identifier
# ---------------------------------------------------------------------------

class TestFindMonthByIdentifier:
    def test_found(self):
        data = {
            "monthlyEnergyUsages": [
                {"monthYear": "10.2025", "totalEnergyUsage": 80},
                {"monthYear": "11.2025", "totalEnergyUsage": 100},
            ]
        }
        result = DataUtil.find_month_by_identifier(data, "11.2025")
        assert result["totalEnergyUsage"] == 100

    def test_not_found(self):
        data = {"monthlyEnergyUsages": [{"monthYear": "10.2025"}]}
        assert DataUtil.find_month_by_identifier(data, "11.2025") is None

    def test_empty(self):
        assert DataUtil.find_month_by_identifier({"monthlyEnergyUsages": []}, "1.2025") is None

    def test_non_dict(self):
        assert DataUtil.find_month_by_identifier("bad", "1.2025") is None


# ---------------------------------------------------------------------------
# extract_device_readings_map
# ---------------------------------------------------------------------------

class TestExtractDeviceReadingsMap:
    def test_basic(self):
        statuses = [
            {"deviceNumber": "A1", "currentReadingValue": 100},
            {"deviceNumber": "B2", "currentReadingValue": 200},
        ]
        result = DataUtil.extract_device_readings_map(statuses)
        assert result == {"A1": 100.0, "B2": 200.0}

    def test_skips_missing_keys(self):
        statuses = [{"deviceNumber": "A1"}, {"currentReadingValue": 50}]
        assert DataUtil.extract_device_readings_map(statuses) == {}

    def test_skips_non_dicts(self):
        assert DataUtil.extract_device_readings_map(["bad"]) == {}

    def test_non_list_input(self):
        assert DataUtil.extract_device_readings_map("bad") == {}

    def test_non_numeric_reading(self):
        statuses = [{"deviceNumber": "A1", "currentReadingValue": "abc"}]
        assert DataUtil.extract_device_readings_map(statuses) == {}


# ---------------------------------------------------------------------------
# calculate_per_device_usage
# ---------------------------------------------------------------------------

class TestCalculatePerDeviceUsage:
    def test_matching_devices(self):
        start = {"1": 100.0, "2": 200.0}
        end = {"1": 150.0, "2": 280.0}
        result = DataUtil.calculate_per_device_usage(start, end)
        ids = {d["id"] for d in result}
        assert ids == {"1", "2"}
        for d in result:
            if d["id"] == "1":
                assert d["start"] == 100.0
                assert d["end"] == 150.0

    def test_device_only_in_start(self):
        """Device present only in start should be excluded."""
        result = DataUtil.calculate_per_device_usage({"1": 10.0}, {"2": 20.0})
        assert result == []

    def test_partial_overlap(self):
        start = {"1": 10.0, "2": 20.0}
        end = {"2": 30.0, "3": 40.0}
        result = DataUtil.calculate_per_device_usage(start, end)
        assert len(result) == 1
        assert result[0]["id"] == "2"

    def test_non_dict_inputs(self):
        assert DataUtil.calculate_per_device_usage("bad", "bad") == []

    def test_empty_maps(self):
        assert DataUtil.calculate_per_device_usage({}, {}) == []
