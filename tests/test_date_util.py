"""Tests for utils/date_util.py."""
from datetime import date, datetime
from unittest.mock import patch

import pytest

from custom_components.mijnted.utils.date_util import DateUtil


class TestGetLastYear:
    @patch("custom_components.mijnted.utils.date_util.datetime")
    def test_returns_previous_year(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 6, 15)
        assert DateUtil.get_last_year() == 2024


class TestGetPreviousMonth:
    @patch("custom_components.mijnted.utils.date_util.datetime")
    def test_mid_year(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 7, 10)
        assert DateUtil.get_previous_month() == (6, 2025)

    @patch("custom_components.mijnted.utils.date_util.datetime")
    def test_january_wraps_to_december(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 1, 5)
        assert DateUtil.get_previous_month() == (12, 2024)


class TestGetFirstDayOfMonth:
    def test_regular(self):
        assert DateUtil.get_first_day_of_month(3, 2025) == date(2025, 3, 1)

    def test_february(self):
        assert DateUtil.get_first_day_of_month(2, 2024) == date(2024, 2, 1)


class TestGetLastDayOfMonth:
    def test_31_day_month(self):
        assert DateUtil.get_last_day_of_month(1, 2025) == date(2025, 1, 31)

    def test_30_day_month(self):
        assert DateUtil.get_last_day_of_month(4, 2025) == date(2025, 4, 30)

    def test_february_non_leap(self):
        assert DateUtil.get_last_day_of_month(2, 2025) == date(2025, 2, 28)

    def test_february_leap(self):
        assert DateUtil.get_last_day_of_month(2, 2024) == date(2024, 2, 29)


class TestFormatDateForApi:
    def test_format(self):
        assert DateUtil.format_date_for_api(date(2025, 11, 3)) == "2025-11-03"

    def test_single_digit_month_day(self):
        assert DateUtil.format_date_for_api(date(2025, 1, 5)) == "2025-01-05"


class TestGetLastNMonths:
    @patch("custom_components.mijnted.utils.date_util.datetime")
    def test_three_months(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 3, 15)
        result = DateUtil.get_last_n_months(3)
        assert result == [(3, 2025), (2, 2025), (1, 2025)]

    @patch("custom_components.mijnted.utils.date_util.datetime")
    def test_crosses_year_boundary(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 2, 10)
        result = DateUtil.get_last_n_months(4)
        assert result == [(2, 2025), (1, 2025), (12, 2024), (11, 2024)]

    @patch("custom_components.mijnted.utils.date_util.datetime")
    def test_zero_months(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 6, 1)
        assert DateUtil.get_last_n_months(0) == []

    @patch("custom_components.mijnted.utils.date_util.datetime")
    def test_single_month(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 1, 1)
        assert DateUtil.get_last_n_months(1) == [(1, 2025)]


class TestGetLastNMonthsFromDate:
    def test_mid_year(self):
        result = DateUtil.get_last_n_months_from_date(3, date(2025, 5, 20))
        assert result == [(5, 2025), (4, 2025), (3, 2025)]

    def test_crosses_year_boundary(self):
        result = DateUtil.get_last_n_months_from_date(3, date(2025, 1, 15))
        assert result == [(1, 2025), (12, 2024), (11, 2024)]

    def test_zero(self):
        assert DateUtil.get_last_n_months_from_date(0, date(2025, 6, 1)) == []


class TestIsCurrentMonth:
    @patch("custom_components.mijnted.utils.date_util.datetime")
    def test_matches(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 11, 15)
        assert DateUtil.is_current_month(11, 2025) is True

    @patch("custom_components.mijnted.utils.date_util.datetime")
    def test_different_month(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 11, 15)
        assert DateUtil.is_current_month(10, 2025) is False

    @patch("custom_components.mijnted.utils.date_util.datetime")
    def test_different_year(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 11, 15)
        assert DateUtil.is_current_month(11, 2024) is False


class TestGetPreviousMonthFromDate:
    def test_regular(self):
        assert DateUtil.get_previous_month_from_date(date(2025, 5, 20)) == (4, 2025)

    def test_january_wraps(self):
        assert DateUtil.get_previous_month_from_date(date(2025, 1, 10)) == (12, 2024)


