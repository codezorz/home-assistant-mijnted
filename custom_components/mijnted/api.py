import aiohttp
import asyncio
import json
import logging
import jwt
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable, Awaitable, List
from .const import (
    BASE_URL,
    AUTH_URL,
    REQUEST_TIMEOUT,
    RESIDENTIAL_UNITS_CLAIM,
    RESIDENTIAL_UNITS_CLAIM_ALT,
    USER_AGENT,
)


_LOGGER = logging.getLogger(__name__)


class MijntedApiError(Exception):
    """Base exception for Mijnted API errors."""
    pass


class MijntedAuthenticationError(MijntedApiError):
    """Exception for authentication errors."""
    pass


class MijntedConnectionError(MijntedApiError):
    """Exception for connection errors."""
    pass


class MijntedTimeoutError(MijntedApiError):
    """Exception for timeout errors."""
    pass

class MijntedApi:
    def __init__(self, client_id: str, refresh_token: Optional[str] = None, access_token: Optional[str] = None, residential_unit: Optional[str] = None, token_update_callback: Optional[Callable[[str, Optional[str], Optional[str]], Awaitable[None]]] = None):
        """Initialize Mijnted API client.
        
        Args:
            client_id: MijnTed client ID (required)
            refresh_token: Refresh token for authentication
            access_token: Access token (optional, will be refreshed if needed)
            residential_unit: Residential unit identifier
            token_update_callback: Callback for token updates
            
        Raises:
            ValueError: If client_id is empty
        """
        if not client_id or not client_id.strip():
            raise ValueError("client_id is required and cannot be empty")
        
        self.client_id = client_id.strip()
        self.refresh_token = refresh_token
        self.access_token = access_token
        self.session: Optional[aiohttp.ClientSession] = None
        self.auth_url = AUTH_URL
        self.base_url = BASE_URL
        self.residential_unit = residential_unit
        self.delivery_type: Optional[str] = None
        self.token_update_callback = token_update_callback

    def _ensure_session(self) -> None:
        """Ensure a session exists, creating one if necessary."""
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def __aenter__(self):
        """Async context manager entry.
        
        Returns:
            Self instance with ensured session
        """
        self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit.
        
        Args:
            exc_type: Exception type if any
            exc_val: Exception value if any
            exc_tb: Exception traceback if any
        """
        await self.close()

    async def refresh_access_token(self) -> str:
        """Refresh the access token using the refresh token.
        
        Returns:
            New access token string
            
        Raises:
            MijntedAuthenticationError: If authentication fails
            MijntedTimeoutError: If request times out
            MijntedConnectionError: If network error occurs
            MijntedApiError: For other API errors
        """
        if not self.refresh_token:
            raise MijntedAuthenticationError("No refresh token available")
        
        self._ensure_session()

        # Azure AD B2C refresh token flow
        # Request access_token by including the client_id in scope
        data = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "scope": f"{self.client_id} openid profile offline_access"
        }

        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        try:
            async with self.session.post(self.auth_url, data=data, timeout=timeout) as response:
                    if response.status == 200:
                        result = await response.json()
                        self.access_token = result.get("access_token")
                        id_token = result.get("id_token")
                        new_refresh_token = result.get("refresh_token")
                        
                        # If no access_token, try using id_token (some flows return only id_token)
                        if not self.access_token and id_token:
                            _LOGGER.debug(
                                "No access_token in response, using id_token",
                                extra={"has_residential_unit": bool(self.residential_unit)}
                            )
                            self.access_token = id_token
                        
                        if not self.access_token:
                            raise MijntedAuthenticationError("Access token missing in response")
                        
                        # Update refresh token if a new one is provided
                        if new_refresh_token:
                            self.refresh_token = new_refresh_token
                        
                        # Extract residential unit from token if not already set
                        if not self.residential_unit:
                            # Try from id_token first, then access_token
                            if id_token:
                                await self._extract_residential_unit_from_id_token(id_token)
                            if not self.residential_unit:
                                self._extract_residential_unit_from_token()
                        
                        # Notify callback if tokens were updated
                        if new_refresh_token and self.token_update_callback:
                            try:
                                await self.token_update_callback(
                                    self.refresh_token,
                                    self.access_token,
                                    self.residential_unit
                                )
                            except Exception as err:
                                _LOGGER.warning(
                                    "Error in token update callback: %s",
                                    err,
                                    extra={"has_residential_unit": bool(self.residential_unit)},
                                    exc_info=True
                                )
                        
                        return self.access_token
                    else:
                        error_text = await response.text()
                        _LOGGER.error(
                            "Token refresh failed: %s - %s",
                            response.status,
                            error_text,
                            extra={"status_code": response.status, "has_residential_unit": bool(self.residential_unit)}
                        )
                        if response.status == 401:
                            raise MijntedAuthenticationError(f"Authentication failed: {error_text}")
                        raise MijntedApiError(f"Token refresh failed: {response.status} - {error_text}")
        except (TimeoutError, asyncio.TimeoutError) as err:
            _LOGGER.error(
                "Timeout during token refresh: %s",
                err,
                extra={"timeout": REQUEST_TIMEOUT}
            )
            raise MijntedTimeoutError("Timeout during token refresh") from err
        except aiohttp.ClientError as err:
            _LOGGER.error(
                "Network error during token refresh: %s",
                err,
                extra={"auth_url": self.auth_url}
            )
            raise MijntedConnectionError(f"Network error during token refresh: {err}") from err
        except (MijntedAuthenticationError, MijntedApiError):
            raise
        except Exception as err:
            _LOGGER.exception("Unexpected error during token refresh: %s", err)
            raise MijntedApiError(f"Unexpected error during token refresh: {err}") from err

    def _extract_residential_unit_from_payload(self, payload: Dict[str, Any]) -> Optional[str]:
        """Extract residential unit from JWT payload.
        
        Args:
            payload: Decoded JWT payload dictionary
            
        Returns:
            Residential unit string if found, None otherwise
        """
        # Try multiple possible claim names
        residential_units = (
            payload.get(RESIDENTIAL_UNITS_CLAIM) or
            payload.get(RESIDENTIAL_UNITS_CLAIM_ALT)
        )
        
        if residential_units:
            if isinstance(residential_units, list) and len(residential_units) > 0:
                return residential_units[0]
            elif isinstance(residential_units, str):
                return residential_units
        return None

    async def _extract_residential_unit_from_id_token(self, id_token: str) -> None:
        """Extract residential unit from the id token.
        
        Args:
            id_token: JWT ID token string
        """
        try:
            payload = jwt.decode(id_token, options={"verify_signature": False})
            residential_unit = self._extract_residential_unit_from_payload(payload)
            if residential_unit:
                self.residential_unit = residential_unit
        except jwt.DecodeError as err:
            _LOGGER.debug(
                "Could not decode id_token: %s",
                err,
                extra={"has_id_token": bool(id_token)}
            )
        except Exception as err:
            _LOGGER.debug(
                "Could not extract residential unit from id_token: %s",
                err,
                extra={"has_id_token": bool(id_token)}
            )

    def _extract_residential_unit_from_token(self) -> None:
        """Extract residential unit from the access token.
        
        Updates self.residential_unit if found in token payload.
        """
        if not self.access_token:
            return
        
        try:
            payload = jwt.decode(self.access_token, options={"verify_signature": False})
            residential_unit = self._extract_residential_unit_from_payload(payload)
            if residential_unit:
                self.residential_unit = residential_unit
        except jwt.DecodeError as err:
            _LOGGER.debug(
                "Could not decode access token: %s",
                err,
                extra={"has_access_token": bool(self.access_token)}
            )
        except Exception as err:
            _LOGGER.debug(
                "Could not extract residential unit from token: %s",
                err,
                extra={"has_access_token": bool(self.access_token)}
            )

    async def authenticate(self) -> None:
        """Authenticate with the Mijnted API using refresh token.
        
        Checks if existing access token is valid, otherwise refreshes it.
        Also fetches delivery types after successful authentication.
        """
        self._ensure_session()

        # If we have an access token, check if it's still valid
        if self.access_token:
            try:
                # Try to decode and check expiration
                payload = jwt.decode(self.access_token, options={"verify_signature": False})
                exp = payload.get("exp")
                if exp:
                    # JWT exp is in UTC, compare with UTC now
                    exp_time = datetime.fromtimestamp(exp, tz=timezone.utc)
                    if exp_time > datetime.now(timezone.utc):
                        # Token is still valid, extract residential unit if needed
                        if not self.residential_unit:
                            self._extract_residential_unit_from_token()
                        await self.get_delivery_types()
                        return
            except jwt.DecodeError:
                # Token is invalid, need to refresh
                _LOGGER.debug(
                    "Access token decode failed, refreshing token",
                    extra={"has_access_token": bool(self.access_token), "has_residential_unit": bool(self.residential_unit)}
                )
            except Exception as err:
                # Token is invalid, need to refresh
                _LOGGER.debug(
                    "Access token validation failed: %s",
                    err,
                    extra={"has_access_token": bool(self.access_token), "has_residential_unit": bool(self.residential_unit)}
                )

        # Refresh the access token
        await self.refresh_access_token()
        await self.get_delivery_types()

    async def _parse_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Parse API response handling both JSON and plain text.
        
        Args:
            response: aiohttp response object
            
        Returns:
            Parsed response data as dictionary
        """
        content_type = response.headers.get("Content-Type", "").lower()
        if "application/json" in content_type:
            return await response.json()
        
        # Handle plain text responses (e.g., dates)
        text_response = await response.text()
        # Try to parse as JSON first, fallback to text
        try:
            return json.loads(text_response)
        except (json.JSONDecodeError, ValueError):
            # Return as plain text wrapped in a dict
            return {"value": text_response}

    async def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make an API request with proper error handling and automatic token refresh.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments passed to aiohttp request
            
        Returns:
            Parsed response data as dictionary
            
        Raises:
            MijntedAuthenticationError: If authentication fails
            MijntedTimeoutError: If request times out
            MijntedConnectionError: If network error occurs
            MijntedApiError: For other API errors
        """
        if not self.access_token:
            await self.authenticate()

        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        try:
            async with self.session.request(method, url, headers=self._headers(), timeout=timeout, **kwargs) as response:
                    if response.status == 200:
                        return await self._parse_response(response)
                    elif response.status == 401:
                        # Token expired, try to refresh
                        _LOGGER.info(
                            "Access token expired, refreshing...",
                            extra={"url": url, "method": method, "residential_unit": self.residential_unit}
                        )
                        await self.refresh_access_token()
                        # Retry the request with new token
                        async with self.session.request(method, url, headers=self._headers(), timeout=timeout, **kwargs) as retry_response:
                            if retry_response.status == 200:
                                return await self._parse_response(retry_response)
                            else:
                                error_text = await retry_response.text()
                                _LOGGER.error(
                                    "API request failed after token refresh: %s - %s",
                                    retry_response.status,
                                    error_text,
                                    extra={"url": url, "method": method, "status_code": retry_response.status, "residential_unit": self.residential_unit}
                                )
                                if retry_response.status == 401:
                                    raise MijntedAuthenticationError(
                                        f"Authentication failed after token refresh: {error_text}"
                                    )
                                raise MijntedApiError(
                                    f"API request failed: {retry_response.status} - {error_text}"
                                )
                    elif response.status == 401:
                        error_text = await response.text()
                        _LOGGER.error(
                            "API request unauthorized: %s",
                            error_text,
                            extra={"url": url, "method": method, "status_code": response.status, "residential_unit": self.residential_unit}
                        )
                        raise MijntedAuthenticationError(f"Authentication failed: {error_text}")
                    else:
                        error_text = await response.text()
                        _LOGGER.error(
                            "API request failed: %s - %s",
                            response.status,
                            error_text,
                            extra={"url": url, "method": method, "status_code": response.status, "residential_unit": self.residential_unit}
                        )
                        raise MijntedApiError(f"API request failed: {response.status} - {error_text}")
        except (TimeoutError, asyncio.TimeoutError) as err:
            _LOGGER.error(
                "Timeout during API request: %s",
                err,
                extra={"url": url, "method": method, "timeout": REQUEST_TIMEOUT, "residential_unit": self.residential_unit}
            )
            raise MijntedTimeoutError("Timeout during API request") from err
        except aiohttp.ClientError as err:
            _LOGGER.error(
                "Network error during API request: %s",
                err,
                extra={"url": url, "method": method, "residential_unit": self.residential_unit}
            )
            raise MijntedConnectionError(f"Network error during API request: {err}") from err
        except (MijntedAuthenticationError, MijntedConnectionError, MijntedTimeoutError, MijntedApiError):
            raise
        except Exception as err:
            _LOGGER.exception(
                "Unexpected error during API request: %s",
                err,
                extra={"url": url, "method": method, "residential_unit": self.residential_unit}
            )
            raise MijntedApiError(f"Unexpected error during API request: {err}") from err

    @staticmethod
    def _get_current_year() -> int:
        """Get the current year.
        
        Returns:
            Current year as integer
        """
        return datetime.now().year

    async def get_delivery_types(self) -> List[Any]:
        """Get delivery types for the residential unit.
        
        Returns:
            List of delivery types, empty list if none found
        """
        url = f"{self.base_url}/address/deliveryTypes/{self.residential_unit}"
        result = await self._make_request("GET", url)
        if isinstance(result, list) and len(result) > 0:
            self.delivery_type = result[0]
            return result
        return []

    async def get_energy_usage(self) -> Dict[str, Any]:
        """Get energy usage data for the current year.
        
        Returns:
            Dictionary containing energy usage data with monthly breakdown
        """
        current_year = self._get_current_year()
        url = f"{self.base_url}/residentialUnitUsage/{current_year}/{self.residential_unit}/{self.delivery_type}"
        _LOGGER.debug(
            "Fetching energy usage",
            extra={"residential_unit": self.residential_unit, "year": current_year, "delivery_type": self.delivery_type}
        )
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
        # API returns a JSON array directly (not wrapped)
        # _make_request returns the JSON as-is when content-type is application/json
        if isinstance(result, list):
            return result
        # Fallback: if somehow wrapped, try to extract
        if isinstance(result, dict) and "value" in result:
            value = result["value"]
            return value if isinstance(value, list) else []
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
        _LOGGER.debug(
            "Fetching usage insight",
            extra={"residential_unit": self.residential_unit, "year": year, "delivery_type": self.delivery_type}
        )
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

    async def get_usage_last_year(self) -> Dict[str, Any]:
        """Get usage data for last year.
        
        Returns:
            Dictionary containing last year's energy usage data
        """
        last_year = self._get_current_year() - 1
        url = f"{self.base_url}/residentialUnitUsage/{last_year}/{self.residential_unit}/{self.delivery_type}"
        return await self._make_request("GET", url)

    async def get_usage_per_room(self) -> Dict[str, Any]:
        """Get usage data per room for current year.
        
        Returns:
            Dictionary containing room usage data
        """
        current_year = self._get_current_year()
        url = f"{self.base_url}/residentialUnitUsagePerRoom/{current_year}/{self.residential_unit}/{self.delivery_type}"
        return await self._make_request("GET", url)

    async def get_unit_of_measures(self) -> List[Dict[str, Any]]:
        """Get unit of measures for the residential unit.
        
        Returns:
            List of unit of measure objects, empty list if none found
        """
        current_year = self._get_current_year()
        url = f"{self.base_url}/unitOfMeasures/{self.residential_unit}/{self.delivery_type}/{current_year}"
        result = await self._make_request("GET", url)
        # API returns a JSON array directly
        if isinstance(result, list):
            return result
        # Fallback: if somehow wrapped, try to extract
        if isinstance(result, dict) and "value" in result:
            value = result["value"]
            return value if isinstance(value, list) else []
        return []

    def _headers(self) -> Dict[str, str]:
        """Get headers for API requests.
        
        Returns:
            Dictionary containing Authorization and User-Agent headers
        """
        return {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": USER_AGENT,
        }

    async def close(self) -> None:
        """Close the API session.
        
        Safely closes the aiohttp session if it exists.
        """
        if self.session:
            await self.session.close()
            self.session = None
