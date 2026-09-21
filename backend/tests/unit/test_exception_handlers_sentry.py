"""Sentry integration scope (2026-09-21): only genuinely unexpected/unhandled exceptions are
reported - routine domain errors (401/404/409/422s) are normal control flow, not crashes, and
must never generate a Sentry event. Exercised directly against the handler functions (async,
trivially callable without spinning up the whole app) rather than through real HTTP, since the
only thing under test is "did capture_exception get called", not routing/response shape (already
covered elsewhere). Run via asyncio.run() rather than pytest.mark.asyncio - this project has no
pytest-asyncio dependency, matching every other async-function unit test in this suite.
"""

import asyncio
from unittest.mock import patch

import pytest

from app.api.exception_handlers import (
    _handle_domain_error,
    _handle_invalid_input,
    _handle_not_found,
    _handle_unauthorized,
    _handle_unexpected_error,
)
from app.core.exceptions import ScholarOSError


def test_unexpected_error_is_reported_to_sentry():
    exc = RuntimeError("genuinely unanticipated failure")
    with patch("app.api.exception_handlers.sentry_sdk.capture_exception") as capture:
        asyncio.run(_handle_unexpected_error(request=None, exc=exc))

    capture.assert_called_once_with(exc)


def test_unexpected_error_response_shape_is_unaffected_by_sentry():
    response = asyncio.run(_handle_unexpected_error(request=None, exc=RuntimeError("boom")))

    assert response.status_code == 500


@pytest.mark.parametrize(
    "handler,exc",
    [
        (_handle_not_found, ScholarOSError("not found")),
        (_handle_invalid_input, ScholarOSError("invalid")),
        (_handle_unauthorized, ScholarOSError("unauthorized")),
        (_handle_domain_error, ScholarOSError("conflict")),
    ],
)
def test_routine_domain_errors_are_never_reported_to_sentry(handler, exc):
    with patch("app.api.exception_handlers.sentry_sdk.capture_exception") as capture:
        asyncio.run(handler(request=None, exc=exc))

    capture.assert_not_called()
