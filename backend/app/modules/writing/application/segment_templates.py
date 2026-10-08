from dataclasses import dataclass, field

from app.modules.writing.application.segments import CreateWritingSegmentUseCase
from app.modules.writing.domain.entities import WritingSegment
from app.modules.writing.domain.exceptions import (
    DuplicateWritingSegmentNameError,
    SegmentTemplateNotFoundError,
    TooManyWritingSegmentsError,
)
from app.modules.writing.domain.segment_templates import (
    SEGMENT_TEMPLATES,
    SegmentTemplate,
    get_segment_template,
)


class ListSegmentTemplatesUseCase:
    """Returns every built-in Segment Template (2026-10-02) - static reference data, not
    user-scoped, so this needs no repository at all.
    """

    def execute(self) -> tuple[SegmentTemplate, ...]:
        return SEGMENT_TEMPLATES


@dataclass
class ApplySegmentTemplateResult:
    """What actually happened applying a template - not just "succeeded", since a template can
    be applied more than once (e.g. after a workspace reset, or by a user who already created
    some of the same-named segments themselves) and a caller needs to tell a fresh segment from
    one that was already there.
    """

    created: list[WritingSegment] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    limit_reached: bool = False


class ApplySegmentTemplateUseCase:
    """Creates the Writing Segments a built-in template defines, on the caller's own Agent
    (2026-10-02). Composes CreateWritingSegmentUseCase rather than duplicating its validation,
    duplicate-name, and segment-cap logic - the only thing this use case adds is tolerance:
    applying a template is expected to be re-runnable (after a reset, or on top of segments the
    user already created by hand), so a per-entry DuplicateWritingSegmentNameError is caught and
    the entry is reported as skipped instead of aborting the whole batch, the way a single
    CreateWritingSegmentUseCase.execute() call correctly would on its own.
    """

    def __init__(self, create_segment_use_case: CreateWritingSegmentUseCase) -> None:
        self._create_segment = create_segment_use_case

    def execute(self, *, user_id: int, template_id: str) -> ApplySegmentTemplateResult:
        template = get_segment_template(template_id)
        if template is None:
            raise SegmentTemplateNotFoundError(template_id=template_id)

        result = ApplySegmentTemplateResult()
        for entry in template.entries:
            try:
                segment = self._create_segment.execute(
                    user_id=user_id, name=entry.name, instructions=entry.instructions
                )
                result.created.append(segment)
            except DuplicateWritingSegmentNameError:
                result.skipped_existing.append(entry.name)
            except TooManyWritingSegmentsError:
                # Stop, don't fail the whole call - whatever was created before the cap was hit
                # is still real and should be reported, not rolled back.
                result.limit_reached = True
                break
        return result
