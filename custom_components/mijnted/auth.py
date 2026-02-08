import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

import aiohttp
import requests

from homeassistant.core import HomeAssistant

from .const import (
    AUTH_URL,
    REQUEST_TIMEOUT,
    TOKEN_REFRESH_MAX_RETRIES,
    TOKEN_REFRESH_RETRY_DELAY,
    ID_TOKEN_CLAIM_RESIDENTIAL_UNITS,
    ID_TOKEN_CLAIM_OCCUPANT_ID,
    ID_TOKEN_CLAIM_BILLING_UNITS,
    ID_TOKEN_CLAIM_USER_ROLE,
    HTTP_STATUS_OK,
    HTTP_STATUS_BAD_REQUEST,
    HTTP_STATUS_UNAUTHORIZED,
    REFRESH_TOKEN_PROACTIVE_REFRESH_THRESHOLD_SECONDS,
    REFRESH_TOKEN_DEFAULT_EXPIRATION_SECONDS,
    OAUTH_GRANT_TYPE_REFRESH_TOKEN,
    OAUTH_SCOPE,
    OAUTH_ERROR_INVALID_GRANT,
)
from .utils import JwtUtil, OAuthUtil, ResponseParserUtil, RetryUtil
from .exceptions import (
    MijntedApiError,
    MijntedAuthenticationError,
    MijntedGrantExpiredError,
    MijntedConnectionError,
    MijntedTimeoutError,
)


_LOGGER = logging.getLogger(__name__)