class TestFormatMonthKey:
    def test_two_digit_month(self):
        assert DateUtil.format_month_key(2025, 11) == "2025-11"

    def test_single_digit_month_padded(self):
        assert DateUtil.format_month_key(2025, 3) == "2025-03"


class TestParseLastSyncDate:
    def test_dict_with_lastSyncDate(self):
        result = DateUtil.parse_last_sync_date({"lastSyncDate": "15/11/2025"})
        assert result == date(2025, 11, 15)

    def test_dict_with_date_key(self):
        result = DateUtil.parse_last_sync_date({"date": "2025-11-15"})
        assert result == date(2025, 11, 15)

    def test_string_dd_mm_yyyy(self):
        result = DateUtil.parse_last_sync_date("01/03/2025")
        assert result == date(2025, 3, 1)

    def test_string_yyyy_mm_dd(self):
        result = DateUtil.parse_last_sync_date("2025-03-01")
        assert result == date(2025, 3, 1)

    def test_none_input(self):
        assert DateUtil.parse_last_sync_date(None) is None

    def test_empty_string(self):
        assert DateUtil.parse_last_sync_date("") is None

    def test_empty_dict(self):
        assert DateUtil.parse_last_sync_date({}) is None

    def test_unparseable_string(self):
        assert DateUtil.parse_last_sync_date("not-a-date") is None

    def test_integer_input(self):
        assert DateUtil.parse_last_sync_date(12345) is None


class TestCalculateDaysBetween:
    def test_same_day(self):
        assert DateUtil.calculate_days_between("2025-11-01", "2025-11-01") == 1

    def test_multi_day(self):
        assert DateUtil.calculate_days_between("2025-11-01", "2025-11-15") == 15

    def test_full_month(self):
        assert DateUtil.calculate_days_between("2025-11-01", "2025-11-30") == 30

    def test_reversed_dates_returns_none(self):
        assert DateUtil.calculate_days_between("2025-11-15", "2025-11-01") is None

    def test_empty_start(self):
        assert DateUtil.calculate_days_between("", "2025-11-15") is None

    def test_empty_end(self):
        assert DateUtil.calculate_days_between("2025-11-01", "") is None

    def test_none_inputs(self):
        assert DateUtil.calculate_days_between(None, None) is None

    def test_bad_format(self):
        assert DateUtil.calculate_days_between("11-01-2025", "11-15-2025") is None


class TestFormatMonthYearKey:
    def test_basic(self):
        assert DateUtil.format_month_year_key(3, 2025) == "3.2025"

    def test_december(self):
        assert DateUtil.format_month_year_key(12, 2024) == "12.2024"


class TestIsCurrentMonthFromKey:
    @patch("custom_components.mijnted.utils.date_util.datetime")
    def test_current(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 11, 15)
        assert DateUtil.is_current_month_from_key("2025-11") is True

    @patch("custom_components.mijnted.utils.date_util.datetime")
    def test_not_current(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 11, 15)
        assert DateUtil.is_current_month_from_key("2025-10") is False

    def test_invalid_key(self):
        assert DateUtil.is_current_month_from_key("bogus") is False

    def test_empty_key(self):
        assert DateUtil.is_current_month_from_key("") is False


class TestParseMonthKey:
    def test_valid(self):
        assert DateUtil.parse_month_key("2025-11") == (2025, 11)

    def test_invalid(self):
        assert DateUtil.parse_month_key("nope") is None

    def test_empty(self):
        assert DateUtil.parse_month_key("") is None

    def test_too_many_parts(self):
        assert DateUtil.parse_month_key("2025-11-01") is None


class TestFormatMonthName:
    def test_november(self):
        assert DateUtil.format_month_name(11, 2025) == "November 2025"

    def test_january(self):
        assert DateUtil.format_month_name(1, 2024) == "January 2024"

    def test_invalid_month_zero(self):
        assert DateUtil.format_month_name(0, 2025) is None

    def test_invalid_month_13(self):
        assert DateUtil.format_month_name(13, 2025) is None

    def test_invalid_year_zero(self):
        assert DateUtil.format_month_name(1, 0) is None
