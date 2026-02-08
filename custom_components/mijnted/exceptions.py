class MijntedApiError(Exception):
    """Base exception for Mijnted API errors."""
    pass


class MijntedAuthenticationError(MijntedApiError):
    """Exception for authentication errors."""
    pass


class MijntedGrantExpiredError(MijntedAuthenticationError):
    """Exception for when the OAuth grant (refresh token) has expired.
    
    This occurs when the refresh token itself expires and automatic refresh
    using stored credentials fails after retries. The user must re-authenticate
    to obtain a new refresh token.
    """
    pass


class MijntedConnectionError(MijntedApiError):
    """Exception for connection errors."""
    pass


class MijntedTimeoutError(MijntedApiError):
    """Exception for timeout errors."""
    pass

