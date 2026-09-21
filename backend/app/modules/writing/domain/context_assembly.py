from dataclasses import dataclass

from app.modules.writing.domain.enums import MemoryRecordType, MessageDirection, ProfileCharacteristicType
from app.modules.writing.domain.exceptions import InvalidContextAssemblyInputError


DEFAULT_CONTEXT_CHARACTER_LIMIT = 12000
DEFAULT_MAX_EVIDENCE = 10
DEFAULT_MAX_CONVERSATION_MESSAGES = 10
"""Bounded conversation context (Persistent Brain Decision 3/§8): only the most recent
`max_conversation_messages` messages are ever rendered into a prompt, regardless of how long
the underlying Conversation has grown. This is a deliberately simple bounding strategy (most
recent N) rather than summarization/compaction - sufficient, deterministic, and testable for
this milestone; true compaction is noted as future work, not implemented here.
"""

DEFAULT_MAX_CONVERSATION_CONTEXT_CHARACTERS = 4000
"""Conversation history's own character sub-budget, independent of `max_conversation_messages`
(2026-09-21 real-usage fix). Before this, conversation history had no character bound of its
own - only a message-COUNT bound - so a handful of long prior AI replies (a previously-written,
several-thousand-character chapter, found live in real production usage) could consume nearly
the entire prompt's overall character budget, crowding out every section listed after it in
`assemble_context`'s fixed order, including BUILT-IN SYSTEM GUIDANCE (now a protected tail
section for the same reason - see `assemble_context`'s own docstring). Trimmed from the OLDEST
end (see `_format_conversation`), keeping the most recent turns intact - recency matters most
for conversational continuity, and dropping whole messages reads better than a mid-message cut.
"""

DEFAULT_MAX_MEMORIES = 20
"""Persistent Brain v3 audit fix: `MemoryRecord` accumulates without limit (a Memory Record is
never deleted, only superseded), and prior to this fix every current record was rendered into
every prompt - an unbounded, unranked pile that would eventually only be trimmed by the
whole-prompt character budget, arbitrarily. Callers are expected to supply `memories` ordered
most-recent-first (see `SqlAlchemyMemoryRecordRepository.list_current_by_agent_id`'s ordering);
this caps it to the most recently established/confirmed `max_memories`, mirroring `max_evidence`
and `max_conversation_messages`'s own established bounding pattern exactly.
"""

BUILTIN_WRITING_STYLE_GUIDANCE = (
    "Write in clear, coherent, well-structured prose appropriate to the project's context. "
    "Prefer precise, plain language over needless complexity. Organize ideas logically with "
    "smooth transitions between them. Avoid repetition and filler. Match tone to the stated "
    "project type (for example academic, professional, or personal) when that is known from "
    "the project topic or description; default to a neutral, professional register otherwise."
)
"""The built-in baseline writing style (Persistent Brain Decision 6/§6, Decision 5-B): always
present so generation never depends on a user having uploaded writing samples. When a user
Writing Profile exists, its characteristics are rendered alongside this baseline, refining it -
never replacing it (see `_format_style_signals`).
"""

HUMANIZER_GUIDANCE = (
    "Write like a person, not an AI assistant. Avoid these common AI-writing patterns: "
    "'not X but Y' contrasts (e.g. 'not just a summary, but a synthesis'); one-line dramatic "
    "closers that just restate the point ('That's the real difference.'); forced groups of "
    "three; overused words such as delve, crucial, testament, underscore, robust, meticulous, "
    "pivotal, landscape, tapestry, fostering; inflated significance ('marks a pivotal moment', "
    "'stands as a testament to'); sales-style language ('nestled in', 'breathtaking', "
    "'vibrant'); em dashes used as a catch-all connector; bold-labeled list items where the "
    "label adds no information; staged openers ('Let's dive in', 'Here's what you need to "
    "know'); and chatbot leftovers ('I hope this helps!', 'Let me know if you'd like more.'). "
    "State points directly and let sentence length vary naturally, the way a person writing "
    "for one specific reader would - not the safest phrasing that fits every reader."
)
"""Applies the same 'Signs of AI Writing' patterns (Wikipedia, WikiProject AI Cleanup) the
`humanizer` Claude Code skill teaches - requested explicitly by the project owner (2026-09-18)
so ScholarOS's own generated output benefits from the same de-AI-ification the skill applies to
this session's own writing, condensed for a generation prompt rather than an editing pass (the
skill's own "mark tells, then rewrite" workflow doesn't apply to text that doesn't exist yet).
Rendered as its own section (not folded into BUILTIN_SYSTEM_GUIDANCE) so it stays independently
testable and readable, and protected from truncation the same way GROUNDING RULES already is -
see _fit_sections_reserving_tail, generalized to reserve both.
"""

