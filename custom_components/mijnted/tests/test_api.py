import os
import pytest
from custom_components.mijnted.api import MijntedApi

@pytest.fixture(scope="module")
def api():
    username = os.environ.get("MIJNTED_USERNAME")
    password = os.environ.get("MIJNTED_PASSWORD")
    client_id = os.environ.get("MIJNTED_CLIENT_ID")
    
    if not all([username, password, client_id]):
        pytest.skip("Mijnted credentials not set in environment variables")
    
    return MijntedApi(username, password, client_id)

@pytest.mark.asyncio
@pytest.mark.enable_socket
async def test_login(api):
    result = await api.login()
    assert result is not None
    assert isinstance(result, str)
