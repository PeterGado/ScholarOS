import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_fake_ai_provider_is_rejected_in_production():
    with pytest.raises(ValidationError):
        Settings(environment="production", ai_provider="fake")


def test_fake_ai_provider_is_allowed_outside_production():
    settings = Settings(environment="test", ai_provider="fake")
    assert settings.ai_provider == "fake"


def test_a_real_provider_is_allowed_in_production():
    settings = Settings(environment="production", ai_provider="google_genai")
    assert settings.ai_provider == "google_genai"
