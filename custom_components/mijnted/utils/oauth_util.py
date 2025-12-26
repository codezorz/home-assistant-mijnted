import logging
import re
import uuid
import urllib.parse
import pkce
import requests
from typing import Dict, Any, Tuple, Optional

from ..const import (
    AUTH_AUTHORIZE_URL,
    AUTH_TOKEN_URL,
    AUTH_LOGIN_URL,
    AUTH_CONFIRM_URL,
    AUTH_POLICY,
    AUTH_TENANT_NAME,
    AUTH_REDIRECT_URI,
    AUTH_USER_AGENT,
    HTTP_STATUS_OK,
    OAUTH_SCOPE,
    OAUTH_GRANT_TYPE_AUTHORIZATION_CODE,
    OAUTH_RESPONSE_TYPE_CODE,
    OAUTH_CODE_CHALLENGE_METHOD,
    OAUTH_RESPONSE_MODE,
    OAUTH_REQUEST_TYPE_RESPONSE,
    OAUTH_REMEMBER_ME_FALSE,
    CONTENT_TYPE_FORM_URLENCODED,
    HEADER_X_REQUESTED_WITH,
)
from ..exceptions import (
    MijntedApiError,
    MijntedAuthenticationError,
    MijntedConnectionError,
)

_LOGGER = logging.getLogger(__name__)


