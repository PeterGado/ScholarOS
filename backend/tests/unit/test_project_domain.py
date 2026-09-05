import pytest

from app.modules.project.domain.entities import Project
from app.modules.project.domain.exceptions import InvalidProjectTitleError, InvalidProjectTopicError


def test_create_produces_an_active_project_with_the_given_topic():
    project = Project.create(agent_id=1, title="Thesis", topic="Coastal erosion")
    assert project.agent_id == 1
    assert project.project_id is None
    assert project.title == "Thesis"
    assert project.topic == "Coastal erosion"


@pytest.mark.parametrize("title", ["", "   ", None])
def test_construction_rejects_missing_title(title):
    with pytest.raises(InvalidProjectTitleError):
        Project(agent_id=1, title=title, topic="Some topic")


@pytest.mark.parametrize("topic", ["", "   ", None])
def test_construction_rejects_missing_topic(topic):
    with pytest.raises(InvalidProjectTopicError):
        Project(agent_id=1, title="Thesis", topic=topic)


def test_no_method_exists_to_change_topic_after_creation():
    """Topic is immutable after creation (05_Constraints_and_Integrity.md §5) - enforced by
    never exposing a mutator, not by freezing the dataclass (status transitions remain legitimate).
    """
    project = Project.create(agent_id=1, title="Thesis", topic="Original topic")
    assert not hasattr(project, "set_topic")
    assert not hasattr(project, "update_topic")
