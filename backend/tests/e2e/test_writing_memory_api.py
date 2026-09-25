from app.auth.hashing import hash_password
from app.database.session import build_sessionmaker
from app.database.shared_models import User
from app.database.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.agent.infrastructure.repositories import SqlAlchemyAgentRepository
from app.modules.writing.domain.entities import MemoryProvenanceLink, MemoryRecord
from app.modules.writing.domain.enums import CreatedBy, MemoryProvenanceSourceType, MemoryRecordType
from app.modules.writing.infrastructure.repositories import (
    SqlAlchemyMemoryProvenanceLinkRepository,
    SqlAlchemyMemoryRecordRepository,
)


def _create_workspace(client, headers) -> dict:
    response = client.post("/agents", json={"project_title": "Thesis", "project_topic": "Coastal erosion"}, headers=headers)
    return response.json()


def _seed_memory_record(db_engine, agent_id: int, content: str = "Seeded memory.") -> int:
    session = build_sessionmaker(db_engine)()
    try:
        records = SqlAlchemyMemoryRecordRepository(session)
        record = records.add(
            MemoryRecord(agent_id=agent_id, record_type=MemoryRecordType.DECISION, content=content, created_by=CreatedBy.SYSTEM)
        )
        SqlAlchemyMemoryProvenanceLinkRepository(session).add(
            MemoryProvenanceLink(record_id=record.record_id, source_type=MemoryProvenanceSourceType.USER_INPUT)
        )
        SqlAlchemyUnitOfWork(session).commit()
        return record.record_id
    finally:
        session.close()


def test_list_memory_returns_seeded_records_with_provenance(client, auth_headers, db_engine):
    workspace = _create_workspace(client, auth_headers)
    _seed_memory_record(db_engine, workspace["agent"]["agent_id"], content="The methodology is a LIDAR survey.")

    response = client.get("/writing/memory", headers=auth_headers)

    assert response.status_code == 200
    records = response.json()["records"]
    assert len(records) == 1
    assert records[0]["content"] == "The methodology is a LIDAR survey."
    assert records[0]["status"] == "current"
    assert len(records[0]["provenance"]) == 1
    assert records[0]["provenance"][0]["source_type"] == "user_input"


def test_list_memory_for_an_agent_with_none_returns_an_empty_list(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.get("/writing/memory", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["records"] == []


def test_supersede_replaces_content_and_excludes_the_old_record_from_listing(client, auth_headers, db_engine):
    workspace = _create_workspace(client, auth_headers)
    record_id = _seed_memory_record(db_engine, workspace["agent"]["agent_id"], content="Original content.")

    response = client.post(
        f"/writing/memory/{record_id}/supersede", json={"content": "Corrected content.", "rationale": "Was wrong."}, headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["content"] == "Corrected content."
    assert response.json()["created_by"] == "user"

    listing = client.get("/writing/memory", headers=auth_headers).json()["records"]
    assert [r["content"] for r in listing] == ["Corrected content."]


def test_supersede_an_already_superseded_record_returns_409(client, auth_headers, db_engine):
    workspace = _create_workspace(client, auth_headers)
    record_id = _seed_memory_record(db_engine, workspace["agent"]["agent_id"])
    client.post(f"/writing/memory/{record_id}/supersede", json={"content": "First correction."}, headers=auth_headers)

    response = client.post(f"/writing/memory/{record_id}/supersede", json={"content": "Second correction."}, headers=auth_headers)

    assert response.status_code == 409


def test_supersede_a_nonexistent_record_returns_404(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.post("/writing/memory/999999/supersede", json={"content": "x"}, headers=auth_headers)

    assert response.status_code == 404


# --- Pagination (2026-09-23, real-traffic audit) -------------------------------------------


def test_list_memory_respects_limit_and_reports_has_more(client, auth_headers, db_engine):
    workspace = _create_workspace(client, auth_headers)
    for i in range(5):
        _seed_memory_record(db_engine, workspace["agent"]["agent_id"], content=f"Memory {i}.")

    response = client.get("/writing/memory", params={"limit": 3}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["records"]) == 3
    assert body["has_more"] is True


def test_list_memory_offset_skips_already_seen_records(client, auth_headers, db_engine):
    workspace = _create_workspace(client, auth_headers)
    for i in range(5):
        _seed_memory_record(db_engine, workspace["agent"]["agent_id"], content=f"Memory {i}.")

    first_page = client.get("/writing/memory", params={"limit": 3}, headers=auth_headers).json()
    second_page = client.get("/writing/memory", params={"limit": 3, "offset": 3}, headers=auth_headers).json()

    assert len(second_page["records"]) == 2
    assert second_page["has_more"] is False
    first_ids = {r["record_id"] for r in first_page["records"]}
    second_ids = {r["record_id"] for r in second_page["records"]}
    assert first_ids.isdisjoint(second_ids)  # no overlap, no gap across the two pages


def test_list_memory_has_more_is_false_when_every_record_fits_on_one_page(client, auth_headers, db_engine):
    workspace = _create_workspace(client, auth_headers)
    for i in range(3):
        _seed_memory_record(db_engine, workspace["agent"]["agent_id"], content=f"Memory {i}.")

    response = client.get("/writing/memory", params={"limit": 3}, headers=auth_headers)

    assert response.json()["has_more"] is False


def test_list_memory_limit_out_of_range_is_rejected(client, auth_headers):
    _create_workspace(client, auth_headers)

    response = client.get("/writing/memory", params={"limit": 0}, headers=auth_headers)

    assert response.status_code == 422


def test_another_users_memory_is_invisible_and_cannot_be_superseded(client, auth_headers, db_engine):
    workspace = _create_workspace(client, auth_headers)
    record_id = _seed_memory_record(db_engine, workspace["agent"]["agent_id"], content="Victim's memory.")

    session = build_sessionmaker(db_engine)()
    try:
        session.add(User(username="intruder-memory", password_hash=hash_password("intruder-pass")))
        session.commit()
    finally:
        session.close()
    intruder_login = client.post("/auth/login", json={"username": "intruder-memory", "password": "intruder-pass"})
    intruder_headers = {"Authorization": f"Bearer {intruder_login.json()['access_token']}"}
    client.post("/agents", json={"project_title": "Other", "project_topic": "Other"}, headers=intruder_headers)

    listing = client.get("/writing/memory", headers=intruder_headers).json()["records"]
    assert listing == []

    response = client.post(f"/writing/memory/{record_id}/supersede", json={"content": "Hijacked."}, headers=intruder_headers)
    assert response.status_code == 404
