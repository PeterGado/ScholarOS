from app.modules.writing.application.use_cases import CreateDraftUseCase, CreateDraftVersionUseCase
from app.modules.writing.domain.entities import Draft, DraftVersion
from app.modules.writing.domain.enums import CreatedBy


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class FakeDraftRepository:
    def __init__(self) -> None:
        self._next_id = 1
        self.saved: list[Draft] = []

    def add(self, draft: Draft) -> Draft:
        draft.draft_id = self._next_id
        self._next_id += 1
        self.saved.append(draft)
        return draft

    def get_by_id(self, draft_id):
        return next((d for d in self.saved if d.draft_id == draft_id), None)

    def list_by_agent_id(self, agent_id):
        return [d for d in self.saved if d.agent_id == agent_id]


class FakeDraftVersionRepository:
    def __init__(self) -> None:
        self._next_id = 1
        self.saved: list[DraftVersion] = []

    def add(self, version: DraftVersion) -> DraftVersion:
        version.version_id = self._next_id
        self._next_id += 1
        self.saved.append(version)
        return version

    def get_by_id(self, version_id):
        return next((v for v in self.saved if v.version_id == version_id), None)

    def list_by_draft_id(self, draft_id):
        return sorted((v for v in self.saved if v.draft_id == draft_id), key=lambda v: v.version_number)

    def get_latest_by_draft_id(self, draft_id):
        versions = self.list_by_draft_id(draft_id)
        return versions[-1] if versions else None


def test_create_draft_use_case_persists_and_commits():
    drafts = FakeDraftRepository()
    uow = FakeUnitOfWork()
    use_case = CreateDraftUseCase(drafts, uow)

    draft = use_case.execute(agent_id=1, title="Chapter 1 Draft")

    assert draft.draft_id == 1
    assert uow.committed is True
    assert uow.rolled_back is False


def test_create_draft_version_use_case_assigns_version_number_one_for_first_version():
    versions = FakeDraftVersionRepository()
    uow = FakeUnitOfWork()
    use_case = CreateDraftVersionUseCase(versions, uow)

    version = use_case.execute(draft_id=1, content="Introduction paragraph.")

    assert version.version_number == 1
    assert version.created_by == CreatedBy.USER


def test_create_draft_version_use_case_increments_from_existing_latest():
    versions = FakeDraftVersionRepository()
    uow = FakeUnitOfWork()
    use_case = CreateDraftVersionUseCase(versions, uow)

    use_case.execute(draft_id=1, content="First version.")
    second = use_case.execute(draft_id=1, content="Revised version.")

    assert second.version_number == 2


def test_create_draft_version_use_case_numbers_independently_per_draft():
    versions = FakeDraftVersionRepository()
    uow = FakeUnitOfWork()
    use_case = CreateDraftVersionUseCase(versions, uow)

    use_case.execute(draft_id=1, content="Draft 1 version.")
    other_draft_version = use_case.execute(draft_id=2, content="Draft 2 version.")

    assert other_draft_version.version_number == 1
