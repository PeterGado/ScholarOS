from app.modules.agent.domain.entities import Agent
from app.modules.agent.domain.enums import AgentStatus


def test_create_produces_an_active_agent_with_no_id_yet():
    agent = Agent.create(user_id=7)
    assert agent.user_id == 7
    assert agent.agent_id is None
    assert agent.status == AgentStatus.ACTIVE
    assert agent.is_active


def test_is_active_is_false_once_archived():
    agent = Agent.create(user_id=7)
    agent.status = AgentStatus.ARCHIVED
    assert not agent.is_active


def test_is_active_is_false_once_soft_deleted():
    from datetime import datetime, timezone

    agent = Agent.create(user_id=7)
    agent.deleted_at = datetime.now(timezone.utc)
    assert not agent.is_active
