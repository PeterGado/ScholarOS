import re

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth.infrastructure import SqlAlchemyPasswordResetTokenRepository, SqlAlchemyUserCredentialLookup
from app.auth.password_reset import RequestPasswordResetUseCase
from app.core.dependencies import get_db, get_request_password_reset_use_case
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app
from tests.e2e.conftest import AUTH_PASSWORD as PASSWORD
from tests.e2e.conftest import AUTH_USERNAME as USERNAME

_TOKEN_LINK_PATTERN = re.compile(r"reset-password\?token=([^\"&<\s]+)")


def _install_fake_email_sender(sent: list[dict]):
    """Overrides the real Resend-backed use case with one whose email_sender just records the
    call, so this test exercises the real token-creation/DB-write path but never calls the
    real network (no test may call a real external provider).
    """

    def override(db: Session = Depends(get_db)) -> RequestPasswordResetUseCase:
        def fake_sender(**kwargs):
            sent.append(kwargs)

        return RequestPasswordResetUseCase(
            SqlAlchemyUserCredentialLookup(db),
            SqlAlchemyPasswordResetTokenRepository(db),
            SqlAlchemyUnitOfWork(db),
            token_ttl_minutes=60,
            frontend_base_url="http://localhost:5173",
            resend_api_key="re_test",
            from_address="ScholarOS <onboarding@resend.dev>",
            email_sender=fake_sender,
        )

    app.dependency_overrides[get_request_password_reset_use_case] = override


def _extract_token(html: str) -> str:
    match = _TOKEN_LINK_PATTERN.search(html)
    assert match is not None, f"no reset token link found in email html: {html!r}"
    return match.group(1)


def test_full_reset_flow_lets_a_user_sign_in_with_a_new_password(client, provisioned_user):
    sent: list[dict] = []
    _install_fake_email_sender(sent)
    try:
        # provisioned_user has no email on file yet - add one, same as a real user would via Settings.
        login_response = client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
        token = login_response.json()["access_token"]
        client.put("/auth/email", json={"email": "researcher@example.com"}, headers={"Authorization": f"Bearer {token}"})

        request_response = client.post("/auth/password-reset/request", json={"email": "researcher@example.com"})
        assert request_response.status_code == 204
        assert len(sent) == 1
        assert sent[0]["to"] == "researcher@example.com"
        raw_token = _extract_token(sent[0]["html"])

        confirm_response = client.post(
            "/auth/password-reset/confirm", json={"token": raw_token, "new_password": "a-brand-new-password"}
        )
        assert confirm_response.status_code == 204

        old_password_login = client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
        assert old_password_login.status_code == 401

        new_password_login = client.post(
            "/auth/login", json={"username": USERNAME, "password": "a-brand-new-password"}
        )
        assert new_password_login.status_code == 200
    finally:
        app.dependency_overrides.pop(get_request_password_reset_use_case, None)


def test_a_successful_reset_ends_the_sessions_that_existed_before_it(client, provisioned_user):
    sent: list[dict] = []
    _install_fake_email_sender(sent)
    try:
        login_response = client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
        old_token = login_response.json()["access_token"]
        client.put(
            "/auth/email", json={"email": "researcher2@example.com"}, headers={"Authorization": f"Bearer {old_token}"}
        )
        assert client.get("/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 204

        client.post("/auth/password-reset/request", json={"email": "researcher2@example.com"})
        raw_token = _extract_token(sent[0]["html"])
        client.post("/auth/password-reset/confirm", json={"token": raw_token, "new_password": "a-brand-new-password"})

        # The pre-reset session must no longer be valid - the whole point of ending all
        # sessions is to kick out anyone who already had access (see ConfirmPasswordResetUseCase).
        assert client.get("/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
    finally:
        app.dependency_overrides.pop(get_request_password_reset_use_case, None)


def test_requesting_a_reset_for_an_unknown_email_still_returns_204(client):
    response = client.post("/auth/password-reset/request", json={"email": "nobody@example.com"})

    assert response.status_code == 204


def test_confirming_with_an_unknown_token_returns_401(client):
    response = client.post(
        "/auth/password-reset/confirm", json={"token": "never-issued", "new_password": "a-brand-new-password"}
    )

    assert response.status_code == 401


def test_confirming_with_a_weak_new_password_returns_422(client, provisioned_user):
    sent: list[dict] = []
    _install_fake_email_sender(sent)
    try:
        login_response = client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
        token = login_response.json()["access_token"]
        client.put(
            "/auth/email", json={"email": "researcher3@example.com"}, headers={"Authorization": f"Bearer {token}"}
        )
        client.post("/auth/password-reset/request", json={"email": "researcher3@example.com"})
        raw_token = _extract_token(sent[0]["html"])

        response = client.post("/auth/password-reset/confirm", json={"token": raw_token, "new_password": "short"})

        assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_request_password_reset_use_case, None)


def test_a_used_token_cannot_be_replayed(client, provisioned_user):
    sent: list[dict] = []
    _install_fake_email_sender(sent)
    try:
        login_response = client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
        token = login_response.json()["access_token"]
        client.put(
            "/auth/email", json={"email": "researcher4@example.com"}, headers={"Authorization": f"Bearer {token}"}
        )
        client.post("/auth/password-reset/request", json={"email": "researcher4@example.com"})
        raw_token = _extract_token(sent[0]["html"])

        first = client.post(
            "/auth/password-reset/confirm", json={"token": raw_token, "new_password": "a-brand-new-password"}
        )
        assert first.status_code == 204

        second = client.post(
            "/auth/password-reset/confirm", json={"token": raw_token, "new_password": "a-different-password"}
        )
        assert second.status_code == 401
    finally:
        app.dependency_overrides.pop(get_request_password_reset_use_case, None)
