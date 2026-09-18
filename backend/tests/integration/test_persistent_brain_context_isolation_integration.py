"""Mandatory cross-agent isolation test for the full assembled generation context
(Persistent Brain §15/§17): topic, description, research evidence, writing style, and memory
for Agent A must never appear in Agent B's assembled prompt, and vice versa - checked against
real SQLite-persisted rows, not fakes.
"""

import pytest

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.application.use_cases import CreateAgentWorkspaceUseCase
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.project.application.use_cases import CreateProjectUseCase
from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository
from app.modules.writing.domain.context_assembly import (
    ContextAssemblyInput,
    ContextEvidence,
    ContextMemory,
    ContextStyleSignal,
    assemble_context,
)
from app.modules.writing.domain.entities import MemoryRecord, ProfileCharacteristic, WritingProfile
from app.modules.writing.domain.enums import MemoryRecordType, ProfileCharacteristicType
from app.modules.writing.infrastructure.repositories import (
    SqlAlchemyMemoryRecordRepository,
    SqlAlchemyProfileCharacteristicRepository,
    SqlAlchemyWritingProfileRepository,
)


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "persistent_brain_context_isolation_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session_factory = build_sessionmaker(engine)
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.close()
        engine.dispose()


def _make_populated_workspace(session, *, username, topic, description, style_signal, memory_content):
    user = User(username=username)
    session.add(user)
    session.flush()
    agents = SqlAlchemyAgentRepository(session)
    projects = SqlAlchemyProjectRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    workspace = CreateAgentWorkspaceUseCase(agents, CreateProjectUseCase(projects), uow).execute(
        user_id=user.user_id, project_title="Thesis", project_topic=topic
    )
    from app.modules.project.infrastructure.models import Project as ProjectModel

    row = session.get(ProjectModel, workspace.project.project_id)
    row.description = description
    session.flush()

    profile = SqlAlchemyWritingProfileRepository(session).add(
        WritingProfile(agent_id=workspace.agent.agent_id, user_id=user.user_id, name="Style")
    )
    SqlAlchemyProfileCharacteristicRepository(session).add(
        ProfileCharacteristic(
            profile_id=profile.profile_id,
            characteristic_type=ProfileCharacteristicType.VOCABULARY,
            signal=style_signal,
        )
    )
    SqlAlchemyMemoryRecordRepository(session).add(
        MemoryRecord(agent_id=workspace.agent.agent_id, record_type=MemoryRecordType.GUIDANCE, content=memory_content)
    )
    session.commit()
    return workspace


def _assembled_context_for(session, workspace, *, evidence_content: str) -> str:
    from app.modules.project.infrastructure.repositories import SqlAlchemyProjectRepository

    project = SqlAlchemyProjectRepository(session).get_by_agent_id(workspace.agent.agent_id)
    profile = SqlAlchemyWritingProfileRepository(session).get_active_by_agent_id(workspace.agent.agent_id)
    style_signals = tuple(
        ContextStyleSignal(characteristic_type=c.characteristic_type, signal=c.signal, confidence=c.confidence)
        for c in SqlAlchemyProfileCharacteristicRepository(session).list_by_profile_id(profile.profile_id)
    )
    memories = tuple(
        ContextMemory(record_type=m.record_type, content=m.content, rationale=m.rationale)
        for m in SqlAlchemyMemoryRecordRepository(session).list_current_by_agent_id(workspace.agent.agent_id)
    )

    context = ContextAssemblyInput(
        topic=project.topic,
        description=project.description,
        instructions="Write the introduction.",
        evidence=(ContextEvidence(chunk_id=1, content=evidence_content, summary=None, score=0.9),),
        style_signals=style_signals,
        memories=memories,
    )
    return assemble_context(context).prompt


def test_full_assembled_context_never_leaks_across_agents(session):
    workspace_a = _make_populated_workspace(
        session,
        username="user-a",
        topic="Topic A: Coastal erosion",
        description="Description A: a field report for an environmental science course.",
        style_signal="Style signal A: prefers short declarative sentences.",
        memory_content="Memory A: methodology is LIDAR survey data.",
    )
    workspace_b = _make_populated_workspace(
        session,
        username="user-b",
        topic="Topic B: Urban housing policy",
        description="Description B: a policy brief for a graduate seminar.",
        style_signal="Style signal B: prefers passive voice and long clauses.",
        memory_content="Memory B: methodology is a survey of 500 renters.",
    )

    prompt_a = _assembled_context_for(session, workspace_a, evidence_content="Evidence A: shoreline retreat data.")
    prompt_b = _assembled_context_for(session, workspace_b, evidence_content="Evidence B: rent burden statistics.")

    # Agent A's prompt contains only Agent A's data.
    assert "Topic A" in prompt_a
    assert "Description A" in prompt_a
    assert "Style signal A" in prompt_a
    assert "Memory A" in prompt_a
    assert "Evidence A" in prompt_a
    for leaked in ("Topic B", "Description B", "Style signal B", "Memory B", "Evidence B"):
        assert leaked not in prompt_a

    # Agent B's prompt contains only Agent B's data.
    assert "Topic B" in prompt_b
    assert "Description B" in prompt_b
    assert "Style signal B" in prompt_b
    assert "Memory B" in prompt_b
    assert "Evidence B" in prompt_b
    for leaked in ("Topic A", "Description A", "Style signal A", "Memory A", "Evidence A"):
        assert leaked not in prompt_b