class MijntedAuth:
    """Handles authentication for MijnTed API."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        client_id: str,
        refresh_token: Optional[str] = None,
        access_token: Optional[str] = None,
        residential_unit: Optional[str] = None,
        refresh_token_expires_at: Optional[datetime] = None,
        token_update_callback: Optional[Callable[[str, Optional[str], Optional[str], Optional[datetime]], Awaitable[None]]] = None,
        credentials_callback: Optional[Callable[[], Awaitable[Tuple[str, str]]]] = None,
    ):
        """Initialize Mijnted authentication handler.
        
        Args:
            hass: Home Assistant instance for executor jobs
            session: aiohttp client session for async requests
            client_id: MijnTed client ID
            refresh_token: Optional refresh token
            access_token: Optional access token
            residential_unit: Optional residential unit identifier
            refresh_token_expires_at: Optional refresh token expiration datetime
            token_update_callback: Optional callback for token updates
            credentials_callback: Optional callback to retrieve credentials for re-authentication
        """
        if not client_id or not client_id.strip():
            raise ValueError("client_id is required and cannot be empty")
        
        self.hass = hass
        self.session = session
        self.client_id = client_id.strip()
        self.refresh_token = refresh_token
        self.access_token = access_token
        self.residential_unit = residential_unit
        self.refresh_token_expires_at = refresh_token_expires_at
        self.auth_url = AUTH_URL
        self.token_update_callback = token_update_callback
        self.credentials_callback = credentials_callback
        self.extension_occupant_id: Optional[str] = None
        self.extension_billing_units: Optional[str] = None
        self.extension_user_role: Optional[str] = None

    def _calculate_refresh_token_expires_at(self, refresh_token_expires_in: Optional[Any]) -> datetime:
        if refresh_token_expires_in is not None:
            try:
                expires_in_seconds = int(refresh_token_expires_in)
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
                return expires_at
            except (ValueError, TypeError) as err:
                _LOGGER.warning("Could not parse refresh_token_expires_in: %s", refresh_token_expires_in, exc_info=True)
        
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=REFRESH_TOKEN_DEFAULT_EXPIRATION_SECONDS)
        return expires_at
    
    async def _invoke_token_update_callback(self) -> None:
        if not self.token_update_callback:
            return
        
        try:
            await self.token_update_callback(
                self.refresh_token,
                self.access_token,
                self.residential_unit,
                self.refresh_token_expires_at
            )
        except Exception as err:
            _LOGGER.warning("Error in token update callback: %s", err, exc_info=True)
    
    async def _populate_claims_from_id_token(self, id_token: str) -> None:
        payload = JwtUtil.decode_token(id_token)
        if not payload:
            return
        
        if not self.extension_occupant_id:
            self.extension_occupant_id = payload.get(ID_TOKEN_CLAIM_OCCUPANT_ID)
        
        if not self.extension_billing_units:
            self.extension_billing_units = payload.get(ID_TOKEN_CLAIM_BILLING_UNITS)
        
        if not self.extension_user_role:
            self.extension_user_role = payload.get(ID_TOKEN_CLAIM_USER_ROLE)
        
        if not self.residential_unit:
            self.residential_unit = payload.get(ID_TOKEN_CLAIM_RESIDENTIAL_UNITS)
    
    def _perform_oauth_flow_sync(self, username, password) -> Dict[str, Any]:
        return OAuthUtil.perform_oauth_flow(self.client_id, username, password)

    async def async_authenticate_with_credentials(self, username: str, password: str) -> Dict[str, Any]:
        """Perform authorization code grant flow with username/password to retrieve tokens.
        
        Args:
            username: User email address
            password: User password
            
        Returns:
            Dictionary containing access_token, refresh_token, id_token, and refresh_token_expires_at
            
        Raises:
            MijntedConnectionError: If network error occurs
            MijntedAuthenticationError: If authentication fails
            MijntedApiError: For other API errors
        """
        try:
            tokens = await self.hass.async_add_executor_job(
                self._perform_oauth_flow_sync, username, password
            )
            
            if "access_token" not in tokens and "id_token" in tokens:
                _LOGGER.debug("Using id_token as access_token")
                tokens["access_token"] = tokens["id_token"]
            
            refresh_token_expires_in = tokens.get("refresh_token_expires_in")
            tokens["refresh_token_expires_at"] = self._calculate_refresh_token_expires_at(refresh_token_expires_in)
            
            _LOGGER.info("Authentication completed successfully for user: %s", username)
            return tokens
            
        except requests.RequestException as exc:
            _LOGGER.error("Network error during authentication: %s", exc, exc_info=True)
            raise MijntedConnectionError(f"Network error: {exc}") from exc
        except (MijntedAuthenticationError, MijntedApiError, MijntedConnectionError):
            raise
        except Exception as exc:
            _LOGGER.exception("Unexpected error during authentication: %s", exc)
            raise MijntedApiError(f"Unexpected error during authentication: {exc}") from exc
    
    async def _rotate_refresh_token_with_credentials(self) -> str:
        if not self.credentials_callback:
            raise MijntedGrantExpiredError(
                "Refresh token expired but no credentials callback available. Please re-authenticate."
            )
        
        _LOGGER.info(
            "Refresh token expired or expiring soon. Using stored credentials to obtain new tokens.",
            extra={"has_residential_unit": bool(self.residential_unit)}
        )
        
        async def _rotate_tokens_attempt() -> str:
            username, password = await self.credentials_callback()
            tokens = await self.async_authenticate_with_credentials(username, password)
            
            access_token = tokens.get("access_token") or tokens.get("id_token")
            if not access_token:
                raise MijntedAuthenticationError("Access token missing in response")
            
            new_refresh_token = tokens.get("refresh_token")
            if not new_refresh_token:
                raise MijntedAuthenticationError("Refresh token missing in response")
            
            self.access_token = access_token
            self.refresh_token = new_refresh_token
            self.refresh_token_expires_at = tokens.get("refresh_token_expires_at")
            
            id_token = tokens.get("id_token")
            if id_token:
                await self._populate_claims_from_id_token(id_token)
            await self._invoke_token_update_callback()
            
            _LOGGER.info(
                "Successfully obtained new tokens using stored credentials",
                extra={"has_residential_unit": bool(self.residential_unit)}
            )
            return self.access_token
        
        try:
            return await RetryUtil.async_retry_with_backoff(
                _rotate_tokens_attempt,
                TOKEN_REFRESH_MAX_RETRIES,
                TOKEN_REFRESH_RETRY_DELAY,
                (Exception,),
                "credential authentication"
            )
        except Exception as err:
            _LOGGER.error(
                "Failed to get new tokens after %d attempts with stored credentials. Credentials may be invalid.",
                TOKEN_REFRESH_MAX_RETRIES + 1,
                extra={"has_residential_unit": bool(self.residential_unit)}
            )
            raise MijntedGrantExpiredError(
                f"Refresh token expired and credential-based refresh failed after {TOKEN_REFRESH_MAX_RETRIES + 1} attempts. Please re-authenticate: {err}"
            ) from err
    
    async def refresh_access_token(self) -> str:
        """Refresh the access token using the refresh token.
        
        The refresh_token grant returns a new refresh_token and access_token.
        The refresh_token_expires_in value remains the same (doesn't reset) until
        a full credential-based authentication is performed.
        
        When the refresh token is expiring (within threshold), it is rotated
        using credentials to get a new refresh token and access token, which
        also resets the refresh_token_expires_in.
        
        Returns:
            New access token string
            
        Raises:
            MijntedAuthenticationError: If authentication fails
            MijntedGrantExpiredError: If refresh token has expired
            MijntedTimeoutError: If request times out
            MijntedConnectionError: If network error occurs after retries exhausted
            MijntedApiError: For other API errors
        """
        if not self.refresh_token:
            raise MijntedAuthenticationError("No refresh token available")
        
        if self.should_proactively_refresh_token():
            return await self._rotate_refresh_token_with_credentials()
        
        data = {
            "client_id": self.client_id,
            "grant_type": OAUTH_GRANT_TYPE_REFRESH_TOKEN,
            "refresh_token": self.refresh_token,
            "scope": f"{self.client_id} {OAUTH_SCOPE}"
        }
        
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        
        async def _refresh_token_attempt() -> str:
            async with self.session.post(self.auth_url, data=data, timeout=timeout) as response:
                if response.status == HTTP_STATUS_OK:
                    result = await response.json()
                    
                    access_token = result.get("access_token")
                    id_token = result.get("id_token")
                    if not access_token and id_token:
                        _LOGGER.debug("No access_token in response, using id_token")
                        access_token = id_token
                    
                    if not access_token:
                        raise MijntedAuthenticationError("Access token missing in response")
                    
                    self.access_token = access_token
                    
                    new_refresh_token = result.get("refresh_token")
                    if new_refresh_token:
                        self.refresh_token = new_refresh_token
                    
                    refresh_token_expires_in = result.get("refresh_token_expires_in")
                    if refresh_token_expires_in is not None:
                        self.refresh_token_expires_at = self._calculate_refresh_token_expires_at(refresh_token_expires_in)
                    
                    await self._invoke_token_update_callback()
                    
                    return self.access_token
                else:
                    try:
                        error_json = await response.json()
                        error_code, error_description = ResponseParserUtil.parse_error_response(error_json)
                    except (ValueError, KeyError):
                        error_code, error_description = ("", "")
                    
                    _LOGGER.error(
                        "Token refresh failed: HTTP %d - %s",
                        response.status,
                        error_code or error_description or "Unknown error",
                        extra={"status_code": response.status, "has_residential_unit": bool(self.residential_unit)}
                    )
                    
                    if response.status in (HTTP_STATUS_UNAUTHORIZED, HTTP_STATUS_BAD_REQUEST) and error_code == OAUTH_ERROR_INVALID_GRANT:
                        _LOGGER.warning("Refresh token invalid, attempting to rotate with credentials")
                        return await self._rotate_refresh_token_with_credentials()
                    
                    if response.status == HTTP_STATUS_UNAUTHORIZED:
                        raise MijntedAuthenticationError(
                            f"Authentication failed: {error_code or error_description or 'Unknown error'}"
                        )
                    raise MijntedApiError(
                        f"Token refresh failed: {response.status} - {error_code or error_description or 'Unknown error'}"
                    )
        
        try:
            return await RetryUtil.async_retry_with_backoff(
                _refresh_token_attempt,
                TOKEN_REFRESH_MAX_RETRIES,
                TOKEN_REFRESH_RETRY_DELAY,
                (aiohttp.ClientError,),
                "token refresh"
            )
        except (TimeoutError, asyncio.TimeoutError) as err:
            _LOGGER.error("Timeout during token refresh: %s", err, extra={"timeout": REQUEST_TIMEOUT})
            raise MijntedTimeoutError("Timeout during token refresh") from err
        except (MijntedAuthenticationError, MijntedApiError, MijntedGrantExpiredError):
            raise
        except Exception as err:
            _LOGGER.exception("Unexpected error during token refresh: %s", err)
            raise MijntedApiError(f"Unexpected error during token refresh: {err}") from err
    
    def is_access_token_expired(self, token: Optional[str] = None) -> bool:
        """Check if the access token is expired.
        
        Args:
            token: Access token to check (defaults to self.access_token)
            
        Returns:
            True if access token is expired or invalid, False if valid
        """
        token_to_check = token or self.access_token
        if not token_to_check:
            return True
        
        return JwtUtil.is_token_expired(token_to_check)
    
    def should_proactively_refresh_token(self) -> bool:
        """Check if refresh token should be refreshed.
        
        Returns:
            True if refresh token is expired or expiring within 15 minutes, False otherwise
        """
        if not self.refresh_token_expires_at:
            return True
        
        now = datetime.now(timezone.utc)
        time_remaining = (self.refresh_token_expires_at - now).total_seconds()
        
        return time_remaining < REFRESH_TOKEN_PROACTIVE_REFRESH_THRESHOLD_SECONDS
    
    async def authenticate(self) -> None:
        """Authenticate with the Mijnted API using refresh token.
        
        Refreshes refresh token if expired or expiring within 15 minutes, otherwise
        always requests a new access token for every update/polling cycle.
        """
        await self.refresh_access_token()

