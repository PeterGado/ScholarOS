from datetime import datetime, timedelta, timezone

import pytest

from app.ai.exceptions import AiUsageQuotaExceededError
from app.ai.usage_guard import AiUsageGuard


class FakeAiUsageRepository:
    def __init__(self):
        self.records: list[tuple[int, int, datetime]] = []

    def record(self, *, user_id: int, tokens: int) -> None:
        self.records.append((user_id, tokens, datetime.now(timezone.utc)))

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


def test_a_no_configured_cap_never_checks_or_records():
    repository = FakeAiUsageRepository()
    guard = AiUsageGuard(repository, FakeUnitOfWork(), daily_token_cap=None)

    guard.check_and_record(user_id=1, estimated_tokens=999_999_999)

    assert repository.records == []


def test_usage_under_the_cap_succeeds_and_is_recorded():
    repository = FakeAiUsageRepository()
    uow = FakeUnitOfWork()
    guard = AiUsageGuard(repository, uow, daily_token_cap=1000)

    guard.check_and_record(user_id=1, estimated_tokens=100)

    assert repository.get_usage_since(user_id=1, since=datetime.now(timezone.utc) - timedelta(hours=24)) == 100
    assert uow.committed is True


def test_usage_that_would_exceed_the_cap_is_rejected_without_recording():
    repository = FakeAiUsageRepository()
    guard = AiUsageGuard(repository, FakeUnitOfWork(), daily_token_cap=1000)
    repository.record(user_id=1, tokens=950)

    with pytest.raises(AiUsageQuotaExceededError):
        guard.check_and_record(user_id=1, estimated_tokens=100)

    assert repository.get_usage_since(user_id=1, since=datetime.now(timezone.utc) - timedelta(hours=24)) == 950


def test_usage_exactly_at_the_cap_succeeds():
    repository = FakeAiUsageRepository()
    guard = AiUsageGuard(repository, FakeUnitOfWork(), daily_token_cap=1000)
    repository.record(user_id=1, tokens=900)

    guard.check_and_record(user_id=1, estimated_tokens=100)  # 900 + 100 == 1000, not over

    assert repository.get_usage_since(user_id=1, since=datetime.now(timezone.utc) - timedelta(hours=24)) == 1000


def test_usage_from_outside_the_24_hour_window_does_not_count():
    repository = FakeAiUsageRepository()
    guard = AiUsageGuard(repository, FakeUnitOfWork(), daily_token_cap=1000)
    repository.records.append((1, 950, datetime.now(timezone.utc) - timedelta(hours=25)))

    guard.check_and_record(user_id=1, estimated_tokens=100)  # would raise if the old usage counted

    assert repository.records[-1] == (1, 100, repository.records[-1][2])


def test_usage_is_tracked_independently_per_user():
    repository = FakeAiUsageRepository()
    guard = AiUsageGuard(repository, FakeUnitOfWork(), daily_token_cap=1000)
    repository.record(user_id=1, tokens=950)

    guard.check_and_record(user_id=2, estimated_tokens=100)  # a different user, unaffected by user 1's usage

    assert repository.get_usage_since(user_id=2, since=datetime.now(timezone.utc) - timedelta(hours=24)) == 100
