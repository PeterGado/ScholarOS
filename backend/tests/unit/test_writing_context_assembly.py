import pytest

from app.modules.writing.domain.context_assembly import (
    ContextAssemblyInput,
    ContextEvidence,
    ContextEvidenceSource,
    ContextMemory,
    ContextStyleSignal,
    assemble_context,
)
from app.modules.writing.domain.enums import MemoryRecordType, ProfileCharacteristicType
from app.modules.writing.domain.exceptions import InvalidContextAssemblyInputError


def test_assembly_is_deterministic_and_preserves_evidence_order():
    context = ContextAssemblyInput(
        topic="The history of public libraries",
        instructions="Write a concise introduction.",
        evidence=(
            ContextEvidence(
                chunk_id=2,
                content="Second evidence.",
                summary=None,
                score=0.8,
                sources=(ContextEvidenceSource(
                    document_id=9, document_title="Sources"),),
            ),
            ContextEvidence(
                chunk_id=2, content="Duplicate evidence.", summary=None, score=0.7),
            ContextEvidence(chunk_id=1, content="First evidence.",
                            summary="A summary", score=0.9),
        ),
        style_signals=(
            ContextStyleSignal(
                ProfileCharacteristicType.STRUCTURE, "Uses clear sections.", 0.9),
        ),
        memories=(ContextMemory(MemoryRecordType.OBJECTIVE,
                  "Focus on public access."),),
    )

    first = assemble_context(context)
    second = assemble_context(context)

    assert first == second
    assert [item.chunk_id for item in first.evidence] == [2, 1]
    assert "Second evidence." in first.prompt
    assert "Duplicate evidence." not in first.prompt
    assert "Uses clear sections." in first.prompt
    assert "Focus on public access." in first.prompt


def test_assembly_applies_evidence_limit_and_prompt_character_limit():
    context = ContextAssemblyInput(
        topic="Topic",
        instructions="Instructions",
        evidence=tuple(
            ContextEvidence(
                chunk_id=index, content=f"Evidence {index}.", summary=None, score=1.0)
            for index in range(3)
        ),
        max_evidence=2,
        max_characters=180,
    )

    assembled = assemble_context(context)

    assert len(assembled.prompt) <= 180
    assert [item.chunk_id for item in assembled.evidence] == [0, 1]
    assert "Evidence 2." not in assembled.prompt


def test_grounding_rules_survive_truncation_under_realistic_evidence_pressure():
    """Regression test for the fixed defect: GROUNDING RULES was rendered last, so any
    context whose earlier sections (topic/instructions/evidence/style/memory) filled the
    budget silently dropped it entirely - exactly when a reminder not to fabricate unsupported
    claims matters most. It must now survive even under a tight budget with real evidence.
    """
    context = ContextAssemblyInput(
        topic="Topic",
        instructions="Instructions",
        evidence=tuple(
            ContextEvidence(chunk_id=index, content=f"Evidence paragraph {index}.", summary=None, score=1.0)
            for index in range(5)
        ),
        max_characters=180,
    )

    assembled = assemble_context(context)

    assert len(assembled.prompt) <= 180
    assert "GROUNDING RULES" in assembled.prompt


def test_truncation_prefers_sentence_boundaries():
    context = ContextAssemblyInput(
        topic="Topic",
        instructions="First instruction sentence. Second instruction sentence.",
        max_characters=260,
    )

    assembled = assemble_context(context)

    assert len(assembled.prompt) <= 260
    assert "First instruction sentence." in assembled.prompt
    assert "Second instruction sentence" not in assembled.prompt


@pytest.mark.parametrize(
    "overrides",
    ({"topic": ""}, {"instructions": ""}, {
     "max_characters": 0}, {"max_evidence": 0}),
)
def test_invalid_assembly_input_is_rejected(overrides):
    values = {"topic": "Topic", "instructions": "Instructions"}
    values.update(overrides)

    with pytest.raises(InvalidContextAssemblyInputError):
        assemble_context(ContextAssemblyInput(**values))
