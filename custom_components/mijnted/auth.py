import aiohttp
import asyncio
import jwt
import logging
import re
import urllib.parse
import uuid
import pkce
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Callable, Awaitable, Tuple
from homeassistant.core import HomeAssistant

from .const import (
    AUTH_URL,
    REQUEST_TIMEOUT,
    TOKEN_REFRESH_MAX_RETRIES,
    TOKEN_REFRESH_RETRY_DELAY,
    RESIDENTIAL_UNITS_CLAIM,
    RESIDENTIAL_UNITS_CLAIM_ALT,
    HTTP_STATUS_OK,
    HTTP_STATUS_UNAUTHORIZED,
    REFRESH_TOKEN_PROACTIVE_REFRESH_THRESHOLD_SECONDS,
    AUTH_AUTHORIZE_URL,
    AUTH_TOKEN_URL,
    AUTH_LOGIN_URL,
    AUTH_CONFIRM_URL,
    AUTH_POLICY,
    AUTH_TENANT_NAME,
    AUTH_REDIRECT_URI,
    AUTH_USER_AGENT,
)
from .utils import ListUtil
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

    def _calculate_refresh_token_expires_at(self, refresh_token_expires_in: Optional[Any]) -> datetime:
        """Calculate refresh token expiration datetime.
        
        Args:
            refresh_token_expires_in: Expiration time in seconds, or None
            
        Returns:
            Datetime when refresh token expires (defaults to 24 hours if not provided)
        """
        if refresh_token_expires_in is not None:
            try:
                expires_in_seconds = int(refresh_token_expires_in)
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
                _LOGGER.debug("Refresh token expires in %d seconds (at %s)", expires_in_seconds, expires_at.isoformat())
                return expires_at
            except (ValueError, TypeError) as err:
                _LOGGER.warning("Could not parse refresh_token_expires_in: %s", refresh_token_expires_in, exc_info=True)
        
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=86400)
        _LOGGER.debug("No expiration info in response, assuming 24 hours")
        return expires_at
    
    async def _invoke_token_update_callback(self) -> None:
        """Invoke the token update callback if available."""
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
    
    async def _extract_residential_unit_from_tokens(self, id_token: Optional[str] = None) -> None:
        """Extract residential unit from id_token or access_token.
        
        Args:
            id_token: Optional ID token to check first
        """
        if self.residential_unit:
            return
        
        if id_token:
            await self._extract_residential_unit_from_id_token(id_token)
        
        if not self.residential_unit:
            self._extract_residential_unit_from_access_token()
    
    def _extract_residential_unit_from_access_token(self) -> None:
        """Extract residential unit from the current access token."""
        if not self.access_token:
            return
        
        try:
            payload = jwt.decode(self.access_token, options={"verify_signature": False})
            residential_unit = self._extract_residential_unit_from_payload(payload)
            if residential_unit:
                self.residential_unit = residential_unit
        except jwt.DecodeError as err:
            _LOGGER.debug("Could not decode access token: %s", err)
        except Exception as err:
            _LOGGER.debug("Could not extract residential unit from access token: %s", err)
    
    def _perform_oauth_flow_sync(self, username, password) -> Dict[str, Any]:
        """Synchronous version of authentication using 'requests'.
        
        This method simulates a browser-based OAuth 2.0 authorization code flow because
        Azure B2C does not support the password grant type (Resource Owner Password Credentials).
        Instead, we must:
        1. Fetch the authorization page to obtain CSRF token and transaction ID
        2. Submit credentials via form POST (simulating browser login)
        3. Follow redirects to obtain the authorization code
        4. Exchange the authorization code for tokens (access_token, refresh_token, id_token)
        
        This approach allows us to obtain refresh tokens that can be used for subsequent
        authentication without requiring user interaction.
        
        Args:
            username: User email address
            password: User password
            
        Returns:
            Dictionary containing tokens from the OAuth flow
        """
        _LOGGER.info("Starting authentication flow for user: %s", username)
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': AUTH_USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        })
        
        code_verifier, code_challenge = pkce.generate_pkce_pair()
        nonce = str(uuid.uuid4())
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": AUTH_REDIRECT_URI,
            "scope": "openid profile offline_access",
            "response_type": "code",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "nonce": nonce,
            "response_mode": "query"
        }
        
        _LOGGER.debug("Fetching authorization page")
        try:
            resp = session.get(AUTH_AUTHORIZE_URL, params=params)
            resp.raise_for_status()
        except requests.RequestException as exc:
            _LOGGER.error("Failed to fetch authorization page: %s", exc)
            raise MijntedConnectionError(f"Failed to fetch authorization page: {exc}") from exc
        
        text = resp.text
        csrf_match = re.search(r'["\']csrf["\']\s*:\s*["\']([^"\']+)["\']', text)
        trans_id_match = re.search(r'["\']transId["\']\s*:\s*["\']([^"\']+)["\']', text)
        
        if not csrf_match or not trans_id_match:
            _LOGGER.error("Could not extract CSRF token or transaction ID from authorization page")
            raise MijntedApiError("Could not initialize login flow (tokens not found)")
        
        csrf_token = csrf_match.group(1)
        trans_id = trans_id_match.group(1)
        _LOGGER.debug("Successfully extracted CSRF token and transaction ID")

        _LOGGER.debug("Submitting credentials")
        post_headers = {
            "X-CSRF-TOKEN": csrf_token,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": f"https://{AUTH_TENANT_NAME}.b2clogin.com",
            "Referer": resp.url 
        }
        
        data = {
            "request_type": "RESPONSE",
            "email": username,
            "password": password
        }
        
        login_params = {"tx": trans_id, "p": AUTH_POLICY}
        
        try:
            login_resp = session.post(AUTH_LOGIN_URL, headers=post_headers, data=data, params=login_params)
        except requests.RequestException as exc:
            _LOGGER.error("Network error while submitting credentials: %s", exc)
            raise MijntedConnectionError(f"Network error during login: {exc}") from exc
        
        if login_resp.status_code != 200:
            _LOGGER.error("Login request failed with HTTP %d", login_resp.status_code)
            raise MijntedAuthenticationError(f"Login failed (HTTP {login_resp.status_code})")
            
        if '"status":"200"' not in login_resp.text and '"status": "200"' not in login_resp.text:
            _LOGGER.warning("Login request returned 200 but status indicates failure")
            raise MijntedAuthenticationError("Invalid credentials or login blocked by server")
        
        _LOGGER.debug("Credentials accepted by server")

        _LOGGER.debug("Retrieving authorization code")
        confirm_params = {
            "rememberMe": "false",
            "csrf_token": csrf_token,
            "tx": trans_id,
            "p": AUTH_POLICY
        }
        
        try:
            confirm_resp = session.get(AUTH_CONFIRM_URL, params=confirm_params, allow_redirects=False)
        except requests.RequestException as exc:
            _LOGGER.error("Network error while retrieving authorization code: %s", exc)
            raise MijntedConnectionError(f"Network error during code retrieval: {exc}") from exc
        
        location = confirm_resp.headers.get("Location")
        auth_code = None

        if location:
            parsed = urllib.parse.urlparse(location)
            qs = urllib.parse.parse_qs(parsed.query)
            if 'code' in qs:
                auth_code = qs['code'][0]
                _LOGGER.debug("Authorization code found in Location header")
        
        if not auth_code and 'code=' in confirm_resp.text:
            match = re.search(r'code=([A-Za-z0-9\-\_]+)', confirm_resp.text)
            if match:
                auth_code = match.group(1)
                _LOGGER.debug("Authorization code found in response body")

        if not auth_code:
            _LOGGER.error("Failed to extract authorization code from response. Status: %d, Location: %s", 
                         confirm_resp.status_code, location)
            raise MijntedApiError("Authentication successful, but failed to retrieve Authorization Code.")

        _LOGGER.debug("Exchanging authorization code for tokens")
        token_data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "scope": "openid profile offline_access",
            "code": auth_code,
            "redirect_uri": AUTH_REDIRECT_URI,
            "code_verifier": code_verifier
        }
        
        try:
            token_resp = session.post(AUTH_TOKEN_URL, data=token_data)
            token_resp.raise_for_status()
            tokens = token_resp.json()
        except requests.RequestException as exc:
            _LOGGER.error("Network error during token exchange: %s", exc)
            raise MijntedConnectionError(f"Network error during token exchange: {exc}") from exc
        except ValueError as exc:
            _LOGGER.error("Invalid JSON response from token endpoint: %s", exc)
            raise MijntedApiError(f"Invalid response from token endpoint: {exc}") from exc
        
        if "error" in tokens:
            error_desc = tokens.get('error_description', 'Unknown error')
            _LOGGER.error("Token exchange failed: %s", error_desc)
            raise MijntedAuthenticationError(f"Token exchange failed: {error_desc}")
        
        has_access = "access_token" in tokens
        has_refresh = "refresh_token" in tokens
        has_id = "id_token" in tokens
        _LOGGER.info("Token exchange successful. Tokens received: access_token=%s, refresh_token=%s, id_token=%s",
                    has_access, has_refresh, has_id)
        
        return tokens

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
            raise
    
    async def refresh_access_token(self) -> str:
        """Refresh the access token using the refresh token.
        
        Returns:
            New access token string
            
        Raises:
            MijntedAuthenticationError: If authentication fails
            MijntedTimeoutError: If request times out
            MijntedConnectionError: If network error occurs after retries exhausted
            MijntedApiError: For other API errors
        """
        if not self.refresh_token:
            _LOGGER.warning("Attempted to refresh access token but no refresh token is available")
            raise MijntedAuthenticationError("No refresh token available")
        
        _LOGGER.debug("Refreshing access token (attempt 1/%d)", TOKEN_REFRESH_MAX_RETRIES + 1)
        
        data = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "scope": f"{self.client_id} openid profile offline_access"
        }
        
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        
        for attempt in range(TOKEN_REFRESH_MAX_RETRIES + 1):
            try:
                async with self.session.post(self.auth_url, data=data, timeout=timeout) as response:
                    if response.status == HTTP_STATUS_OK:
                        result = await response.json()
                        self.access_token = result.get("access_token")
                        id_token = result.get("id_token")
                        new_refresh_token = result.get("refresh_token")
                        refresh_token_expires_in = result.get("refresh_token_expires_in")
                        
                        if not self.access_token and id_token:
                            _LOGGER.debug("No access_token in response, using id_token")
                            self.access_token = id_token
                        
                        if not self.access_token:
                            _LOGGER.error("Token refresh succeeded but no access_token or id_token in response")
                            raise MijntedAuthenticationError("Access token missing in response")
                        
                        if new_refresh_token:
                            self.refresh_token = new_refresh_token
                            _LOGGER.debug("Received new refresh token")
                        
                        if new_refresh_token or refresh_token_expires_in is not None:
                            self.refresh_token_expires_at = self._calculate_refresh_token_expires_at(refresh_token_expires_in)
                        
                        await self._extract_residential_unit_from_tokens(id_token)
                        await self._invoke_token_update_callback()
                        
                        _LOGGER.info("Access token refreshed successfully")
                        return self.access_token
                    else:
                        error_text = ""
                        error_code = ""
                        error_description = ""
                        
                        try:
                            error_json = await response.json()
                            error_code = error_json.get("error", "")
                            error_description = error_json.get("error_description", "")
                        except (ValueError, KeyError, Exception):
                            error_code = ""
                            error_description = ""
                        
                        _LOGGER.error(
                            "Token refresh failed: HTTP %d - %s",
                            response.status,
                            error_code or "Unknown error",
                            extra={"status_code": response.status, "has_residential_unit": bool(self.residential_unit)}
                        )
                        if error_description and error_description != error_code:
                            _LOGGER.debug("Token refresh error description: %s", error_description)
                        
                        if (response.status == HTTP_STATUS_UNAUTHORIZED or response.status == 400) and error_code == "invalid_grant":
                            error_lower = (error_description or "").lower()
                            if "grant has expired" in error_lower:
                                if self.credentials_callback:
                                    _LOGGER.info(
                                        "Refresh token grant has expired. Attempting re-authentication with stored credentials.",
                                        extra={"has_residential_unit": bool(self.residential_unit)}
                                    )
                                    try:
                                        username, password = await self.credentials_callback()
                                        tokens = await self.async_authenticate_with_credentials(username, password)
                                        
                                        self.access_token = tokens.get("access_token") or tokens.get("id_token")
                                        if not self.access_token:
                                            raise MijntedAuthenticationError("Access token missing in response")
                                        
                                        new_refresh_token = tokens.get("refresh_token")
                                        if new_refresh_token:
                                            self.refresh_token = new_refresh_token
                                        
                                        refresh_token_expires_at = tokens.get("refresh_token_expires_at")
                                        if refresh_token_expires_at:
                                            self.refresh_token_expires_at = refresh_token_expires_at
                                        
                                        id_token = tokens.get("id_token")
                                        await self._extract_residential_unit_from_tokens(id_token)
                                        await self._invoke_token_update_callback()
                                        
                                        return self.access_token
                                    except Exception as err:
                                        _LOGGER.warning(
                                            "Re-authentication with stored credentials failed: %s",
                                            err,
                                            extra={"has_residential_unit": bool(self.residential_unit)}
                                        )
                                        raise MijntedGrantExpiredError(
                                            f"Refresh token grant has expired and re-authentication failed: {err}"
                                        ) from err
                                
                                _LOGGER.warning(
                                    "Refresh token grant has expired. Re-authentication required.",
                                    extra={"has_residential_unit": bool(self.residential_unit)}
                                )
                                raise MijntedGrantExpiredError(
                                    f"Refresh token grant has expired. Please re-authenticate: {error_description or 'Unknown error'}"
                                )
                        
                        if response.status == HTTP_STATUS_UNAUTHORIZED:
                            raise MijntedAuthenticationError(f"Authentication failed: {error_code or error_description or 'Unknown error'}")
                        raise MijntedApiError(f"Token refresh failed: {response.status} - {error_code or error_description or 'Unknown error'}")
            except (TimeoutError, asyncio.TimeoutError) as err:
                _LOGGER.error(
                    "Timeout during token refresh: %s",
                    err,
                    extra={"timeout": REQUEST_TIMEOUT}
                )
                raise MijntedTimeoutError("Timeout during token refresh") from err
            except aiohttp.ClientError as err:
                _LOGGER.warning("Network error during token refresh (attempt %d/%d): %s",
                               attempt + 1, TOKEN_REFRESH_MAX_RETRIES + 1, err)
                if attempt < TOKEN_REFRESH_MAX_RETRIES:
                    _LOGGER.info("Retrying token refresh in %d seconds...", TOKEN_REFRESH_RETRY_DELAY)
                    await asyncio.sleep(TOKEN_REFRESH_RETRY_DELAY)
                    _LOGGER.debug("Retrying token refresh (attempt %d/%d)", attempt + 2, TOKEN_REFRESH_MAX_RETRIES + 1)
                    continue
                _LOGGER.error("Token refresh failed after %d attempts: %s", TOKEN_REFRESH_MAX_RETRIES + 1, err)
                raise MijntedConnectionError(f"Network error during token refresh: {err}") from err
            except (MijntedAuthenticationError, MijntedApiError):
                raise
            except Exception as err:
                _LOGGER.exception("Unexpected error during token refresh: %s", err)
                raise MijntedApiError(f"Unexpected error during token refresh: {err}") from err
    
    def _extract_residential_unit_from_payload(self, payload: Dict[str, Any]) -> Optional[str]:
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
        """Extract residential unit from an ID token.
        
        Args:
            id_token: JWT ID token to decode
        """
        try:
            payload = jwt.decode(id_token, options={"verify_signature": False})
            residential_unit = self._extract_residential_unit_from_payload(payload)
            if residential_unit:
                self.residential_unit = residential_unit
        except jwt.DecodeError as err:
            _LOGGER.debug("Could not decode id_token: %s", err)
        except Exception as err:
            _LOGGER.debug("Could not extract residential unit from id_token: %s", err)
    
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
            return True
        except (jwt.DecodeError, Exception):
            return True
    
    def should_proactively_refresh_token(self) -> bool:
        """Check if refresh token should be proactively refreshed.
        
        Returns:
            True if proactive refresh is needed, False otherwise
        """
        if not self.refresh_token_expires_at:
            return True
        
        now = datetime.now(timezone.utc)
        time_remaining = (self.refresh_token_expires_at - now).total_seconds()
        
        if time_remaining < REFRESH_TOKEN_PROACTIVE_REFRESH_THRESHOLD_SECONDS:
            _LOGGER.info(
                "Refresh token within proactive refresh threshold (%.1f hours remaining), refreshing now",
                time_remaining / 3600,
                extra={"has_residential_unit": bool(self.residential_unit)}
            )
            return True
        
        return False
    
    async def authenticate(self) -> None:
        """Authenticate with the Mijnted API using refresh token.
        
        Proactively refreshes refresh token if close to expiration, otherwise
        checks if access token is valid and refreshes if needed.
        """
        if self.should_proactively_refresh_token():
            expires_at_str = self.refresh_token_expires_at.isoformat() if self.refresh_token_expires_at else "unknown"
            _LOGGER.info("Proactively refreshing refresh token before expiration (expires at: %s)", expires_at_str)
            await self.refresh_access_token()
            return
        
        if self.access_token:
            try:
                payload = jwt.decode(self.access_token, options={"verify_signature": False})
                exp = payload.get("exp")
                if exp:
                    exp_time = datetime.fromtimestamp(exp, tz=timezone.utc)
                    if exp_time > datetime.now(timezone.utc):
                        _LOGGER.debug("Access token is still valid (expires at: %s)", exp_time.isoformat())
                        await self._extract_residential_unit_from_tokens()
                        return
                    else:
                        _LOGGER.debug("Access token has expired (expired at: %s)", exp_time.isoformat())
            except jwt.DecodeError:
                _LOGGER.debug("Access token decode failed, refreshing token")
            except Exception as err:
                _LOGGER.debug("Access token validation failed: %s", err)
        
        _LOGGER.debug("Refreshing access token")
        await self.refresh_access_token()

