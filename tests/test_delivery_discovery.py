"""Tests for multi-delivery-type discovery (issue #50).

Exercises the API discovery helpers against scrubbed real responses captured
from the MijnTed API (``tests/fixtures/api_multi_delivery.json``).
"""
import json
import pathlib

import pytest

from custom_components.mijnted.api import MijntedApi

_FIXTURES = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "api_multi_delivery.json").read_text()
)


def _make_api(monkeypatch):
    """Build a MijntedApi whose _make_request is served from fixtures."""
    api = MijntedApi(hass=object(), client_id="test-client", residential_unit="100000")

    async def fake_make_request(method, url, **kwargs):
        for path, body in _FIXTURES.items():
            if url.endswith(path):
                return body
        raise AssertionError(f"No fixture for {url}")

    monkeypatch.setattr(api, "_make_request", fake_make_request)
    monkeypatch.setattr(MijntedApi, "_get_current_year", staticmethod(lambda: 2026))
    return api


class TestUnitQueryParams:
    def test_gj_appends_param(self):
        assert MijntedApi.unit_query_params("GJ") == {"unitOfMeasure": "GJ"}

    def test_gj_case_insensitive(self):
        assert MijntedApi.unit_query_params("gj") == {"unitOfMeasure": "GJ"}

    @pytest.mark.parametrize("unit", ["m³", "eenheid", "Eenheden", "", None])
    def test_non_gj_omits_param(self, unit):
        assert MijntedApi.unit_query_params(unit) is None


class TestDeliveryTypeLabel:
    @pytest.mark.parametrize(
        "model,label",
        [
            ("F59", "Heating"),
            ("WWZ", "Warm water"),
            ("KWZ", "Cold water"),
            ("wwz", "Warm water"),
        ],
    )
    def test_known_models(self, model, label):
        assert MijntedApi._delivery_type_label(model) == label

    def test_unknown_model_passes_through(self):
        assert MijntedApi._delivery_type_label("XYZ") == "XYZ"

    def test_none_returns_none(self):
        assert MijntedApi._delivery_type_label(None) is None


class TestDiscoverDeliveryTypes:
    @pytest.mark.asyncio
    async def test_discovers_all_three_types(self, monkeypatch):
        api = _make_api(monkeypatch)

        discovered = await api.discover_delivery_types()

        assert [d["id"] for d in discovered] == [1, 2, 3]
        by_id = {d["id"]: d for d in discovered}
        assert by_id[1]["model"] == "F59"
        assert by_id[1]["label"] == "Heating"
        assert by_id[2]["label"] == "Warm water"
        assert by_id[3]["label"] == "Cold water"

    @pytest.mark.asyncio
    async def test_units_per_type(self, monkeypatch):
        api = _make_api(monkeypatch)

        by_id = {d["id"]: d for d in await api.discover_delivery_types()}

        heating_units = {u["value"] for u in by_id[1]["units"]}
        assert heating_units == {"eenheid", "GJ"}
        assert [u["value"] for u in by_id[2]["units"]] == ["m³"]
        assert [u["value"] for u in by_id[3]["units"]] == ["m³"]
