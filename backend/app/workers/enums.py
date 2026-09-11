import enum


class WorkItemKind(str, enum.Enum):
    PIPELINE_STAGE = "pipeline_stage"
    DOMAIN_EVENT = "domain_event"


class WorkItemState(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
