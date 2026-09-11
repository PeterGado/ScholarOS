from app.ai.providers.base import EmbeddingProvider, TextGenerationProvider


class FakeProvider:
    """A minimal double satisfying both provider protocols - used throughout Slice 2's tests
    so no automated test ever calls a real AI provider (Backend_Slice2_Implementation_Plan.md
    §14/§15).
    """

    def __init__(self, generated_text: str = "generated", embedding: list[float] | None = None):
        self.generated_text = generated_text
        self.embedding = embedding if embedding is not None else [0.1, 0.2, 0.3]
        self.prompts_seen: list[str] = []
        self.texts_embedded: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts_seen.append(prompt)
        return self.generated_text

    def embed(self, text: str) -> list[float]:
        self.texts_embedded.append(text)
        return self.embedding


def test_fake_provider_satisfies_text_generation_protocol():
    provider: TextGenerationProvider = FakeProvider(generated_text="hello")
    assert provider.generate("prompt") == "hello"


def test_fake_provider_satisfies_embedding_protocol():
    provider: EmbeddingProvider = FakeProvider(embedding=[1.0, 2.0])
    assert provider.embed("text") == [1.0, 2.0]


def test_fake_provider_records_calls_for_assertions():
    provider = FakeProvider()
    provider.generate("a prompt")
    provider.embed("some text")

    assert provider.prompts_seen == ["a prompt"]
    assert provider.texts_embedded == ["some text"]