BUILTIN_SYSTEM_GUIDANCE = (
    "You are ScholarOS's writing assistant, operating inside one user's private Agent "
    "Workspace. Use the project topic, project description, conversation context, research "
    "evidence, writing style guidance, and current project memory above as background context "
    "for this request. When research evidence is not available, rely on your own general "
    "knowledge and say so rather than inventing sources or citations.\n\n"
    "WRITING INSTRUCTIONS above states exactly what to produce right now - follow its stated "
    "scope precisely. If it asks for one specific section or a narrower slice of something "
    "written earlier, produce only that: do not restate, repeat, or continue material already "
    "covered in RELEVANT CONVERSATION CONTEXT just because it exists there, and do not expand "
    "scope to a fuller draft than what was actually asked for."
)
"""Built-in system-level behavior (Persistent Brain §6 point 1: "built-in system behavior" as
one of the context sources generation can fall back on even when every optional source is
absent). Fixed and always present - distinct from writing style/tone guidance above.

The second paragraph (2026-09-21) closes a real gap found in production: a long conversation
containing prior full-chapter replies pushed the model toward continuing/repeating that
established pattern even when the current instruction asked for one specific, narrower section -
the instruction itself was followed (the right section), but scope crept to include material
already produced earlier. Explicit, not implicit, because the model has no other signal in this
prompt telling it that conversation history is background, not a template to keep extending.
"""


@dataclass(frozen=True)
class ContextEvidenceSource:
    document_id: int
    document_title: str


@dataclass(frozen=True)
class ContextEvidence:
    chunk_id: int
    content: str
    summary: str | None
    score: float
    sources: tuple[ContextEvidenceSource, ...] = ()


@dataclass(frozen=True)
class ContextStyleSignal:
    characteristic_type: ProfileCharacteristicType
    signal: str
    confidence: float | None = None


@dataclass(frozen=True)
class ContextMemory:
    record_type: MemoryRecordType
    content: str
    rationale: str | None = None


@dataclass(frozen=True)
class ContextConversationMessage:
    """One bounded, already-persisted Message rendered into the RELEVANT CONVERSATION CONTEXT
    section (Persistent Brain Decision 3). Deliberately a projection of `Message` - direction +
    content only - not the full entity, matching the read-only, prompt-shaped role every other
    Context* dataclass here plays.

    `is_summary` (Persistent Brain v2, scalable conversation memory) marks an entry as a
    rolling AI-generated summary of older messages rather than a raw exchange - see
    `app.modules.writing.domain.conversation_context.resolve_bounded_conversation_messages`,
    which is what actually produces these. Rendered with a distinct label so the model (and
    anyone inspecting the prompt) can tell compacted history apart from a verbatim message.
    """

    direction: MessageDirection
    content: str
    is_summary: bool = False


@dataclass(frozen=True)
class ContextAssemblyInput:
    topic: str
    instructions: str
    description: str | None = None
    evidence: tuple[ContextEvidence, ...] = ()
    style_signals: tuple[ContextStyleSignal, ...] = ()
    memories: tuple[ContextMemory, ...] = ()
    conversation_messages: tuple[ContextConversationMessage, ...] = ()
    max_characters: int = DEFAULT_CONTEXT_CHARACTER_LIMIT
    max_evidence: int = DEFAULT_MAX_EVIDENCE
    max_conversation_messages: int = DEFAULT_MAX_CONVERSATION_MESSAGES
    max_conversation_context_characters: int = DEFAULT_MAX_CONVERSATION_CONTEXT_CHARACTERS
    max_memories: int = DEFAULT_MAX_MEMORIES


@dataclass(frozen=True)
class AssembledContext:
    prompt: str
    evidence: tuple[ContextEvidence, ...]


