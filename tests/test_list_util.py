"""Tests for utils/list_util.py."""
import pytest

from custom_components.mijnted.utils.list_util import ListUtil


class TestGetFirstItem:
    def test_non_empty_list(self):
        assert ListUtil.get_first_item([10, 20, 30]) == 10

    def test_single_element(self):
        assert ListUtil.get_first_item(["only"]) == "only"

    def test_empty_list(self):
        assert ListUtil.get_first_item([]) is None

    def test_none(self):
        assert ListUtil.get_first_item(None) is None

    def test_string_not_treated_as_list(self):
        assert ListUtil.get_first_item("hello") is None

    def test_dict_not_treated_as_list(self):
        assert ListUtil.get_first_item({"a": 1}) is None

    def test_integer_not_treated_as_list(self):
        assert ListUtil.get_first_item(42) is None

    def test_nested_list(self):
        assert ListUtil.get_first_item([[1, 2], [3, 4]]) == [1, 2]
