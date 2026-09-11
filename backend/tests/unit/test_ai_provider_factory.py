import pytest

from app.ai.exceptions import ProviderConfigurationError
from app.ai.providers.factory import create_provider
from app.ai.providers.google_genai import GoogleGenAIProvider
from app.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.core.config import Settings


def test_dispatches_to_google_genai_by_default():
    settings = Settings(ai_api_key="test-key")
    assert settings.ai_provider == "google_genai"
    provider = create_provider(settings)
    assert isinstance(provider, GoogleGenAIProvider)


def test_dispatches_to_openai_compatible_when_selected():
    settings = Settings(ai_provider="openai_compatible", ai_api_key="test-key", ai_base_url="https://example.test/v1")
    provider = create_provider(settings)
    assert isinstance(provider, OpenAICompatibleProvider)


def test_unknown_provider_raises_configuration_error():
    settings = Settings(ai_provider="not-a-real-provider", ai_api_key="test-key")
    with pytest.raises(ProviderConfigurationError):
        create_provider(settings)
