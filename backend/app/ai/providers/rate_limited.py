import threading
import time
from collections import deque
from typing import Callable

__all__ = ["RateLimitedProvider"]


class RateLimitedProvider:
    """Wraps a single provider and paces its calls to stay under a per-minute request cap,
    proactively sleeping rather than relying on the provider's own 429 rejection plus
    FailoverProvider's retry-next-key to absorb bursts (2026-09-30, added alongside multi-key
    failover - see app.core.config.Settings.ai_max_calls_per_minute_per_key). A sliding 60s
    window of call timestamps, guarded by a lock so multiple Work Item executor worker threads
    sharing the same underlying key (e.g. after FailoverProvider's randomized starting point
    lands more than one thread on it) wait their turn instead of racing past the limit.

    time_source/sleep are injectable (mirroring this package's other injectable dependencies,
    e.g. GoogleGenAIProvider's `client`) so tests can drive the window deterministically without
    a real wall-clock wait.
    """

    def __init__(
        self,
        provider,
        *,
        max_calls_per_minute: int,
        time_source: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._provider = provider
        self._max_calls_per_minute = max_calls_per_minute
        self._time_source = time_source
        self._sleep = sleep
        self._lock = threading.Lock()
        self._call_times: deque[float] = deque()

    def generate(self, prompt: str) -> str:
        self._wait_for_slot()
        return self._provider.generate(prompt)

    def embed(self, text: str) -> list[float]:
        self._wait_for_slot()
        return self._provider.embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self._wait_for_slot()
        return self._provider.embed_batch(texts)

    def _wait_for_slot(self) -> None:
        while True:
            with self._lock:
                now = self._time_source()
                while self._call_times and now - self._call_times[0] >= 60:
                    self._call_times.popleft()
                if len(self._call_times) < self._max_calls_per_minute:
                    self._call_times.append(now)
                    return
                wait_seconds = 60 - (now - self._call_times[0])
            self._sleep(max(wait_seconds, 0))