class OAuthUtil:
    """Utility class for OAuth 2.0 authorization code flow."""
    
    _CSRF_TOKEN_PATTERN = re.compile(r'["\']csrf["\']\s*:\s*["\']([^"\']+)["\']')
    _TRANSACTION_ID_PATTERN = re.compile(r'["\']transId["\']\s*:\s*["\']([^"\']+)["\']')
    _AUTH_CODE_PATTERN = re.compile(r'code=([A-Za-z0-9\-\_]+)')
    
    @staticmethod
    def _parse_csrf_token(html_text: str) -> Optional[str]:
        """Extract CSRF token from authorization page HTML.
        
        Args:
            html_text: HTML content from authorization page
            
        Returns:
            CSRF token string if found, None otherwise
        """
        if not html_text or not isinstance(html_text, str):
            return None
        
        match = OAuthUtil._CSRF_TOKEN_PATTERN.search(html_text)
        if match:
            return match.group(1)
        return None
    
    @staticmethod
    def _parse_transaction_id(html_text: str) -> Optional[str]:
        """Extract transaction ID from authorization page HTML.
        
        Args:
            html_text: HTML content from authorization page
            
        Returns:
            Transaction ID string if found, None otherwise
        """
        if not html_text or not isinstance(html_text, str):
            return None
        
        match = OAuthUtil._TRANSACTION_ID_PATTERN.search(html_text)
        if match:
            return match.group(1)
        return None
    
    @staticmethod
    def _parse_authorization_code_from_location(location_header: str) -> Optional[str]:
        """Parse authorization code from Location header.
        
        Args:
            location_header: Location header value from redirect response
            
        Returns:
            Authorization code if found, None otherwise
        """
        if not location_header or not isinstance(location_header, str):
            return None
        
        try:
            parsed = urllib.parse.urlparse(location_header)
            qs = urllib.parse.parse_qs(parsed.query)
            if 'code' in qs and qs['code']:
                code = qs['code'][0]
                if code:
                    return code
        except (ValueError, AttributeError, IndexError) as err:
            _LOGGER.debug("Failed to parse authorization code from Location header: %s", err)
        
        return None
    
    @staticmethod
    def _parse_authorization_code_from_body(response_text: str) -> Optional[str]:
        """Parse authorization code from response body.
        
        Args:
            response_text: Response body text
            
        Returns:
            Authorization code if found, None otherwise
        """
        if not response_text or not isinstance(response_text, str):
            return None
        
        if 'code=' not in response_text:
            return None
        
        match = OAuthUtil._AUTH_CODE_PATTERN.search(response_text)
        if match:
            return match.group(1)
        return None
    
    @staticmethod
    def extract_csrf_and_transaction_id(html_text: str) -> Tuple[str, str]:
        """Extract CSRF token and transaction ID from authorization page HTML.
        
        Args:
            html_text: HTML content from authorization page
            
        Returns:
            Tuple of (csrf_token, transaction_id)
            
        Raises:
            MijntedApiError: If tokens cannot be extracted
        """
        csrf_token = OAuthUtil._parse_csrf_token(html_text)
        trans_id = OAuthUtil._parse_transaction_id(html_text)
        
        if not csrf_token or not trans_id:
            _LOGGER.error("Could not extract CSRF token or transaction ID from authorization page")
            raise MijntedApiError("Could not initialize login flow (tokens not found)")
        
        return (csrf_token, trans_id)
    
    @staticmethod
    def submit_credentials(
        session: requests.Session,
        csrf_token: str,
        trans_id: str,
        username: str,
        password: str,
        referer_url: str
    ) -> None:
        """Submit credentials via form POST.
        
        Args:
            session: Requests session object
            csrf_token: CSRF token from authorization page
            trans_id: Transaction ID from authorization page
            username: User email address
            password: User password
            referer_url: URL of the authorization page
            
        Raises:
            MijntedConnectionError: If network error occurs
            MijntedAuthenticationError: If credentials are invalid
        """
        post_headers = {
            "X-CSRF-TOKEN": csrf_token,
            "Content-Type": CONTENT_TYPE_FORM_URLENCODED,
            "X-Requested-With": HEADER_X_REQUESTED_WITH,
            "Origin": f"https://{AUTH_TENANT_NAME}.b2clogin.com",
            "Referer": referer_url
        }
        
        data = {
            "request_type": OAUTH_REQUEST_TYPE_RESPONSE,
            "email": username,
            "password": password
        }
        
        login_params = {"tx": trans_id, "p": AUTH_POLICY}
        
        try:
            login_resp = session.post(AUTH_LOGIN_URL, headers=post_headers, data=data, params=login_params)
        except requests.RequestException as exc:
            _LOGGER.error("Network error while submitting credentials: %s", exc)
            raise MijntedConnectionError(f"Network error during login: {exc}") from exc
        
        if login_resp.status_code != HTTP_STATUS_OK:
            _LOGGER.error("Login request failed with HTTP %d", login_resp.status_code)
            raise MijntedAuthenticationError(f"Login failed (HTTP {login_resp.status_code})")
        
        status_ok_str = f'"status":"{HTTP_STATUS_OK}"'
        status_ok_str_spaced = f'"status": "{HTTP_STATUS_OK}"'
        if status_ok_str not in login_resp.text and status_ok_str_spaced not in login_resp.text:
            _LOGGER.warning("Login request returned 200 but status indicates failure")
            raise MijntedAuthenticationError("Invalid credentials or login blocked by server")
    
    @staticmethod
    def extract_authorization_code(confirm_resp: requests.Response) -> str:
        """Extract authorization code from response.
        
        Args:
            confirm_resp: Response from confirmation endpoint
            
        Returns:
            Authorization code string
            
        Raises:
            MijntedApiError: If authorization code cannot be extracted
        """
        location = confirm_resp.headers.get("Location")
        auth_code = None
        
        if location:
            auth_code = OAuthUtil._parse_authorization_code_from_location(location)
        
        if not auth_code:
            auth_code = OAuthUtil._parse_authorization_code_from_body(confirm_resp.text)
        
        if not auth_code:
            _LOGGER.error("Failed to extract authorization code from response. Status: %d, Location: %s",
                         confirm_resp.status_code, location)
            raise MijntedApiError("Authentication successful, but failed to retrieve Authorization Code.")
        
        return auth_code
    
    @staticmethod
    def exchange_code_for_tokens(
        session: requests.Session,
        auth_code: str,
        code_verifier: str,
        client_id: str
    ) -> Dict[str, Any]:
        """Exchange authorization code for tokens.
        
        Args:
            session: Requests session object
            auth_code: Authorization code from redirect
            code_verifier: PKCE code verifier
            client_id: OAuth client ID
            
        Returns:
            Dictionary containing access_token, refresh_token, id_token
            
        Raises:
            MijntedConnectionError: If network error occurs
            MijntedApiError: If response is invalid
            MijntedAuthenticationError: If token exchange fails
        """
        token_data = {
            "grant_type": OAUTH_GRANT_TYPE_AUTHORIZATION_CODE,
            "client_id": client_id,
            "scope": OAUTH_SCOPE,
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
        
        return tokens
    
    @staticmethod
    def perform_oauth_flow(client_id: str, username: str, password: str) -> Dict[str, Any]:
        """Perform complete OAuth 2.0 authorization code flow.
        
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
            client_id: OAuth client ID
            username: User email address
            password: User password
            
        Returns:
            Dictionary containing tokens from the OAuth flow
            
        Raises:
            MijntedConnectionError: If network error occurs
            MijntedAuthenticationError: If authentication fails
            MijntedApiError: For other API errors
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
            "client_id": client_id,
            "redirect_uri": AUTH_REDIRECT_URI,
            "scope": OAUTH_SCOPE,
            "response_type": OAUTH_RESPONSE_TYPE_CODE,
            "code_challenge": code_challenge,
            "code_challenge_method": OAUTH_CODE_CHALLENGE_METHOD,
            "nonce": nonce,
            "response_mode": OAUTH_RESPONSE_MODE
        }
        
        try:
            resp = session.get(AUTH_AUTHORIZE_URL, params=params)
            resp.raise_for_status()
        except requests.RequestException as exc:
            _LOGGER.error("Failed to fetch authorization page: %s", exc)
            raise MijntedConnectionError(f"Failed to fetch authorization page: {exc}") from exc
        
        csrf_token, trans_id = OAuthUtil.extract_csrf_and_transaction_id(resp.text)
        
        OAuthUtil.submit_credentials(session, csrf_token, trans_id, username, password, resp.url)
        
        confirm_params = {
            "rememberMe": OAUTH_REMEMBER_ME_FALSE,
            "csrf_token": csrf_token,
            "tx": trans_id,
            "p": AUTH_POLICY
        }
        
        try:
            confirm_resp = session.get(AUTH_CONFIRM_URL, params=confirm_params, allow_redirects=False)
        except requests.RequestException as exc:
            _LOGGER.error("Network error while retrieving authorization code: %s", exc)
            raise MijntedConnectionError(f"Network error during code retrieval: {exc}") from exc
        
        auth_code = OAuthUtil.extract_authorization_code(confirm_resp)
        
        tokens = OAuthUtil.exchange_code_for_tokens(session, auth_code, code_verifier, client_id)
        
        return tokens


class ResponseParserUtil:
    """Utility class for parsing HTTP responses."""
    
    @staticmethod
    def parse_error_response(response_json: Dict[str, Any]) -> Tuple[str, str]:
        """Extract error code and description from error response.
        
        Args:
            response_json: JSON response dictionary
            
        Returns:
            Tuple of (error_code, error_description)
        """
        if not response_json or not isinstance(response_json, dict):
            return ("", "")
        
        try:
            error_code = response_json.get("error", "")
            error_description = response_json.get("error_description", "")
            error_code = str(error_code) if error_code else ""
            error_description = str(error_description) if error_description else ""
            return (error_code, error_description)
        except (ValueError, KeyError, AttributeError, TypeError) as err:
            _LOGGER.debug("Failed to parse error response: %s", err)
            return ("", "")