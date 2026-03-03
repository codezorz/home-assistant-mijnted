"""Tests for utils/jwt_util.py."""
import time

import jwt as pyjwt
import pytest

from custom_components.mijnted.utils.jwt_util import JwtUtil


def _make_token(payload: dict, exp_offset: int | None = None) -> str:
    """Helper to create a signed JWT for testing."""
    if exp_offset is not None:
        payload["exp"] = int(time.time()) + exp_offset
    return pyjwt.encode(payload, "secret", algorithm="HS256")


class TestDecodeToken:
    def test_valid_token(self):
        token = _make_token({"sub": "user1", "role": "admin"})
        decoded = JwtUtil.decode_token(token)
        assert decoded is not None
        assert decoded["sub"] == "user1"

    def test_invalid_token(self):
        assert JwtUtil.decode_token("not.a.jwt") is None

    def test_empty_string(self):
        assert JwtUtil.decode_token("") is None


class TestGetFirstClaimValue:
    def test_string_value(self):
        assert JwtUtil.get_first_claim_value("hello") == "hello"

    def test_list_value(self):
        assert JwtUtil.get_first_claim_value(["a", "b"]) == "a"

    def test_empty_list(self):
        assert JwtUtil.get_first_claim_value([]) is None

    def test_none(self):
        assert JwtUtil.get_first_claim_value(None) is None

    def test_none_with_default(self):
        assert JwtUtil.get_first_claim_value(None, default="fallback") == "fallback"

    def test_empty_string_with_default(self):
        assert JwtUtil.get_first_claim_value("", default="fallback") == "fallback"

    def test_list_of_ints(self):
        assert JwtUtil.get_first_claim_value([42, 99]) == "42"


class TestIsTokenExpired:
    def test_valid_token_not_expired(self):
        token = _make_token({"sub": "u"}, exp_offset=3600)
        assert JwtUtil.is_token_expired(token) is False

    def test_expired_token(self):
        token = _make_token({"sub": "u"}, exp_offset=-3600)
        assert JwtUtil.is_token_expired(token) is True

    def test_no_exp_claim(self):
        token = _make_token({"sub": "u"})
        assert JwtUtil.is_token_expired(token) is True

    def test_garbage_token(self):
        assert JwtUtil.is_token_expired("garbage") is True
