import aiohttp
import asyncio
import jwt
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable, Awaitable
from .const import (
    AUTH_URL,
    REQUEST_TIMEOUT,
    TOKEN_REFRESH_MAX_RETRIES,
    TOKEN_REFRESH_RETRY_DELAY,
    RESIDENTIAL_UNITS_CLAIM,
    RESIDENTIAL_UNITS_CLAIM_ALT,
    HTTP_STATUS_OK,
    HTTP_STATUS_UNAUTHORIZED,
)
from .utils import ListUtil
from .exceptions import (
    MijntedApiError,
    MijntedAuthenticationError,
    MijntedConnectionError,
    MijntedTimeoutError,
)

_LOGGER = logging.getLogger(__name__)


class MijntedAuth:
    """Handles authentication for MijnTed API."""
    
    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: str,
        refresh_token: Optional[str] = None,
        access_token: Optional[str] = None,
        residential_unit: Optional[str] = None,
        token_update_callback: Optional[Callable[[str, Optional[str], Optional[str]], Awaitable[None]]] = None
    ):
        """Initialize Mijnted authentication handler.
        
        Args:
            session: aiohttp ClientSession for making requests
            client_id: MijnTed client ID (required)
            refresh_token: Refresh token for authentication
            access_token: Access token (optional, will be refreshed if needed)
            residential_unit: Residential unit identifier
            token_update_callback: Callback for token updates
        """
        if not client_id or not client_id.strip():
            raise ValueError("client_id is required and cannot be empty")
        
        self.session = session
        self.client_id = client_id.strip()
        self.refresh_token = refresh_token
        self.access_token = access_token
        self.residential_unit = residential_unit
        self.auth_url = AUTH_URL
        self.token_update_callback = token_update_callback
    
    async def refresh_access_token(self) -> str:
        """Refresh the access token using the refresh token.
        
        Retries up to 3 times with 10 second wait between attempts for connection errors.
        
        Returns:
            New access token string
            
        Raises:
            MijntedAuthenticationError: If authentication fails
            MijntedTimeoutError: If request times out
            MijntedConnectionError: If network error occurs after retries exhausted
            MijntedApiError: For other API errors
        """
        if not self.refresh_token:
            raise MijntedAuthenticationError("No refresh token available")
        
        # Azure AD B2C refresh token flow
        # Request access_token by including the client_id in scope
        data = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "scope": f"{self.client_id} openid profile offline_access"
        }
        
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        
        for attempt in range(TOKEN_REFRESH_MAX_RETRIES + 1):  # 0, 1, 2 = 3 total attempts
            try:
                async with self.session.post(self.auth_url, data=data, timeout=timeout) as response:
                    if response.status == HTTP_STATUS_OK:
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
                        if response.status == HTTP_STATUS_UNAUTHORIZED:
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
                # Log as WARNING for temporary network errors
                _LOGGER.warning(
                    "Network error during token refresh (attempt %d/%d): %s",
                    attempt + 1,
                    TOKEN_REFRESH_MAX_RETRIES + 1,
                    err,
                    extra={"auth_url": self.auth_url, "attempt": attempt + 1, "max_retries": TOKEN_REFRESH_MAX_RETRIES + 1}
                )
                # Retry if we haven't exhausted attempts
                if attempt < TOKEN_REFRESH_MAX_RETRIES:
                    _LOGGER.info(
                        "Retrying token refresh in %d seconds...",
                        TOKEN_REFRESH_RETRY_DELAY,
                        extra={"attempt": attempt + 1, "max_retries": TOKEN_REFRESH_MAX_RETRIES + 1}
                    )
                    await asyncio.sleep(TOKEN_REFRESH_RETRY_DELAY)
                    continue
                # All retries exhausted
                _LOGGER.warning(
                    "Token refresh failed after %d attempts: %s",
                    TOKEN_REFRESH_MAX_RETRIES + 1,
                    err,
                    extra={"auth_url": self.auth_url, "attempts": TOKEN_REFRESH_MAX_RETRIES + 1}
                )
                raise MijntedConnectionError(f"Network error during token refresh: {err}") from err
            except (MijntedAuthenticationError, MijntedApiError):
                # Don't retry authentication or API errors
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
            first_item = ListUtil.get_first_item(residential_units)
            if first_item is not None:
                return first_item
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
    
    def is_token_expired(self, token: Optional[str] = None) -> bool:
        """Check if a token is expired.
        
        Args:
            token: Token to check (defaults to self.access_token)
            
        Returns:
            True if token is expired or invalid, False if valid
        """
        token_to_check = token or self.access_token
        if not token_to_check:
            return True
        
        try:
            payload = jwt.decode(token_to_check, options={"verify_signature": False})
            exp = payload.get("exp")
            if exp:
                exp_time = datetime.fromtimestamp(exp, tz=timezone.utc)
                return exp_time <= datetime.now(timezone.utc)
            # No expiration claim, consider it expired for safety
            return True
        except (jwt.DecodeError, Exception):
            # Token is invalid or can't be decoded
            return True
    
    async def authenticate(self) -> None:
        """Authenticate with the Mijnted API using refresh token.
        
        Checks if existing access token is valid, otherwise refreshes it.
        """
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

