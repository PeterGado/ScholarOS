import json
import re
from dataclasses import dataclass

from app.ai.providers.base import TextGenerationProvider
from app.modules.knowledge.domain.enums import KnowledgeElementType
from app.modules.knowledge.domain.exceptions import SemanticExtractionError

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_PROMPT_TEMPLATE = '''Classify the following research excerpt as exactly one of: concept, theme, method, claim, relationship.
Respond with ONLY a JSON object: {{"element_type": "...", "label": "...", "description": "..."}}
- element_type: exactly one of concept, theme, method, claim, relationship
- label: a short name (a few words) summarizing the excerpt
- description: one or two sentences describing what the excerpt conveys

Excerpt:
"""
{excerpt}
"""
'''

_BATCH_PROMPT_TEMPLATE = '''Classify each of the following {count} research excerpts as exactly one of: concept, theme, method, claim, relationship.
Respond with ONLY a JSON array of exactly {count} objects, in the same order as the excerpts. Each object: {{"element_type": "...", "label": "...", "description": "..."}}
- element_type: exactly one of concept, theme, method, claim, relationship
- label: a short name (a few words) summarizing the excerpt
- description: one or two sentences describing what the excerpt conveys

{excerpts}
'''


@dataclass(frozen=True)
class ChunkClassification:
    element_type: KnowledgeElementType
    label: str
    description: str | None


def build_classification_prompt(chunk_text: str) -> str:
    return _PROMPT_TEMPLATE.format(excerpt=chunk_text)


def build_batch_classification_prompt(chunk_texts: list[str]) -> str:
    excerpts = "\n\n".join(
        f'Excerpt {index + 1}:\n"""\n{text}\n"""' for index, text in enumerate(chunk_texts)
    )
    return _BATCH_PROMPT_TEMPLATE.format(count=len(chunk_texts), excerpts=excerpts)


def _parse_classification_object(payload: object) -> ChunkClassification:
    if not isinstance(payload, dict):
        raise SemanticExtractionError(reason="provider response was not a JSON object")

    try:
        element_type = KnowledgeElementType(payload.get("element_type"))
    except ValueError as exc:
        raise SemanticExtractionError(
            reason=f"element_type {payload.get('element_type')!r} is not one of the approved values"
        ) from exc

    label = payload.get("label")
    if not label or not str(label).strip():
        raise SemanticExtractionError(reason="label was missing or empty")

    description = payload.get("description")
    return ChunkClassification(
        element_type=element_type,
        label=str(label).strip(),
        description=str(description).strip() if description else None,
    )


def parse_classification_response(raw_response: str) -> ChunkClassification:
    """Never coerces an invalid value into a guessed one (Stage 5 plan §4) - any deviation
    from the expected shape raises SemanticExtractionError.
    """
    cleaned = _CODE_FENCE.sub("", raw_response).strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SemanticExtractionError(reason="provider response was not valid JSON") from exc

    return _parse_classification_object(payload)


def parse_batch_classification_response(raw_response: str, *, expected_count: int) -> list[ChunkClassification]:
    cleaned = _CODE_FENCE.sub("", raw_response).strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SemanticExtractionError(reason="provider response was not valid JSON") from exc

    if not isinstance(payload, list):
        raise SemanticExtractionError(reason="provider response was not a JSON array")
    if len(payload) != expected_count:
        raise SemanticExtractionError(
            reason=f"provider returned {len(payload)} classifications, expected {expected_count}"
        )

    return [_parse_classification_object(item) for item in payload]


def classify_chunk(chunk_text: str, provider: TextGenerationProvider) -> ChunkClassification:
    raw_response = provider.generate(build_classification_prompt(chunk_text))
    return parse_classification_response(raw_response)


def classify_chunks_batch(chunk_texts: list[str], provider: TextGenerationProvider) -> list[ChunkClassification]:
    """Classifies several chunks in a single provider call instead of one call per chunk. A
    real multi-page paper can produce dozens of chunks; classifying (and separately embedding)
    one at a time was enough to exhaust a free-tier daily request quota on a single document.
    The whole batch fails together on a malformed response, same as `classify_chunk` failing
    a single chunk - callers already treat a document's extraction as atomic (Stage 5 plan
    §5), so this doesn't change the failure contract, only its granularity.
    """
    if not chunk_texts:
        return []
    raw_response = provider.generate(build_batch_classification_prompt(chunk_texts))
    return parse_batch_classification_response(raw_response, expected_count=len(chunk_texts))
