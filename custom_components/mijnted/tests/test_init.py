"""Test MijnTed setup process."""
from unittest.mock import patch, MagicMock
from homeassistant.setup import async_setup_component
from custom_components.mijnted import async_setup_entry
from homeassistant.core import HomeAssistant
from ..const import DOMAIN
import pytest

pytestmark = pytest.mark.asyncio

async def test_async_setup(hass: HomeAssistant):
    """Test the component gets setup."""
    config = {DOMAIN: {"username": "test", "password": "test_password"}}
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    assert DOMAIN in hass.data

async def test_async_setup_entry(hass: HomeAssistant):
    """Test the component gets setup."""
    mock_config_entry = MagicMock()
    mock_config_entry.data = {
        "username": "test",
        "password": "test_password",
        "client_id": "test_client_id"
    }
    assert await async_setup_entry(hass, mock_config_entry)
    assert DOMAIN in hass.data
