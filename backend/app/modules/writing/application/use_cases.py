from app.core.unit_of_work import UnitOfWork
from app.modules.writing.domain.entities import Draft, DraftVersion
from app.modules.writing.domain.enums import CreatedBy
from app.modules.writing.domain.repositories import DraftRepository, DraftVersionRepository


class CreateDraftUseCase:
    """Stage 2's minimal persistence-oriented entry point (Project_Writing_Implementation_
    Plan.md §18 Stage 2; Stage 2 prompt §21) - creates the stable writing-workspace object.
    Deliberately does not touch AI providers, retrieval, or Work Items: no generation happens
    here or anywhere in Stage 2.
    """

    def __init__(self, draft_repository: DraftRepository, unit_of_work: UnitOfWork) -> None:
        self._drafts = draft_repository
        self._uow = unit_of_work

    def execute(self, *, agent_id: int, title: str, target: str | None = None) -> Draft:
        draft = Draft.create(agent_id=agent_id, title=title, target=target)
        try:
            persisted = self._drafts.add(draft)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
        return persisted


class CreateDraftVersionUseCase:
    """Assigns the next `version_number` for a Draft and persists the new, immutable
    Draft Version (04_Logical_Data_Model.md §3.16: "versions are strictly ordered per draft";
    §6: the current version is the latest version_number, never a stored attribute - so this
    use case computes it from existing versions rather than reading/writing a pointer field).

    Does not perform generation: `content` is supplied by the caller (a human-authored draft,
    or - in a later stage - the Generation Gateway's output). No LLM call, no context
    assembly, and no provider dependency exists in this module (Stage 2 prompt §21/§22).
    """

    def __init__(self, draft_version_repository: DraftVersionRepository, unit_of_work: UnitOfWork) -> None:
        self._versions = draft_version_repository
        self._uow = unit_of_work

    def execute(self, *, draft_id: int, content: str, created_by: CreatedBy = CreatedBy.USER) -> DraftVersion:
        latest = self._versions.get_latest_by_draft_id(draft_id)
        next_version_number = latest.version_number + 1 if latest is not None else 1
        version = DraftVersion(
            draft_id=draft_id, version_number=next_version_number, content=content, created_by=created_by
        )
        try:
            persisted = self._versions.add(version)
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise
        return persisted
