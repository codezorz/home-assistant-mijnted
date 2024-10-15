"""Tests for the MijnTed sensor platform."""
from unittest.mock import patch, MagicMock
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from ..const import DOMAIN
from ..sensor import async_setup_entry
import pytest

pytestmark = pytest.mark.asyncio

async def test_sensor_setup(hass: HomeAssistant, mock_mijnted_api):
    """Test sensor setup."""
    mock_config_entry = MagicMock()
    mock_config_entry.data = {
        "username": "test",
        "password": "test_password",
        "client_id": "test_client_id"
    }
    mock_async_add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)
    assert mock_async_add_entities.called

async def test_sensor_update(hass: HomeAssistant, mock_mijnted_api):
    """Test sensor update."""
    mock_data = {
        "energy_usage": {"current_usage": 500, "total_usage": 10000},
        "last_update": "2023-01-01T00:00:00Z",
        "filter_status": "OK",
        "usage_insight": {"daily": 100, "weekly": 700, "monthly": 3000}
    }
    mock_mijnted_api.get_energy_usage.return_value = mock_data["energy_usage"]
    mock_mijnted_api.get_last_data_update.return_value = mock_data["last_update"]
    mock_mijnted_api.get_filter_status.return_value = mock_data["filter_status"]
    mock_mijnted_api.get_usage_insight.return_value = mock_data["usage_insight"]

    mock_config_entry = MagicMock()
    mock_config_entry.data = {
        "username": "test",
        "password": "test_password",
        "client_id": "test_client_id"
    }
    mock_async_add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)
    await hass.async_block_till_done()

    # Add assertions to check if the sensors are created and updated correctly
