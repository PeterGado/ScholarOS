import pytest

from app.modules.writing.domain.context_assembly import (
    BUILTIN_SYSTEM_GUIDANCE,
    BUILTIN_WRITING_STYLE_GUIDANCE,
    ContextAssemblyInput,
    ContextConversationMessage,
    ContextEvidence,
    ContextEvidenceSource,
    ContextMemory,
    ContextStyleSignal,
    assemble_context,
)
from app.modules.writing.domain.enums import MemoryRecordType, MessageDirection, ProfileCharacteristicType
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


def test_human_sounding_writing_guidance_is_always_present():
    """Requested explicitly by the project owner (2026-09-18): every generated reply should
    benefit from the same 'avoid AI-writing tells' guidance the `humanizer` skill applies to
    this session's own writing, not just when there happens to be room for it.
    """
    context = ContextAssemblyInput(topic="Topic", instructions="Instructions")

    assembled = assemble_context(context)

    assert "## HUMAN-SOUNDING WRITING" in assembled.prompt
    assert "not X but Y" in assembled.prompt


def test_latest_user_message_is_a_final_explicit_response_task():
    assembled = assemble_context(
        ContextAssemblyInput(
            topic="Topic",
            instructions="Answer with the methodology I selected.",
            conversation_messages=(
                ContextConversationMessage(direction=MessageDirection.USER_REQUEST, content="Use a LIDAR survey."),
            ),
        )
    )

    assert "## RESPONSE TASK — LATEST USER MESSAGE" in assembled.prompt
    assert assembled.prompt.rstrip().endswith("User: Answer with the methodology I selected.")


def test_human_sounding_writing_guidance_survives_truncation_alongside_grounding_rules():
    """Both always-present tail sections must survive a tight budget together, not just
    whichever one happens to be reserved first - regression coverage for generalizing
    _fit_sections_reserving_tail from one tail section to a list.
    """
    context = ContextAssemblyInput(
        topic="Topic",
        instructions="Instructions",
        evidence=tuple(
            ContextEvidence(chunk_id=index, content=f"Evidence paragraph {index}.", summary=None, score=1.0)
            for index in range(5)
        ),
        max_characters=1500,
    )

    assembled = assemble_context(context)

    assert len(assembled.prompt) <= 1500
    assert "## GROUNDING RULES" in assembled.prompt
    assert "## HUMAN-SOUNDING WRITING" in assembled.prompt


def test_truncation_prefers_sentence_boundaries():
    # max_characters is calibrated so PROJECT TOPIC, PROJECT DESCRIPTION, and the reserved
    # BUILT-IN SYSTEM GUIDANCE + GROUNDING RULES + HUMAN-SOUNDING WRITING tail sections all fit
    # in full, leaving just enough room for WRITING INSTRUCTIONS to be truncated - at a sentence
    # boundary - after its first sentence. (2026-09-21: recalibrated after BUILT-IN SYSTEM
    # GUIDANCE moved into the reserved tail, which reserves more space up front than before.)
    context = ContextAssemblyInput(
        topic="Topic",
        instructions="First instruction sentence. Second instruction sentence.",
        max_characters=2280,
    )

    assembled = assemble_context(context)

    assert len(assembled.prompt) <= 2280
    assert "First instruction sentence." in assembled.prompt
    assert "Second instruction sentence" not in assembled.prompt


@pytest.mark.parametrize(
    "overrides",
    (
        {"topic": ""},
        {"instructions": ""},
        {"max_characters": 0},
        {"max_evidence": 0},
        {"max_conversation_messages": 0},
        {"max_conversation_context_characters": 0},
        {"max_memories": 0},
    ),
)
def test_invalid_assembly_input_is_rejected(overrides):
    values = {"topic": "Topic", "instructions": "Instructions"}
    values.update(overrides)

    with pytest.raises(InvalidContextAssemblyInputError):
        assemble_context(ContextAssemblyInput(**values))


# --- Persistent Brain v3 audit fix: bounded memory -----------------------------------------


def test_memories_are_bounded_to_max_memories():
    """Before this fix, every current Memory Record was rendered into every prompt, unbounded -
    only the whole-prompt character budget eventually (arbitrarily) trimmed it. Callers are
    expected to supply `memories` most-recent-first; this caps deterministically to the first
    `max_memories`, mirroring `max_evidence`'s own established pattern exactly.
    """
    memories = tuple(ContextMemory(MemoryRecordType.DECISION, f"Memory {i}.") for i in range(25))
    context = ContextAssemblyInput(topic="Topic", instructions="Instructions", memories=memories, max_memories=20)

    assembled = assemble_context(context)

    assert "Memory 0." in assembled.prompt  # within the first 20, kept
    assert "Memory 19." in assembled.prompt  # the 20th, kept
    assert "Memory 20." not in assembled.prompt  # the 21st, dropped by the cap
    assert "Memory 24." not in assembled.prompt


