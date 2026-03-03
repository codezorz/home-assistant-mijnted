"""Tests for exceptions.py."""
import pytest

from custom_components.mijnted.exceptions import (
    MijntedApiError,
    MijntedAuthenticationError,
    MijntedConnectionError,
    MijntedGrantExpiredError,
    MijntedTimeoutError,
)


class TestExceptionHierarchy:
    def test_api_error_is_exception(self):
        assert issubclass(MijntedApiError, Exception)

    def test_auth_error_is_api_error(self):
        assert issubclass(MijntedAuthenticationError, MijntedApiError)

    def test_grant_expired_is_auth_error(self):
        assert issubclass(MijntedGrantExpiredError, MijntedAuthenticationError)

    def test_connection_error_is_api_error(self):
        assert issubclass(MijntedConnectionError, MijntedApiError)

    def test_timeout_error_is_api_error(self):
        assert issubclass(MijntedTimeoutError, MijntedApiError)


class TestExceptionUsage:
    def test_raise_and_catch_api_error(self):
        with pytest.raises(MijntedApiError, match="something broke"):
            raise MijntedApiError("something broke")

    def test_catch_auth_as_api(self):
        with pytest.raises(MijntedApiError):
            raise MijntedAuthenticationError("bad creds")

    def test_catch_grant_expired_as_auth(self):
        with pytest.raises(MijntedAuthenticationError):
            raise MijntedGrantExpiredError("token gone")

    def test_catch_grant_expired_as_api(self):
        with pytest.raises(MijntedApiError):
            raise MijntedGrantExpiredError("token gone")
