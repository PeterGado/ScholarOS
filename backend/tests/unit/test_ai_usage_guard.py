from datetime import UTC, datetime, timedelta

import pytest

from app.ai.exceptions import AiUsageQuotaExceededError
from app.ai.provider_usage import ProviderTokenUsage, ProviderUsageMeter
from app.ai.usage_guard import AiUsageGuard


class FakeAiUsageRepository:
    def __init__(self):
        self.records: list[tuple[int, int, datetime]] = []

    def record(self, *, user_id: int, tokens: int) -> None:
        self.records.append((user_id, tokens, datetime.now(UTC)))

    def get_usage_since(self, *, user_id: int, since: datetime) -> int:
        return sum(tokens for uid, tokens, recorded_at in self.records if uid == user_id and recorded_at >= since)


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


# --- the gate (check) -----------------------------------------------------------------------


def test_a_no_configured_cap_never_checks():
    guard = AiUsageGuard(FakeAiUsageRepository(), FakeUnitOfWork(), daily_token_cap=None)

    guard.check(user_id=1, estimated_tokens=999_999_999)  # never raises


def test_a_check_under_the_cap_passes_and_writes_nothing():
    repository = FakeAiUsageRepository()
    uow = FakeUnitOfWork()
    guard = AiUsageGuard(repository, uow, daily_token_cap=1000)

    guard.check(user_id=1, estimated_tokens=100)

    # The split that stops double counting (2026-10-23): an approved check is not usage yet.
    assert repository.records == []
    assert uow.committed is False


def test_a_check_that_would_exceed_the_cap_is_rejected_without_recording():
    repository = FakeAiUsageRepository()
    guard = AiUsageGuard(repository, FakeUnitOfWork(), daily_token_cap=1000)
    repository.record(user_id=1, tokens=950)

    with pytest.raises(AiUsageQuotaExceededError):
        guard.check(user_id=1, estimated_tokens=100)

    assert len(repository.records) == 1


def test_a_check_exactly_at_the_cap_passes():
    repository = FakeAiUsageRepository()
    guard = AiUsageGuard(repository, FakeUnitOfWork(), daily_token_cap=1000)
    repository.record(user_id=1, tokens=900)

    guard.check(user_id=1, estimated_tokens=100)  # 900 + 100 == 1000, not over


def test_usage_from_outside_the_24_hour_window_does_not_count():
    repository = FakeAiUsageRepository()
    guard = AiUsageGuard(repository, FakeUnitOfWork(), daily_token_cap=1000)
    repository.records.append((1, 950, datetime.now(UTC) - timedelta(hours=25)))

    guard.check(user_id=1, estimated_tokens=100)  # would raise if the old usage counted


def test_checks_are_per_user():
    repository = FakeAiUsageRepository()
    guard = AiUsageGuard(repository, FakeUnitOfWork(), daily_token_cap=1000)
    repository.record(user_id=1, tokens=950)

    guard.check(user_id=2, estimated_tokens=100)  # a different user, unaffected by user 1's usage


# --- the ledger (record) --------------------------------------------------------------------


def test_recording_writes_one_row_and_commits():
    repository = FakeAiUsageRepository()
    uow = FakeUnitOfWork()
    guard = AiUsageGuard(repository, uow, daily_token_cap=1000)

    guard.record(user_id=1, tokens=100)

    assert repository.get_usage_since(user_id=1, since=datetime.now(UTC) - timedelta(hours=24)) == 100
    assert uow.committed is True


def test_recording_writes_nothing_when_no_cap_is_configured():
    """Unset disables the whole feature, bookkeeping included - the same convention the file's
    other optional integrations follow (a deployment that opted out of the cap does not get
    ledger rows written for it).
    """
    repository = FakeAiUsageRepository()
    uow = FakeUnitOfWork()
    guard = AiUsageGuard(repository, uow, daily_token_cap=None)

    guard.record(user_id=1, tokens=100)

    assert repository.records == []
    assert uow.committed is False


def test_recording_a_non_positive_amount_writes_nothing():
    repository = FakeAiUsageRepository()
    uow = FakeUnitOfWork()
    guard = AiUsageGuard(repository, uow, daily_token_cap=1000)

    guard.record(user_id=1, tokens=0)

    assert repository.records == []
    assert uow.committed is False


def test_a_failed_write_rolls_back_and_raises():
    class ExplodingRepository(FakeAiUsageRepository):
        def record(self, *, user_id: int, tokens: int) -> None:
            raise RuntimeError("database is down")

    uow = FakeUnitOfWork()
    guard = AiUsageGuard(ExplodingRepository(), uow, daily_token_cap=1000)

    with pytest.raises(RuntimeError):
        guard.record(user_id=1, tokens=100)

    assert uow.rolled_back is True


# --- metered recording ----------------------------------------------------------------------


def test_a_metered_block_records_the_providers_exact_total():
    repository = FakeAiUsageRepository()
    guard = AiUsageGuard(repository, FakeUnitOfWork(), daily_token_cap=1000)
    meter = ProviderUsageMeter()
    meter.observe(ProviderTokenUsage(input_tokens=120, output_tokens=30))

    guard.record_metered(user_id=1, meter=meter, fallback_estimate=999)

    # The real count wins over the estimate, never added on top of it.
    assert repository.records[0][:2] == (1, 150)


def test_an_unobserved_metered_block_falls_back_to_the_estimate():
    """Gemini's embedding endpoint reports no token counts at all - an embedding-only block
    would otherwise record nothing and silently understate usage.
    """
    repository = FakeAiUsageRepository()
    guard = AiUsageGuard(repository, FakeUnitOfWork(), daily_token_cap=1000)
    meter = ProviderUsageMeter()

    guard.record_metered(user_id=1, meter=meter, fallback_estimate=42)

    assert repository.records[0][:2] == (1, 42)


def test_an_unobserved_metered_block_without_a_fallback_records_nothing():
    repository = FakeAiUsageRepository()
    guard = AiUsageGuard(repository, FakeUnitOfWork(), daily_token_cap=1000)

    guard.record_metered(user_id=1, meter=ProviderUsageMeter())

    assert repository.records == []


def test_a_metered_block_that_partly_reported_never_mixes_in_the_estimate():
    repository = FakeAiUsageRepository()
    guard = AiUsageGuard(repository, FakeUnitOfWork(), daily_token_cap=1000)
    meter = ProviderUsageMeter()
    meter.observe(ProviderTokenUsage(input_tokens=10, output_tokens=5))

    guard.record_metered(user_id=1, meter=meter, fallback_estimate=999)

    assert repository.records[0][:2] == (1, 15)
