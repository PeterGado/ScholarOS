from dataclasses import dataclass

from app.modules.writing.domain.enums import MemoryRecordType, ProfileCharacteristicType
from app.modules.writing.domain.exceptions import InvalidContextAssemblyInputError


DEFAULT_CONTEXT_CHARACTER_LIMIT = 12000
DEFAULT_MAX_EVIDENCE = 10


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
class ContextAssemblyInput:
    topic: str
    instructions: str
    evidence: tuple[ContextEvidence, ...] = ()
    style_signals: tuple[ContextStyleSignal, ...] = ()
    memories: tuple[ContextMemory, ...] = ()
    max_characters: int = DEFAULT_CONTEXT_CHARACTER_LIMIT
    max_evidence: int = DEFAULT_MAX_EVIDENCE


@dataclass(frozen=True)
class AssembledContext:
    prompt: str
    evidence: tuple[ContextEvidence, ...]


def assemble_context(context: ContextAssemblyInput) -> AssembledContext:
    _validate_input(context)

    evidence = _unique_evidence(context.evidence)[: context.max_evidence]
    sections = [
        ("PROJECT TOPIC", context.topic),
        ("WRITING INSTRUCTIONS", context.instructions),
        ("RESEARCH EVIDENCE", _format_evidence(evidence)),
        ("WRITING STYLE SIGNALS", _format_style_signals(context.style_signals)),
        ("CURRENT PROJECT MEMORY", _format_memories(context.memories)),
    ]
    grounding_rules = (
        "GROUNDING RULES",
        "Use research evidence for factual claims. Treat style signals as writing guidance, "
        "not facts. If the evidence is insufficient, say so explicitly.",
    )

    prompt = _fit_sections_reserving_tail(sections, grounding_rules, context.max_characters)
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


def _unique_evidence(evidence: tuple[ContextEvidence, ...]) -> tuple[ContextEvidence, ...]:
    seen: set[int] = set()
    unique: list[ContextEvidence] = []
    for item in evidence:
        if item.chunk_id not in seen and item.content.strip():
            seen.add(item.chunk_id)
            unique.append(item)
    return tuple(unique)


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
    if not signals:
        return "No writing-style signals were available."

    return "\n".join(
        f"- {signal.characteristic_type.value}: {signal.signal}"
        + (f" (confidence={signal.confidence:.2f})" if signal.confidence is not None else "")
        for signal in signals
        if signal.signal.strip()
    ) or "No writing-style signals were available."


def _format_memories(memories: tuple[ContextMemory, ...]) -> str:
    if not memories:
        return "No current project memory was available."

    return "\n".join(
        f"- {memory.record_type.value}: {memory.content}"
        + (f" (rationale: {memory.rationale})" if memory.rationale and memory.rationale.strip() else "")
        for memory in memories
        if memory.content.strip()
    ) or "No current project memory was available."


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
    sections: list[tuple[str, str]], tail_section: tuple[str, str], max_characters: int
) -> str:
    """Fits `sections` (dropped/truncated under pressure, in order - same as `_fit_sections`)
    within a budget that reserves room for `tail_section` *first*, then appends it, truncated
    to whatever remains.

    `tail_section` is the fixed, always-present grounding-rules reminder. Rendering it last in
    a plain `_fit_sections` call (as an earlier version of this function did) meant any tight
    character budget silently dropped it entirely, since `_fit_sections` stops filling once
    the budget runs out and grounding rules were the final entry - exactly the case where a
    reminder not to fabricate unsupported claims matters most (long evidence sections eating
    the budget). Reserving its cost up front guarantees it always survives, at the cost of
    `sections` getting less room. Found and fixed before Stage 7.
    """
    tail_heading, tail_content = tail_section
    full_tail = f"## {tail_heading}\n{tail_content.strip()}"
    reserved = min(max_characters, len(full_tail) + 2)  # + "\n\n" separator, reserved even if sections end up empty

    leading = _fit_sections(sections, max(0, max_characters - reserved))

    remaining_for_tail = max_characters - len(leading) - (2 if leading else 0)
    tail = _truncate(full_tail, remaining_for_tail) if remaining_for_tail > 0 else ""

    if leading and tail:
        return leading + "\n\n" + tail
    return leading or tail


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
