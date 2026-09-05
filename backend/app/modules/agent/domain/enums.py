from enum import Enum


class AgentStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
