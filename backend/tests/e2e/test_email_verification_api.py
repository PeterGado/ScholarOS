import io
import re

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth.email_verification import RequestEmailVerificationUseCase
from app.auth.infrastructure import (
    SqlAlchemyEmailVerificationTokenRepository,
    SqlAlchemyUserCredentialLookup,
)
from app.core.dependencies import get_db, get_request_email_verification_use_case
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app

_TOKEN_LINK_PATTERN = re.compile(r"verify-email\?token=([^\"&<\s]+)")


def _install_fake_email_sender(sent: list[dict]):
    """Same reasoning as test_password_reset_api.py's own helper - exercises the real
    token-creation/DB-write path but never calls the real network.
    """

    def override(db: Session = Depends(get_db)) -> RequestEmailVerificationUseCase:
        def fake_sender(**kwargs):
            sent.append(kwargs)

        return RequestEmailVerificationUseCase(
            SqlAlchemyUserCredentialLookup(db),
            SqlAlchemyEmailVerificationTokenRepository(db),
            SqlAlchemyUnitOfWork(db),
            token_ttl_minutes=1440,
            frontend_base_url="http://localhost:5173",
            resend_api_key="re_test",
            from_address="ScholarOS <onboarding@resend.dev>",
            email_sender=fake_sender,
        )

    app.dependency_overrides[get_request_email_verification_use_case] = override


def _extract_token(html: str) -> str:
    match = _TOKEN_LINK_PATTERN.search(html)
    assert match is not None, f"no verification token link found in email html: {html!r}"
    return match.group(1)


def _register(client, sent: list[dict], email="new-researcher@example.com", password="a-real-password"):
    _install_fake_email_sender(sent)
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_registering_sends_a_verification_email(client):
    sent: list[dict] = []
    token = _register(client, sent)

    assert len(sent) == 1
    assert sent[0]["to"] == "new-researcher@example.com"

    profile = client.get("/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert profile.json()["email_verified"] is False


def test_upload_is_blocked_until_the_email_is_verified(client, tmp_path):
    sent: list[dict] = []
    token = _register(client, sent)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/agents", json={"project_title": "Thesis", "project_topic": "Topic"}, headers=headers)
    project = client.get("/agents", headers=headers).json()["project"]

    blocked = client.post(
        f"/projects/{project['project_id']}/documents",
        files={"file": ("doc.pdf", io.BytesIO(b"content"), "application/pdf")},
        data={"title": "Doc", "format": "pdf"},
        headers=headers,
    )
    assert blocked.status_code == 403
    assert blocked.json()["error_type"] == "EmailNotVerifiedError"

    raw_token = _extract_token(sent[0]["html"])
    confirm = client.post("/auth/email-verification/confirm", json={"token": raw_token})
    assert confirm.status_code == 204

    allowed = client.post(
        f"/projects/{project['project_id']}/documents",
        files={"file": ("doc.pdf", io.BytesIO(b"content"), "application/pdf")},
        data={"title": "Doc", "format": "pdf"},
        headers=headers,
    )
    assert allowed.status_code == 201


def test_confirming_an_unknown_token_returns_401(client):
    response = client.post("/auth/email-verification/confirm", json={"token": "never-issued"})

    assert response.status_code == 401
    assert response.json()["error_type"] == "InvalidVerificationTokenError"


def test_confirming_an_already_used_token_cannot_be_replayed(client):
    sent: list[dict] = []
    _register(client, sent)
    raw_token = _extract_token(sent[0]["html"])

    first = client.post("/auth/email-verification/confirm", json={"token": raw_token})
    second = client.post("/auth/email-verification/confirm", json={"token": raw_token})

    assert first.status_code == 204
    assert second.status_code == 401


def test_resend_sends_a_fresh_verification_email(client):
    sent: list[dict] = []
    token = _register(client, sent)
    _install_fake_email_sender(sent)

    response = client.post(
        "/auth/email-verification/request", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204
    assert len(sent) == 2  # one from registration, one from the explicit resend


def test_a_pre_existing_account_is_grandfathered_verified(client, provisioned_user):
    from tests.e2e.conftest import AUTH_PASSWORD, AUTH_USERNAME

    login = client.post("/auth/login", json={"username": AUTH_USERNAME, "password": AUTH_PASSWORD})
    token = login.json()["access_token"]

    profile = client.get("/auth/profile", headers={"Authorization": f"Bearer {token}"})

    assert profile.json()["email_verified"] is True
