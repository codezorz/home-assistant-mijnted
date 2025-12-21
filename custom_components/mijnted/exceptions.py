

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

