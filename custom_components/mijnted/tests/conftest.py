"""Common fixtures for the MijnTed tests."""
from unittest.mock import patch
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component
from ..const import DOMAIN
import pytest
import sys
import os
import asyncio
import tempfile

@pytest.fixture
def mock_mijnted_api():
    """Fixture to provide a mock MijnTed API client."""
    with patch('custom_components.mijnted.api.MijntedApi') as mock_api:
        yield mock_api

@pytest.fixture
async def hass_with_mijnted(hass):
    """Set up a Home Assistant instance with MijnTed integration."""
    assert await async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            "username": "test_user",
            "password": "test_password"
        }
    })
    await hass.async_block_till_done()
    return hass

@pytest.fixture
async def hass(event_loop):
    """Fixture to provide a test instance of Home Assistant."""
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    with tempfile.TemporaryDirectory() as config_dir:
        hass = HomeAssistant(config_dir)
        hass.config.components.add("http")
        hass.config.api = None
        hass.config.internal_url = "http://example.local:8123"
        hass.config.external_url = "https://example.com"
        await hass.async_start()
        yield hass
        await hass.async_stop()

@pytest.fixture
def hass_storage(tmpdir):
    """Fixture to mock storage for hass."""
    return tmpdir.mkdir("storage")

@pytest.fixture
def config() -> ConfigType:
    """Fixture to create a config."""
    return {DOMAIN: {"username": "test_user", "password": "test_password", "client_id": "test_client_id"}}