def test_default_max_memories_is_twenty():
    memories = tuple(ContextMemory(MemoryRecordType.DECISION, f"Memory {i}.") for i in range(21))
    context = ContextAssemblyInput(topic="Topic", instructions="Instructions", memories=memories)

    assembled = assemble_context(context)

    assert "Memory 19." in assembled.prompt
    assert "Memory 20." not in assembled.prompt


# --- Persistent Brain: PROJECT DESCRIPTION ------------------------------------------------


def test_project_description_reaches_the_assembled_prompt():
    context = ContextAssemblyInput(
        topic="Topic", instructions="Instructions", description="A 12-page literature review for a graduate seminar."
    )

    assembled = assemble_context(context)

    assert "## PROJECT DESCRIPTION" in assembled.prompt
    assert "A 12-page literature review for a graduate seminar." in assembled.prompt


def test_blank_project_description_renders_a_clean_placeholder():
    context = ContextAssemblyInput(topic="Topic", instructions="Instructions", description=None)

    assembled = assemble_context(context)

    assert "## PROJECT DESCRIPTION\nNo project description was provided." in assembled.prompt


# --- Persistent Brain: RELEVANT CONVERSATION CONTEXT --------------------------------------


def test_conversation_context_reaches_the_assembled_prompt():
    context = ContextAssemblyInput(
        topic="Topic",
        instructions="Instructions",
        conversation_messages=(
            ContextConversationMessage(direction=MessageDirection.USER_REQUEST, content="Remember X."),
            ContextConversationMessage(direction=MessageDirection.SYSTEM_RESPONSE, content="Understood."),
        ),
    )

    assembled = assemble_context(context)

    assert "## RELEVANT CONVERSATION CONTEXT" in assembled.prompt
    assert "Remember X." in assembled.prompt
    assert "Understood." in assembled.prompt


def test_empty_conversation_context_renders_a_clean_placeholder():
    context = ContextAssemblyInput(topic="Topic", instructions="Instructions")

    assembled = assemble_context(context)

    assert "No relevant prior conversation was available." in assembled.prompt


def test_conversation_context_is_bounded_to_the_most_recent_messages():
    messages = tuple(
        ContextConversationMessage(direction=MessageDirection.USER_REQUEST, content=f"Message {i}.")
        for i in range(15)
    )
    context = ContextAssemblyInput(
        topic="Topic", instructions="Instructions", conversation_messages=messages, max_conversation_messages=3
    )

    assembled = assemble_context(context)

    assert "Message 14." in assembled.prompt  # most recent survives
    assert "Message 0." not in assembled.prompt  # oldest is dropped


def test_a_few_long_prior_replies_do_not_crowd_out_every_later_section():
    """Regression test for a real production defect (2026-09-21): a conversation containing a
    handful of long prior AI-generated replies (a several-thousand-character chapter, easily)
    consumed nearly the entire overall character budget, since conversation history had no
    character bound of its own - only a message-count bound. Every section listed after it in
    assemble_context's fixed order (research evidence, writing style, current project memory,
    and BUILT-IN SYSTEM GUIDANCE) was silently dropped as a result, even under this function's
    own default, generous max_characters.
    """
    long_reply = "Paragraph. " * 800  # ~8800 characters - realistic for a previously-written chapter
    messages = tuple(
        ContextConversationMessage(
            direction=MessageDirection.USER_REQUEST if i % 2 == 0 else MessageDirection.SYSTEM_RESPONSE,
            content=f"Short question {i}." if i % 2 == 0 else long_reply,
        )
        for i in range(6)
    )
    context = ContextAssemblyInput(
        topic="Topic",
        instructions="Only the background section.",
        conversation_messages=messages,
        style_signals=(ContextStyleSignal(ProfileCharacteristicType.STRUCTURE, "Short paragraphs.", 0.9),),
        memories=(ContextMemory(MemoryRecordType.DECISION, "Use LIDAR survey data."),),
    )

    assembled = assemble_context(context)

    assert "## BUILT-IN KNOWLEDGE / SYSTEM GUIDANCE" in assembled.prompt
    assert BUILTIN_SYSTEM_GUIDANCE in assembled.prompt
    assert "## WRITING STYLE AND TONE" in assembled.prompt
    assert "Short paragraphs." in assembled.prompt
    assert "## CURRENT PROJECT MEMORY" in assembled.prompt
    assert "Use LIDAR survey data." in assembled.prompt


