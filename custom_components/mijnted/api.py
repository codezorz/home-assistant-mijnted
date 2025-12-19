import aiohttp
import async_timeout
import logging
import asyncio
import jwt
from datetime import datetime
from typing import Dict, Any, Optional
from .const import BASE_URL, AUTH_URL

_LOGGER = logging.getLogger(__name__)

class MijntedApiError(Exception):
    """Base exception for Mijnted API errors."""
    pass

class MijntedApi:
    def __init__(self, client_id: str, refresh_token: Optional[str] = None, access_token: Optional[str] = None, residential_unit: Optional[str] = None):
        self.client_id = client_id
        self.refresh_token = refresh_token
        self.access_token = access_token
        self.session: Optional[aiohttp.ClientSession] = None
        self.auth_url = AUTH_URL
        self.base_url = BASE_URL
        self.residential_unit = residential_unit
        self.delivery_type: Optional[str] = None
        self.residential_units_claim = "https://ted-prod-function-app.azurewebsites.net/residential_units"

    async def __aenter__(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def refresh_access_token(self) -> str:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            raise MijntedApiError("No refresh token available")
        
        if self.session is None:
            self.session = aiohttp.ClientSession()

        # Azure AD B2C refresh token flow
        # Request access_token by including the client_id in scope
        data = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "scope": f"{self.client_id} openid profile offline_access"
        }

        try:
            async with async_timeout.timeout(10):
                async with self.session.post(self.auth_url, data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        self.access_token = result.get("access_token")
                        id_token = result.get("id_token")
                        new_refresh_token = result.get("refresh_token")
                        
                        # If no access_token, try using id_token (some flows return only id_token)
                        if not self.access_token and id_token:
                            _LOGGER.warning("No access_token in response, using id_token")
                            self.access_token = id_token
                        
                        if not self.access_token:
                            raise MijntedApiError("Access token missing in response")
                        
                        # Update refresh token if a new one is provided
                        if new_refresh_token:
                            self.refresh_token = new_refresh_token
                        
                        # Extract residential unit from token if not already set
                        if not self.residential_unit:
                            # Try from id_token first, then access_token
                            if id_token:
                                await self._extract_residential_unit_from_id_token(id_token)
                            if not self.residential_unit:
                                await self._extract_residential_unit_from_token()
                        
                        return self.access_token
                    else:
                        error_text = await response.text()
                        _LOGGER.error("Token refresh failed: %s - %s", response.status, error_text)
                        raise MijntedApiError(f"Token refresh failed: {response.status} - {error_text}")
        except aiohttp.ClientError as err:
            _LOGGER.error("Network error during token refresh: %s", err)
            raise MijntedApiError(f"Network error during token refresh: {err}")
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout during token refresh")
            raise MijntedApiError("Timeout during token refresh")

    async def _extract_residential_unit_from_id_token(self, id_token: str) -> None:
        """Extract residential unit from the id token."""
        try:
            payload = jwt.decode(id_token, options={"verify_signature": False})
            # Try multiple possible claim names
            residential_units = (
                payload.get(self.residential_units_claim) or
                payload.get("extension_ResidentialUnits") or
                payload.get("https://ted-prod-function-app.azurewebsites.net/residential_units")
            )
            if residential_units:
                if isinstance(residential_units, list) and len(residential_units) > 0:
                    self.residential_unit = residential_units[0]
                elif isinstance(residential_units, str):
                    self.residential_unit = residential_units
        except Exception as err:
            _LOGGER.warning("Could not extract residential unit from id_token: %s", err)

    async def _extract_residential_unit_from_token(self) -> None:
        """Extract residential unit from the access token."""
        if not self.access_token:
            return
        
        try:
            payload = jwt.decode(self.access_token, options={"verify_signature": False})
            # Try multiple possible claim names
            residential_units = (
                payload.get(self.residential_units_claim) or
                payload.get("extension_ResidentialUnits") or
                payload.get("https://ted-prod-function-app.azurewebsites.net/residential_units")
            )
            if residential_units:
                if isinstance(residential_units, list) and len(residential_units) > 0:
                    self.residential_unit = residential_units[0]
                elif isinstance(residential_units, str):
                    self.residential_unit = residential_units
        except Exception as err:
            _LOGGER.warning("Could not extract residential unit from token: %s", err)

    async def authenticate(self) -> None:
        """Authenticate with the Mijnted API using refresh token."""
        if self.session is None:
            self.session = aiohttp.ClientSession()

        # If we have an access token, check if it's still valid
        if self.access_token:
            try:
                # Try to decode and check expiration
                payload = jwt.decode(self.access_token, options={"verify_signature": False})
                exp = payload.get("exp")
                if exp and datetime.fromtimestamp(exp) > datetime.now():
                    # Token is still valid, extract residential unit if needed
                    if not self.residential_unit:
                        await self._extract_residential_unit_from_token()
                    await self.get_delivery_types()
                    return
            except Exception:
                # Token is invalid, need to refresh
                pass

        # Refresh the access token
        await self.refresh_access_token()
        await self.get_delivery_types()

    async def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make an API request with proper error handling and automatic token refresh."""
        if not self.access_token:
            await self.authenticate()

        try:
            async with async_timeout.timeout(10):
                async with self.session.request(method, url, headers=self._headers(), **kwargs) as response:
                    if response.status == 200:
                        # Check content type to handle both JSON and plain text responses
                        content_type = response.headers.get("Content-Type", "").lower()
                        if "application/json" in content_type:
                            return await response.json()
                        else:
                            # Handle plain text responses (e.g., dates)
                            text_response = await response.text()
                            # Try to parse as JSON first, fallback to text
                            try:
                                import json
                                return json.loads(text_response)
                            except (json.JSONDecodeError, ValueError):
                                # Return as plain text wrapped in a dict
                                return {"value": text_response}
                    elif response.status == 401:
                        # Token expired, try to refresh
                        _LOGGER.info("Access token expired, refreshing...")
                        await self.refresh_access_token()
                        # Retry the request with new token
                        async with self.session.request(method, url, headers=self._headers(), **kwargs) as retry_response:
                            if retry_response.status == 200:
                                content_type = retry_response.headers.get("Content-Type", "").lower()
                                if "application/json" in content_type:
                                    return await retry_response.json()
                                else:
                                    text_response = await retry_response.text()
                                    try:
                                        import json
                                        return json.loads(text_response)
                                    except (json.JSONDecodeError, ValueError):
                                        return {"value": text_response}
                            else:
                                error_text = await retry_response.text()
                                _LOGGER.error("API request failed after token refresh: %s - %s", retry_response.status, error_text)
                                raise MijntedApiError(f"API request failed: {retry_response.status} - {error_text}")
                    else:
                        error_text = await response.text()
                        _LOGGER.error("API request failed: %s - %s", response.status, error_text)
                        raise MijntedApiError(f"API request failed: {response.status} - {error_text}")
        except aiohttp.ClientError as err:
            _LOGGER.error("Network error during API request: %s", err)
            raise MijntedApiError(f"Network error during API request: {err}")
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout during API request")
            raise MijntedApiError("Timeout during API request")

    async def get_delivery_types(self) -> list:
        """Get delivery types for the residential unit."""
        url = f"{self.base_url}/address/deliveryTypes/{self.residential_unit}"
        result = await self._make_request("GET", url)
        if isinstance(result, list) and len(result) > 0:
            self.delivery_type = result[0]
            return result
        return []

    async def get_energy_usage(self) -> Dict[str, Any]:
        """Get energy usage data."""
        current_year = datetime.now().year
        url = f"{self.base_url}/residentialUnitUsage/{current_year}/{self.residential_unit}/{self.delivery_type}"
        return await self._make_request("GET", url)

    async def get_last_data_update(self) -> Dict[str, Any]:
        """Get last data update information."""
        url = f"{self.base_url}/getLastSyncDate/{self.residential_unit}/{self.delivery_type}/{datetime.now().year}"
        return await self._make_request("GET", url)

    async def get_filter_status(self):
        """Get filter status information. Returns a list of device status objects."""
        url = f"{self.base_url}/deviceStatuses/{self.residential_unit}/{self.delivery_type}/{datetime.now().year}"
        result = await self._make_request("GET", url)
        # API returns a JSON array directly (not wrapped)
        # _make_request returns the JSON as-is when content-type is application/json
        if isinstance(result, list):
            return result
        # Fallback: if somehow wrapped, try to extract
        if isinstance(result, dict) and "value" in result:
            value = result["value"]
            return value if isinstance(value, list) else []
        return []

    async def get_usage_insight(self) -> Dict[str, Any]:
        """Get usage insight information."""
        url = f"{self.base_url}/usageInsight/{datetime.now().year}/{self.residential_unit}/{self.delivery_type}"
        return await self._make_request("GET", url)

    async def get_active_model(self) -> Dict[str, Any]:
        """Get active model information."""
        url = f"{self.base_url}/activeModel/{self.residential_unit}/{self.delivery_type}"
        return await self._make_request("GET", url)

    async def get_residential_unit_detail(self) -> Dict[str, Any]:
        """Get residential unit detail information."""
        url = f"{self.base_url}/residentialUnitDetailItem/{self.residential_unit}"
        return await self._make_request("GET", url)

    async def get_usage_last_year(self) -> Dict[str, Any]:
        """Get usage data for last year."""
        last_year = datetime.now().year - 1
        url = f"{self.base_url}/residentialUnitUsage/{last_year}/{self.residential_unit}/{self.delivery_type}"
        return await self._make_request("GET", url)

    async def get_usage_per_room(self) -> Dict[str, Any]:
        """Get usage data per room for current year."""
        current_year = datetime.now().year
        url = f"{self.base_url}/residentialUnitUsagePerRoom/{current_year}/{self.residential_unit}/{self.delivery_type}"
        return await self._make_request("GET", url)

    def _headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": "HomeAssistant/MijnTed"
        }

    async def close(self) -> None:
        """Close the API session."""
        if self.session:
            await self.session.close()
            self.session = None
