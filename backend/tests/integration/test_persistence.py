import pytest
from sqlalchemy.exc import IntegrityError

from app.database.session import build_engine, build_sessionmaker, init_db
from app.database.shared_models import User
from app.modules.agent.infrastructure.models import Agent, AgentStatus
from app.modules.document.infrastructure.models import DocumentProcessingStatus, ResearchDocument
from app.modules.project.infrastructure.models import Project


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "persistence_test.db"
    engine = build_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session_factory = build_sessionmaker(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_user(session, username="researcher"):
    user = User(username=username)
    session.add(user)
    session.flush()
    return user


def _make_agent(session, user=None):
    user = user or _make_user(session)
    agent = Agent(user_id=user.user_id)
    session.add(agent)
    session.flush()
    return agent


def _make_project(session, agent=None, **overrides):
    agent = agent or _make_agent(session)
    defaults = {"title": "Thesis Workspace", "topic": "Climate policy adaptation"}
    defaults.update(overrides)
    project = Project(agent_id=agent.agent_id, **defaults)
    session.add(project)
    session.flush()
    return project


# --- Agent -------------------------------------------------------------------


def test_agent_persists_and_retrieves(db_session):
    user = _make_user(db_session)
    agent = Agent(user_id=user.user_id)
    db_session.add(agent)
    db_session.commit()

    fetched = db_session.get(Agent, agent.agent_id)
    assert fetched is not None
    assert fetched.user_id == user.user_id
    assert fetched.status == AgentStatus.ACTIVE
    assert fetched.deleted_at is None


def test_agent_user_id_is_unique(db_session):
    user = _make_user(db_session)
    db_session.add(Agent(user_id=user.user_id))
    db_session.commit()

    db_session.add(Agent(user_id=user.user_id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_agent_requires_existing_user(db_session):
    db_session.add(Agent(user_id=999))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- Project -------------------------------------------------------------------


def test_project_persists_with_topic_and_retrieves(db_session):
    agent = _make_agent(db_session)
    project = Project(agent_id=agent.agent_id, title="Thesis", topic="Urban heat islands")
    db_session.add(project)
    db_session.commit()

    fetched = db_session.get(Project, project.project_id)
    assert fetched.agent_id == agent.agent_id
    assert fetched.topic == "Urban heat islands"


def test_project_agent_id_is_unique(db_session):
    agent = _make_agent(db_session)
    db_session.add(Project(agent_id=agent.agent_id, title="First", topic="Topic A"))
    db_session.commit()

    db_session.add(Project(agent_id=agent.agent_id, title="Second", topic="Topic B"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_project_requires_existing_agent(db_session):
    db_session.add(Project(agent_id=999, title="Orphan", topic="Topic"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- Research Document -------------------------------------------------------------------


def test_document_persists_with_pending_status_by_default(db_session):
    project = _make_project(db_session)
    doc = ResearchDocument(
        project_id=project.project_id,
        title="Source A",
        format="pdf",
        content_reference="deadbeef.pdf",
    )
    db_session.add(doc)
    db_session.commit()

    fetched = db_session.get(ResearchDocument, doc.document_id)
    assert fetched.processing_status == DocumentProcessingStatus.PENDING
    assert fetched.deleted_at is None


def test_document_requires_existing_project(db_session):
    db_session.add(
        ResearchDocument(project_id=999, title="Orphan", format="pdf", content_reference="ref")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_multiple_documents_per_project_are_allowed(db_session):
    project = _make_project(db_session)
    db_session.add_all(
        [
            ResearchDocument(project_id=project.project_id, title="A", format="pdf", content_reference="ref-a"),
            ResearchDocument(project_id=project.project_id, title="B", format="docx", content_reference="ref-b"),
        ]
    )
    db_session.commit()

    stored = db_session.query(ResearchDocument).filter_by(project_id=project.project_id).all()
    assert len(stored) == 2


# --- Full chain -------------------------------------------------------------------


def test_full_agent_project_document_chain_persists_and_traverses(db_session):
    user = _make_user(db_session)
    agent = _make_agent(db_session, user=user)
    project = _make_project(db_session, agent=agent, title="Thesis", topic="Coastal erosion")
    doc = ResearchDocument(
        project_id=project.project_id, title="Baseline survey", format="pdf", content_reference="ref-baseline"
    )
    db_session.add(doc)
    db_session.commit()

    stored_agent = db_session.get(Agent, agent.agent_id)
    stored_project = db_session.get(Project, project.project_id)
    assert stored_project.agent_id == stored_agent.agent_id
    assert stored_project.agent_id == agent.agent_id

    stored_docs = db_session.query(ResearchDocument).filter_by(project_id=stored_project.project_id).all()
    assert len(stored_docs) == 1
    assert stored_docs[0].content_reference == "ref-baseline"
