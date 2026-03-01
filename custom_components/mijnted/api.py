import asyncio
import json
import logging
from datetime import date, datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

import aiohttp

from .const import (
    API_BASE_URL,
    API_DATE_FORMAT,
    AUTHORIZATION_SCHEME_BEARER,
    CONTENT_TYPE_JSON,
    HTTP_STATUS_OK,
    HTTP_STATUS_UNAUTHORIZED,
    REQUEST_TIMEOUT,
    USER_AGENT,
)
from .auth import MijntedAuth
from .exceptions import (
    MijntedApiError,
    MijntedAuthenticationError,
    MijntedConnectionError,
    MijntedTimeoutError,
)
from .utils import ApiUtil, DateUtil, ListUtil

_LOGGER = logging.getLogger(__name__)


class MijntedApi:
    """Client for the MijnTed cloud API.

    Manages authenticated HTTP sessions and provides methods to fetch
    energy usage, device statuses, and other data from the MijnTed API.

    Args:
        hass: HomeAssistant instance for async operations.
        client_id: OAuth client ID for MijnTed API authentication.
        refresh_token: OAuth refresh token (optional).
        access_token: OAuth access token (optional).
        residential_unit: Residential unit identifier (optional).
        refresh_token_expires_at: Expiration datetime for the refresh token (optional).
        token_update_callback: Async callback invoked when tokens are refreshed (optional).
        credentials_callback: Async callback to retrieve credentials for re-authentication (optional).
    """

    def __init__(self, hass, client_id: str, refresh_token: Optional[str] = None, access_token: Optional[str] = None, residential_unit: Optional[str] = None, refresh_token_expires_at: Optional[datetime] = None, token_update_callback: Optional[Callable[[str, Optional[str], Optional[str], Optional[datetime]], Awaitable[None]]] = None, credentials_callback: Optional[Callable[[], Awaitable[tuple]]] = None):
        """Initialize Mijnted API client.
        
        Args:
            hass: Home Assistant instance (required for executor jobs)
            client_id: MijnTed client ID (required)
            refresh_token: Refresh token for authentication
            access_token: Access token (optional, will be refreshed if needed)
            residential_unit: Residential unit identifier
            refresh_token_expires_at: UTC datetime when refresh token expires
            token_update_callback: Callback for token updates (includes expiration time)
            credentials_callback: Callback to retrieve (username, password) tuple when re-authentication is needed
            
        Raises:
            ValueError: If client_id is empty
        """
        if not client_id or not client_id.strip():
            raise ValueError("client_id is required and cannot be empty")
        
        self.hass = hass
        self.client_id = client_id.strip()
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_url = API_BASE_URL
        self.delivery_type: Optional[str] = None
        self.token_update_callback = token_update_callback
        self.auth: Optional[MijntedAuth] = None
        self._auth_init_params = {
            "hass": self.hass,
            "client_id": self.client_id,
            "refresh_token": refresh_token,
            "access_token": access_token,
            "residential_unit": residential_unit,
            "refresh_token_expires_at": refresh_token_expires_at,
            "token_update_callback": token_update_callback,
            "credentials_callback": credentials_callback
        }

    def _ensure_session(self) -> None:
        """Creates session and auth if needed."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
            if self.auth is None:
                self.auth = MijntedAuth(
                    session=self.session,
                    **self._auth_init_params
                )
    
    @property
    def access_token(self) -> Optional[str]:
        """Get the current access token from auth handler.

        Returns:
            The current access token, or None if not authenticated.
        """
        return self.auth.access_token if self.auth else self._auth_init_params.get("access_token")
    
    @property
    def refresh_token(self) -> Optional[str]:
        """Get the current refresh token from auth handler.

        Returns:
            The current refresh token, or None if not available.
        """
        return self.auth.refresh_token if self.auth else self._auth_init_params.get("refresh_token")
    
    @property
    def residential_unit(self) -> Optional[str]:
        """Get the current residential unit from auth handler.

        Returns:
            The residential unit identifier, or None if not set.
        """
        return self.auth.residential_unit if self.auth else self._auth_init_params.get("residential_unit")
    
    @property
    def refresh_token_expires_at(self) -> Optional[datetime]:
        """Get the refresh token expiration time from auth handler.

        Returns:
            UTC datetime when the refresh token expires, or None if not available.
        """
        return self.auth.refresh_token_expires_at if self.auth else self._auth_init_params.get("refresh_token_expires_at")

    async def __aenter__(self):
        """Async context manager entry.

        Returns:
            self: The API client instance.
        """
        if self.session is None:
            self.session = aiohttp.ClientSession()
        self.auth = MijntedAuth(
            session=self.session,
            **self._auth_init_params
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit.

        Args:
            exc_type: Exception type if an exception was raised.
            exc_val: Exception value if an exception was raised.
            exc_tb: Exception traceback if an exception was raised.

        Returns:
            None: Always returns None.
        """
        await self.close()

    async def authenticate(self) -> None:
        """Authenticate with the Mijnted API using refresh token and fetch delivery types.

        Raises:
            MijntedAuthenticationError: When authentication fails.
            MijntedConnectionError: When a network error occurs.
            MijntedTimeoutError: When the request times out.
            MijntedApiError: When the API returns an error.
        """
        self._ensure_session()
        await self.auth.authenticate()
        await self.get_delivery_types()

    async def _parse_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Parses an aiohttp response to dict."""
        content_type = response.headers.get("Content-Type", "").lower()
        if CONTENT_TYPE_JSON in content_type:
            return await response.json()
        
        text_response = await response.text()
        try:
            return json.loads(text_response)
        except (json.JSONDecodeError, ValueError):
            return {"value": text_response}

    async def _retry_after_unauthorized(self, method: str, url: str, timeout: aiohttp.ClientTimeout, **kwargs) -> Dict[str, Any]:
        """Refresh the access token and retry the request once after a 401."""
        _LOGGER.debug(
            "Access token expired, refreshing...",
            extra={"url": url, "method": method, "residential_unit": self.residential_unit},
        )
        self._ensure_session()
        await self.auth.refresh_access_token()
        async with self.session.request(method, url, headers=self._headers(), timeout=timeout, **kwargs) as retry_response:
            if retry_response.status == HTTP_STATUS_OK:
                return await self._parse_response(retry_response)
            error_text = await retry_response.text()
            _LOGGER.error(
                "API request failed after token refresh: %s - %s",
                retry_response.status, error_text,
                extra={"url": url, "method": method, "status_code": retry_response.status, "residential_unit": self.residential_unit},
            )
            if retry_response.status == HTTP_STATUS_UNAUTHORIZED:
                raise MijntedAuthenticationError(f"Authentication failed after token refresh: {error_text}")
            raise MijntedApiError(f"API request failed: {retry_response.status} - {error_text}")

    @staticmethod
    def _get_current_year() -> int:
        """Return the current calendar year."""
        return datetime.now().year

    async def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Sends an HTTP request with auth and error handling."""
        self._ensure_session()
        if not self.auth or not self.auth.access_token:
            await self.authenticate()

        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        try:
            async with self.session.request(method, url, headers=self._headers(), timeout=timeout, **kwargs) as response:
                if response.status == HTTP_STATUS_OK:
                    return await self._parse_response(response)
                if response.status == HTTP_STATUS_UNAUTHORIZED:
                    return await self._retry_after_unauthorized(method, url, timeout, **kwargs)
                error_text = await response.text()
                _LOGGER.error(
                    "API request failed: %s - %s", response.status, error_text,
                    extra={"url": url, "method": method, "status_code": response.status, "residential_unit": self.residential_unit},
                )
                raise MijntedApiError(f"API request failed: {response.status} - {error_text}")
        except (TimeoutError, asyncio.TimeoutError) as err:
            _LOGGER.error(
                "Timeout during API request: %s", err,
                extra={"url": url, "method": method, "timeout": REQUEST_TIMEOUT, "residential_unit": self.residential_unit},
            )
            raise MijntedTimeoutError("Timeout during API request") from err
        except aiohttp.ClientError as err:
            _LOGGER.error(
                "Network error during API request: %s", err,
                extra={"url": url, "method": method, "residential_unit": self.residential_unit},
            )
            raise MijntedConnectionError(f"Network error during API request: {err}") from err
        except (MijntedAuthenticationError, MijntedConnectionError, MijntedTimeoutError, MijntedApiError):
            raise
        except Exception as err:
            _LOGGER.exception(
                "Unexpected error during API request: %s", err,
                extra={"url": url, "method": method, "residential_unit": self.residential_unit},
            )
            raise MijntedApiError(f"Unexpected error during API request: {err}") from err

    async def get_delivery_types(self) -> List[Any]:
        """Get delivery types for the residential unit.
        
        Returns:
            List of delivery types, empty list if none found
        """
        url = f"{self.base_url}/address/deliveryTypes/{self.residential_unit}"
        result = await self._make_request("GET", url)
        first_item = ListUtil.get_first_item(result)
        if first_item is not None:
            self.delivery_type = first_item
        return result if isinstance(result, list) else []

    async def get_energy_usage(self, year: Optional[int] = None) -> Dict[str, Any]:
        """Get energy usage data for a specific year.
        
        Args:
            year: Year to get usage data for (defaults to current year)
        
        Returns:
            Dictionary containing energy usage data with monthly breakdown
        """
        if year is None:
            year = self._get_current_year()
        url = f"{self.base_url}/residentialUnitUsage/{year}/{self.residential_unit}/{self.delivery_type}"
        return await self._make_request("GET", url)

    async def get_last_data_update(self) -> Dict[str, Any]:
        """Get last data update information.
        
        Returns:
            Dictionary containing last sync date information
        """
        url = f"{self.base_url}/getLastSyncDate/{self.residential_unit}/{self.delivery_type}/{self._get_current_year()}"
        return await self._make_request("GET", url)

    async def get_filter_status(self) -> List[Dict[str, Any]]:
        """Get filter status information.
        
        Returns:
            List of device status objects, empty list if none found
        """
        url = f"{self.base_url}/deviceStatuses/{self.residential_unit}/{self.delivery_type}/{self._get_current_year()}"
        result = await self._make_request("GET", url)
        if isinstance(result, list):
            return result
        value = ApiUtil.extract_value(result, [])
        return value if isinstance(value, list) else []

    async def get_device_statuses_for_date(self, target_date: date) -> List[Dict[str, Any]]:
        """Get device statuses for a specific date.
        
        Args:
            target_date: Date object for which to retrieve device statuses
            
        Returns:
            List of device status objects for the specified date, empty list if none found or on error
        """
        try:
            date_str = target_date.strftime(API_DATE_FORMAT)
            year = target_date.year
            url = f"{self.base_url}/deviceStatuses/{self.residential_unit}/{self.delivery_type}/{year}?fromDate={date_str}"
            result = await self._make_request("GET", url)
            if isinstance(result, list):
                return result
            value = ApiUtil.extract_value(result, [])
            return value if isinstance(value, list) else []
        except Exception as err:
            date_str = target_date.strftime(API_DATE_FORMAT) if target_date else "unknown"
            _LOGGER.warning(
                "Failed to fetch device statuses for date %s: %s",
                target_date,
                err,
                extra={"date": date_str, "residential_unit": self.residential_unit, "error_type": type(err).__name__}
            )
            return []

    async def get_usage_insight(self, year: Optional[int] = None) -> Dict[str, Any]:
        """Get usage insight information for a specific year.
        
        Args:
            year: Year to get insights for (defaults to current year)
            
        Returns:
            Dictionary containing usage insight data
        """
        if year is None:
            year = self._get_current_year()
        url = f"{self.base_url}/usageInsight/{year}/{self.residential_unit}/{self.delivery_type}"
        return await self._make_request("GET", url)

    async def get_active_model(self) -> Dict[str, Any]:
        """Get active model information.
        
        Returns:
            Dictionary containing active model data
        """
        url = f"{self.base_url}/activeModel/{self.residential_unit}/{self.delivery_type}"
        return await self._make_request("GET", url)

    async def get_residential_unit_detail(self) -> Dict[str, Any]:
        """Get residential unit detail information.
        
        Returns:
            Dictionary containing residential unit details (address, etc.)
        """
        url = f"{self.base_url}/residentialUnitDetailItem/{self.residential_unit}"
        return await self._make_request("GET", url)


    async def get_usage_per_room(self, year: Optional[int] = None) -> Dict[str, Any]:
        """Get usage data per room for a specific year.
        
        Args:
            year: Year to get usage data for (defaults to current year)
        
        Returns:
            Dictionary containing room usage data
        """
        if year is None:
            year = self._get_current_year()
        url = f"{self.base_url}/residentialUnitUsagePerRoom/{year}/{self.residential_unit}/{self.delivery_type}"
        return await self._make_request("GET", url)

    async def get_unit_of_measures(self) -> List[Dict[str, Any]]:
        """Get unit of measures for the residential unit.
        
        Returns:
            List of unit of measure objects, empty list if none found
        """
        current_year = self._get_current_year()
        url = f"{self.base_url}/unitOfMeasures/{self.residential_unit}/{self.delivery_type}/{current_year}"
        result = await self._make_request("GET", url)
        if isinstance(result, list):
            return result
        value = ApiUtil.extract_value(result, [])
        return value if isinstance(value, list) else []

    def _headers(self) -> Dict[str, str]:
        """Returns authorization headers dict."""
        return {
            "Authorization": f"{AUTHORIZATION_SCHEME_BEARER} {self.auth.access_token if self.auth else ''}",
            "User-Agent": USER_AGENT
        }

    async def close(self) -> None:
        """Close the API session and release resources.

        Returns:
            None
        """
        if self.session:
            await self.session.close()
            self.session = None
