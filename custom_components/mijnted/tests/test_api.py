"""Tests for the MijnTed API."""
from ..api import MijntedApi
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_aiohttp_client():
    with patch('aiohttp.ClientSession') as mock:
        yield mock

async def test_api_auth_success(mock_aiohttp_client):
    """Test successful authentication."""
    mock_session = MagicMock()
    mock_response = AsyncMock()
    mock_response.json.return_value = {"access_token": "test_token"}
    mock_session.post.return_value.__aenter__.return_value = mock_response
    mock_aiohttp_client.return_value = mock_session

    client = MijntedApi("test_user", "test_password", "test_client_id")
    await client.authenticate()
    assert client.access_token == "test_token"

async def test_get_energy_usage(mock_aiohttp_client):
    """Test retrieving energy usage data."""
    mock_session = MagicMock()
    mock_response = AsyncMock()
    mock_data = {"current_usage": 500, "total_usage": 10000}
    mock_response.json.return_value = mock_data
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_aiohttp_client.return_value = mock_session

    client = MijntedApi("test_user", "test_password", "test_client_id")
    client.access_token = "test_token"
    data = await client.get_energy_usage()
    assert data == mock_data

async def test_get_last_data_update(mock_aiohttp_client):
    """Test retrieving last data update."""
    mock_session = MagicMock()
    mock_response = AsyncMock()
    mock_data = "2023-01-01T00:00:00Z"
    mock_response.json.return_value = {"last_update": mock_data}
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_aiohttp_client.return_value = mock_session

    client = MijntedApi("test_user", "test_password", "test_client_id")
    client.access_token = "test_token"
    data = await client.get_last_data_update()
    assert data == mock_data

async def test_get_filter_status(mock_aiohttp_client):
    """Test retrieving filter status."""
    mock_session = MagicMock()
    mock_response = AsyncMock()
    mock_data = "OK"
    mock_response.json.return_value = {"filter_status": mock_data}
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_aiohttp_client.return_value = mock_session

    client = MijntedApi("test_user", "test_password", "test_client_id")
    client.access_token = "test_token"
    data = await client.get_filter_status()
    assert data == mock_data

async def test_get_usage_insight(mock_aiohttp_client):
    """Test retrieving usage insight."""
    mock_session = MagicMock()
    mock_response = AsyncMock()
    mock_data = {"daily": 100, "weekly": 700, "monthly": 3000}
    mock_response.json.return_value = mock_data
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_aiohttp_client.return_value = mock_session

    client = MijntedApi("test_user", "test_password", "test_client_id")
    client.access_token = "test_token"
    data = await client.get_usage_insight()
    assert data == mock_data

async def test_api_error(mock_aiohttp_client):
    """Test API error handling."""
    mock_session = MagicMock()
    mock_response = AsyncMock()
    mock_response.raise_for_status.side_effect = Exception("API Error")
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_aiohttp_client.return_value = mock_session

    client = MijntedApi("test_user", "test_password", "test_client_id")
    client.access_token = "test_token"
    with pytest.raises(Exception):
        await client.get_energy_usage()
