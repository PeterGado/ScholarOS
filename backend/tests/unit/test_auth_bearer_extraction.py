import pytest
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import extract_bearer_token
from app.auth.exceptions import InvalidSessionError


def test_valid_bearer_credentials_return_the_raw_token():
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="a-real-token")
    assert extract_bearer_token(credentials) == "a-real-token"


def test_missing_credentials_raise_invalid_session():
    with pytest.raises(InvalidSessionError):
        extract_bearer_token(None)


def test_a_non_bearer_scheme_raises_invalid_session():
    credentials = HTTPAuthorizationCredentials(scheme="Basic", credentials="dXNlcjpwYXNz")
    with pytest.raises(InvalidSessionError):
        extract_bearer_token(credentials)


def test_scheme_matching_is_case_insensitive():
    credentials = HTTPAuthorizationCredentials(scheme="bearer", credentials="a-real-token")
    assert extract_bearer_token(credentials) == "a-real-token"