def assemble_context(context: ContextAssemblyInput) -> AssembledContext:
    """Builds the final LLM prompt from every available context source, section by section.

    Research evidence and writing-style signals are optional (Persistent Brain Decision 6):
    an empty `evidence` tuple is a valid, first-class input, not an error - the caller decides
    whether to require evidence, this pure function never does. Absent optional sources render
    a clean placeholder rather than being omitted, matching every existing section's precedent.

    BUILT-IN KNOWLEDGE / SYSTEM GUIDANCE (2026-09-21) is a protected tail section, not a normal
    one: a real production conversation showed conversation history alone (a few long prior AI
    replies) consuming nearly the whole character budget, silently dropping every section after
    it in the old fixed order - including this one, the section that tells the model to treat
    WRITING INSTRUCTIONS as authoritative rather than just continuing the pattern visible in
    conversation history. It must never be the section pressure drops.
    """
    _validate_input(context)

    evidence = _unique_evidence(context.evidence)[: context.max_evidence]
    recent_messages = context.conversation_messages[-context.max_conversation_messages :]
    bounded_memories = context.memories[: context.max_memories]
    sections = [
        ("PROJECT TOPIC", context.topic),
        ("PROJECT DESCRIPTION", _format_description(context.description)),
        ("WRITING INSTRUCTIONS", context.instructions),
        ("RELEVANT CONVERSATION CONTEXT", _format_conversation(recent_messages, context.max_conversation_context_characters)),
        ("RESEARCH EVIDENCE", _format_evidence(evidence)),
        ("WRITING STYLE AND TONE", _format_style_signals(context.style_signals)),
        ("CURRENT PROJECT MEMORY", _format_memories(bounded_memories)),
    ]
    tail_sections = [
        ("BUILT-IN KNOWLEDGE / SYSTEM GUIDANCE", BUILTIN_SYSTEM_GUIDANCE),
        _grounding_rules(has_evidence=bool(evidence)),
        ("HUMAN-SOUNDING WRITING", HUMANIZER_GUIDANCE),
    ]

    prompt = _fit_sections_reserving_tail(sections, tail_sections, context.max_characters)
    return AssembledContext(prompt=prompt, evidence=evidence)


def _validate_input(context: ContextAssemblyInput) -> None:
    if not context.topic.strip():
        raise InvalidContextAssemblyInputError("topic must not be blank")
    if not context.instructions.strip():
        raise InvalidContextAssemblyInputError(
            "instructions must not be blank")
    if context.max_characters < 1:
        raise InvalidContextAssemblyInputError(
            "max_characters must be positive")
    if context.max_evidence < 1:
        raise InvalidContextAssemblyInputError("max_evidence must be positive")
    if context.max_conversation_messages < 1:
        raise InvalidContextAssemblyInputError("max_conversation_messages must be positive")
    if context.max_conversation_context_characters < 1:
        raise InvalidContextAssemblyInputError("max_conversation_context_characters must be positive")
    if context.max_memories < 1:
        raise InvalidContextAssemblyInputError("max_memories must be positive")


def _unique_evidence(evidence: tuple[ContextEvidence, ...]) -> tuple[ContextEvidence, ...]:
    seen: set[int] = set()
    unique: list[ContextEvidence] = []
    for item in evidence:
        if item.chunk_id not in seen and item.content.strip():
            seen.add(item.chunk_id)
            unique.append(item)
    return tuple(unique)


def _format_description(description: str | None) -> str:
    if description is None or not description.strip():
        return "No project description was provided."
    return description.strip()


def _format_conversation(
    messages: tuple[ContextConversationMessage, ...],
    max_characters: int = DEFAULT_MAX_CONVERSATION_CONTEXT_CHARACTERS,
) -> str:
    if not messages:
        return "No relevant prior conversation was available."

    labels = {
        MessageDirection.USER_REQUEST: "User",
        MessageDirection.SYSTEM_RESPONSE: "Assistant",
    }

    def render(message: ContextConversationMessage) -> str | None:
        if not message.content.strip():
            return None
        if message.is_summary:
            return f"[Earlier conversation summary]: {message.content.strip()}"
        return f"{labels.get(message.direction, message.direction.value)}: {message.content.strip()}"

    # Trimmed from the OLDEST end (iterating newest-first, then reversing) so the most recent
    # turns - the ones most relevant to the current request - always survive intact, rather
    # than a handful of long prior replies silently consuming the whole sub-budget and pushing
    # out the turns that actually matter for understanding the current request.
    kept: list[str] = []
    remaining = max_characters
    for message in reversed(messages):
        line = render(message)
        if line is None:
            continue
        cost = len(line) + (1 if kept else 0)  # + the "\n" separator joining it to what follows
        if cost > remaining:
            break
        kept.append(line)
        remaining -= cost

    kept.reverse()
    return "\n".join(kept) or "No relevant prior conversation was available."


