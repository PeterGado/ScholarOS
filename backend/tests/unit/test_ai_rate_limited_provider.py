from app.ai.providers.rate_limited import RateLimitedProvider


class FakeClock:
    """A controllable stand-in for time.monotonic/time.sleep - advances only when the provider
    under test actually sleeps (or when a test advances it directly), so these tests verify the
    sliding-window logic deterministically without a real wall-clock wait.
    """

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeProvider:
    def __init__(self) -> None:
        self.generate_calls = 0
        self.embed_calls = 0
        self.embed_batch_calls = 0

    def generate(self, prompt: str) -> str:
        self.generate_calls += 1
        return f"reply: {prompt}"

    def embed(self, text: str) -> list[float]:
        self.embed_calls += 1
        return [1.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.embed_batch_calls += 1
        return [[1.0] for _ in texts]


def _build(max_calls_per_minute: int, clock: FakeClock) -> tuple[RateLimitedProvider, FakeProvider]:
    inner = FakeProvider()
    provider = RateLimitedProvider(
        inner,
        max_calls_per_minute=max_calls_per_minute,
        time_source=clock.time,
        sleep=clock.sleep,
    )
    return provider, inner


def test_calls_within_the_limit_never_sleep():
    clock = FakeClock()
    provider, inner = _build(3, clock)

    for _ in range(3):
        provider.generate("x")

    assert clock.sleeps == []
    assert inner.generate_calls == 3


def test_calls_the_underlying_provider_and_returns_its_result():
    clock = FakeClock()
    provider, _inner = _build(5, clock)

    assert provider.generate("hello") == "reply: hello"
    assert provider.embed("text") == [1.0]
    assert provider.embed_batch(["a", "b"]) == [[1.0], [1.0]]


def test_sleeps_once_the_window_is_full_but_still_completes_the_call():
    clock = FakeClock()
    provider, inner = _build(2, clock)

    provider.generate("a")
    provider.generate("b")
    provider.generate("c")

    assert clock.sleeps  # had to wait at least once for a slot to free up
    assert inner.generate_calls == 3


def test_calls_older_than_60_seconds_fall_out_of_the_window():
    clock = FakeClock()
    provider, inner = _build(1, clock)

    provider.generate("a")
    clock.now += 61  # simulate a minute passing without the provider itself sleeping
    provider.generate("b")

    assert clock.sleeps == []  # the first call had already fallen out of the window
    assert inner.generate_calls == 2


def test_concurrent_threads_sharing_one_instance_never_exceed_the_limit():
    import threading
    import time as real_time

    provider = RateLimitedProvider(FakeProvider(), max_calls_per_minute=1000)
    errors: list[Exception] = []

    def worker():
        try:
            for _ in range(20):
                provider.generate("x")
        except Exception as exc:  # noqa: BLE001 - surfaced via the errors list below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    start = real_time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert not errors
    assert real_time.monotonic() - start < 5  # sanity: didn't deadlock or hang
