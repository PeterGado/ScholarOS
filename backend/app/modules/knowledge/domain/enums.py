import enum


class KnowledgeElementType(str, enum.Enum):
    CONCEPT = "concept"
    THEME = "theme"
    METHOD = "method"
    CLAIM = "claim"
    RELATIONSHIP = "relationship"


class KnowledgeElementStatus(str, enum.Enum):
    CURRENT = "current"
    SUPERSEDED = "superseded"


class CreatedBy(str, enum.Enum):
    """Shared by Knowledge Element ("system (capability) / user") and Chunk Evidence Link
    ("system (pipeline) / user") - the parenthetical is descriptive context per entity, not a
    distinct value set (04_Logical_Data_Model.md §3.5, §4.1).
    """

    SYSTEM = "system"
    USER = "user"
