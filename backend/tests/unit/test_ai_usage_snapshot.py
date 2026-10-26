from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.ai.usage_snapshot import GetAiUsageSnapshotUseCase


@dataclass
class FakeAiUsageRepository:
    """In-memory stand-in for the AiUsageRepository port - the same shape
    test_ai_usage_guard.py already uses, so the read-only view and the guard are exercised
    against identical ledger semantics.
    """

    records: list[tuple[int, int, datetime]] = field(default_factory=list)

    def record(self, *, user_id: int, tokens: int) -> None:
        self.records.append((user_id, tokens, datetime.now(UTC)))

    def get_usage_since(self, *, user_id: int, since: datetime) -> int:
        return sum(tokens for uid, tokens, recorded_at in self.records if uid == user_id and recorded_at >= since)


def test_a_user_with_no_history_reports_zero_used_and_the_full_budget():
    snapshot = GetAiUsageSnapshotUseCase(FakeAiUsageRepository(), daily_token_cap=1000).execute(user_id=1)

    assert snapshot.used_tokens == 0
    assert snapshot.daily_token_cap == 1000
    assert snapshot.remaining_tokens == 1000


def test_usage_inside_the_window_is_reported_and_subtracted_from_the_budget():
    repository = FakeAiUsageRepository()
    repository.records.append((1, 250, datetime.now(UTC) - timedelta(hours=1)))

    snapshot = GetAiUsageSnapshotUseCase(repository, daily_token_cap=1000).execute(user_id=1)

    assert snapshot.used_tokens == 250
    assert snapshot.remaining_tokens == 750


def test_usage_older_than_the_window_is_not_reported():
    repository = FakeAiUsageRepository()
    repository.records.append((1, 950, datetime.now(UTC) - timedelta(hours=25)))

    snapshot = GetAiUsageSnapshotUseCase(repository, daily_token_cap=1000).execute(user_id=1)

    assert snapshot.used_tokens == 0
    assert snapshot.remaining_tokens == 1000


def test_no_configured_cap_reports_unlimited_rather_than_zero():
    repository = FakeAiUsageRepository()
    repository.record(user_id=1, tokens=500)

    snapshot = GetAiUsageSnapshotUseCase(repository, daily_token_cap=None).execute(user_id=1)

    assert snapshot.used_tokens == 500
    assert snapshot.daily_token_cap is None
    assert snapshot.remaining_tokens is None  # unlimited, never 0


def test_usage_over_the_cap_never_reports_a_negative_budget():
    repository = FakeAiUsageRepository()
    repository.record(user_id=1, tokens=1500)

    snapshot = GetAiUsageSnapshotUseCase(repository, daily_token_cap=1000).execute(user_id=1)

    assert snapshot.used_tokens == 1500
    assert snapshot.remaining_tokens == 0


def test_usage_is_reported_per_user():
    repository = FakeAiUsageRepository()
    repository.record(user_id=1, tokens=900)
    use_case = GetAiUsageSnapshotUseCase(repository, daily_token_cap=1000)

    assert use_case.execute(user_id=1).used_tokens == 900
    assert use_case.execute(user_id=2).used_tokens == 0


def test_the_reported_window_matches_the_guards_own_window():
    """The snapshot must describe the same window the guard enforces, or the reported budget
    and the actual rejection point would disagree.
    """
    snapshot = GetAiUsageSnapshotUseCase(FakeAiUsageRepository(), daily_token_cap=1000).execute(user_id=1)

    assert snapshot.window_hours == 24.0