def test_conversation_context_has_its_own_character_budget_independent_of_message_count():
    """A handful of very long messages, well under max_conversation_messages, must still be
    trimmed by their own character sub-budget - not just by count.
    """
    long_reply = "Paragraph. " * 800  # ~8800 characters
    messages = (
        ContextConversationMessage(direction=MessageDirection.USER_REQUEST, content="Oldest question."),
        ContextConversationMessage(direction=MessageDirection.SYSTEM_RESPONSE, content=long_reply),
        ContextConversationMessage(direction=MessageDirection.USER_REQUEST, content="Newest question."),
    )
    context = ContextAssemblyInput(
        topic="Topic",
        instructions="Instructions",
        conversation_messages=messages,
        max_conversation_context_characters=200,
    )

    assembled = assemble_context(context)

    assert "Newest question." in assembled.prompt  # most recent survives intact
    assert "Oldest question." not in assembled.prompt  # trimmed from the oldest end first


def test_default_max_conversation_context_characters_is_four_thousand():
    context = ContextAssemblyInput(topic="Topic", instructions="Instructions")
    assert context.max_conversation_context_characters == 4000


# --- Persistent Brain: built-in writing style (Decision 6/C) -------------------------------


def test_builtin_style_baseline_is_always_present():
    context = ContextAssemblyInput(topic="Topic", instructions="Instructions")

    assembled = assemble_context(context)

    assert BUILTIN_WRITING_STYLE_GUIDANCE in assembled.prompt


def test_user_specific_style_signals_are_layered_on_top_of_the_baseline_not_instead_of_it():
    context = ContextAssemblyInput(
        topic="Topic",
        instructions="Instructions",
        style_signals=(ContextStyleSignal(ProfileCharacteristicType.VOCABULARY, "Prefers technical terms.", 0.8),),
    )

    assembled = assemble_context(context)

    assert BUILTIN_WRITING_STYLE_GUIDANCE in assembled.prompt  # baseline still present
    assert "Prefers technical terms." in assembled.prompt  # user-specific signal layered on top


def test_builtin_system_guidance_is_always_present():
    context = ContextAssemblyInput(topic="Topic", instructions="Instructions")

    assembled = assemble_context(context)

    assert "## BUILT-IN KNOWLEDGE / SYSTEM GUIDANCE" in assembled.prompt
    assert BUILTIN_SYSTEM_GUIDANCE in assembled.prompt


# --- Persistent Brain: optional research evidence (Decision 6/B) --------------------------


def test_zero_evidence_is_valid_and_does_not_raise():
    context = ContextAssemblyInput(topic="Topic", instructions="Instructions", evidence=())

    assembled = assemble_context(context)

    assert assembled.evidence == ()
    assert "No retrieved research evidence was available." in assembled.prompt


def test_grounding_rules_warn_against_fabrication_when_no_evidence_is_present():
    context = ContextAssemblyInput(topic="Topic", instructions="Instructions", evidence=())

    assembled = assemble_context(context)

    assert "## GROUNDING RULES" in assembled.prompt
    assert "Do not fabricate citations" in assembled.prompt


def test_grounding_rules_reference_evidence_when_it_is_present():
    context = ContextAssemblyInput(
        topic="Topic",
        instructions="Instructions",
        evidence=(ContextEvidence(chunk_id=1, content="Real evidence.", summary=None, score=1.0),),
    )

    assembled = assemble_context(context)

    assert "## GROUNDING RULES" in assembled.prompt
    assert "Use the research evidence above for factual claims." in assembled.prompt
    assert "Do not fabricate citations" not in assembled.prompt


# --- Prompt-inspection: the full section structure, not just field presence ---------------


def test_full_section_structure_is_present_with_every_context_source_populated():
    """Asserts on the actual assembled prompt text and its exact section headings (Persistent
    Brain §15/§18 requirement) - not merely that each ContextAssemblyInput field exists.
    """
    context = ContextAssemblyInput(
        topic="Erosion on barrier islands",
        instructions="Write the introduction.",
        description="A field report for an environmental science course.",
        evidence=(ContextEvidence(chunk_id=1, content="Shoreline retreat data.", summary=None, score=0.9),),
        style_signals=(ContextStyleSignal(ProfileCharacteristicType.STRUCTURE, "Short paragraphs.", 0.7),),
        memories=(ContextMemory(MemoryRecordType.METHOD, "Uses LIDAR survey data."),),
        conversation_messages=(
            ContextConversationMessage(direction=MessageDirection.USER_REQUEST, content="Focus on the north end."),
        ),
    )

    assembled = assemble_context(context)
    expected_headings = [
        "## PROJECT TOPIC",
        "## PROJECT DESCRIPTION",
        "## WRITING INSTRUCTIONS",
        "## RELEVANT CONVERSATION CONTEXT",
        "## RESEARCH EVIDENCE",
        "## WRITING STYLE AND TONE",
        "## CURRENT PROJECT MEMORY",
        "## BUILT-IN KNOWLEDGE / SYSTEM GUIDANCE",
        "## GROUNDING RULES",
        "## HUMAN-SOUNDING WRITING",
    ]
    for heading in expected_headings:
        assert heading in assembled.prompt

    # Headings appear in the documented order (Persistent Brain §7).
    positions = [assembled.prompt.index(heading) for heading in expected_headings]
    assert positions == sorted(positions)
