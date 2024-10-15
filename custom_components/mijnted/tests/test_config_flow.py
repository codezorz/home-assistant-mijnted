"""Test the MijnTed config flow."""
from unittest.mock import patch
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from ..const import DOMAIN
import pytest

pytestmark = pytest.mark.asyncio

async def test_form(hass: HomeAssistant):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "custom_components.mijnted.config_flow.MijnTedApiClient.authenticate",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
    }