def _format_evidence(evidence: tuple[ContextEvidence, ...]) -> str:
    if not evidence:
        return "No retrieved research evidence was available."

    entries = []
    for index, item in enumerate(evidence, start=1):
        sources = ", ".join(
            source.document_title for source in item.sources) or "unknown source"
        entries.append(
            f"[{index}] chunk_id={item.chunk_id}; score={item.score:.6f}; sources={sources}\n{item.content}")
    return "\n\n".join(entries)


def _format_style_signals(signals: tuple[ContextStyleSignal, ...]) -> str:
    lines = [BUILTIN_WRITING_STYLE_GUIDANCE]

    specific = [
        f"- {signal.characteristic_type.value}: {signal.signal}"
        + (f" (confidence={signal.confidence:.2f})" if signal.confidence is not None else "")
        for signal in signals
        if signal.signal.strip()
    ]
    if specific:
        lines.append(
            "The following user-specific style signals refine the baseline above and take "
            "precedence over it wherever they conflict:"
        )
        lines.extend(specific)

    return "\n".join(lines)


def _format_memories(memories: tuple[ContextMemory, ...]) -> str:
    if not memories:
        return "No current project memory was available."

    return "\n".join(
        f"- {memory.record_type.value}: {memory.content}"
        + (f" (rationale: {memory.rationale})" if memory.rationale and memory.rationale.strip() else "")
        for memory in memories
        if memory.content.strip()
    ) or "No current project memory was available."


def _grounding_rules(*, has_evidence: bool) -> tuple[str, str]:
    if has_evidence:
        text = (
            "Use the research evidence above for factual claims. Treat style signals as "
            "writing guidance, not facts. If the evidence is insufficient for a claim, say so "
            "explicitly rather than inventing support."
        )
    else:
        text = (
            "No research evidence was supplied for this request. Do not fabricate citations, "
            "sources, or specific findings, and do not claim support from research the user "
            "has not actually provided. Rely on general knowledge, clearly presented as such, "
            "together with the project context above."
        )
    return ("GROUNDING RULES", text)


def _fit_sections(sections: list[tuple[str, str]], max_characters: int) -> str:
    rendered: list[str] = []
    remaining = max_characters

    for heading, content in sections:
        section = f"## {heading}\n{content.strip()}"
        separator = "\n\n" if rendered else ""
        available = remaining - len(separator)
        if available <= 0:
            break
        fitted = _truncate(section, available)
        if fitted:
            rendered.append(separator + fitted)
            remaining -= len(separator) + len(fitted)

    return "".join(rendered)


def _fit_sections_reserving_tail(
    sections: list[tuple[str, str]], tail_sections: list[tuple[str, str]], max_characters: int
) -> str:
    """Fits `sections` (dropped/truncated under pressure, in order - same as `_fit_sections`)
    within a budget that reserves room for every entry in `tail_sections` *first*, then appends
    them in order, each truncated to whatever remains.

    `tail_sections` are fixed, always-present reminders (currently GROUNDING RULES and
    HUMAN-SOUNDING WRITING). Rendering them last in a plain `_fit_sections` call (as an earlier
    version of this function did, with a single tail_section) meant any tight character budget
    silently dropped them entirely, since `_fit_sections` stops filling once the budget runs
    out - exactly the case where these reminders matter most (long evidence sections eating the
    budget). Reserving their combined cost up front guarantees they always survive, at the cost
    of `sections` getting less room. The single-tail version was found and fixed before Stage
    7; generalized to a list (2026-09-18) when a second always-present section was added.
    """
    full_tails = [f"## {heading}\n{content.strip()}" for heading, content in tail_sections]
    reserved = min(max_characters, sum(len(t) + 2 for t in full_tails))  # each + "\n\n" separator

    leading = _fit_sections(sections, max(0, max_characters - reserved))

    remaining = max_characters - len(leading) - (2 if leading else 0)
    rendered_tails: list[str] = []
    for full_tail in full_tails:
        if remaining <= 0:
            break
        tail = _truncate(full_tail, remaining)
        if tail:
            rendered_tails.append(tail)
            remaining -= len(tail) + 2

    parts = [leading] + rendered_tails if leading else rendered_tails
    return "\n\n".join(part for part in parts if part)


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]

    candidate = value[: limit - 3].rstrip()
    boundary = max(candidate.rfind(
        "."), candidate.rfind("!"), candidate.rfind("?"))
    if boundary >= 0:
        candidate = candidate[: boundary + 1]
    else:
        candidate = candidate.rsplit(" ", 1)[0].rstrip()
    return candidate + "..."
