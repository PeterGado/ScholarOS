import json
import re
from dataclasses import dataclass

from app.ai.providers.base import TextGenerationProvider
from app.modules.writing.domain.enums import ProfileCharacteristicType
from app.modules.writing.domain.exceptions import StyleExtractionError, UnusableWritingStyleSampleError

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

MAX_SAMPLES_PER_EXTRACTION = 5
MAX_CHARACTERS_PER_SAMPLE = 4000

_PROMPT_TEMPLATE = '''You are analyzing writing samples to identify an author's recurring, observable writing-style characteristics. You are not evaluating quality, continuing or imitating the writing, or inferring anything about who the author is.

Analyze the writing sample(s) below and identify recurring characteristics of the writing style. Respond with ONLY a JSON object of this exact shape:
{{"characteristics": [{{"characteristic_type": "...", "signal": "...", "confidence": 0.0}}, ...]}}

- characteristic_type: exactly one of structure, vocabulary, transitions, explanation, citation
- signal: a concise, specific description of an observed, recurring characteristic - describe the pattern, do not quote or reproduce the sample text verbatim
- confidence: your confidence in this observation, a number between 0 and 1 (optional)

Do not:
- write new prose or continue the samples
- imitate the author's voice
- judge whether the writing is good or bad
- infer the author's identity, demographics, or any personal characteristic
- invent biographical facts
- reproduce sample text verbatim in "signal"
- describe anything other than observable writing-style characteristics

Writing sample(s):
"""
{samples}
"""
'''


def decode_sample_text(content: bytes, *, document_id: int) -> str:
    """Mirrors app.modules.knowledge.domain.text_extraction.PlainTextExtractor's own strict
    UTF-8-decode-or-unsupported approach, duplicated deliberately rather than imported: Writing
    and Knowledge are architecturally separate pipelines that must never depend on each other
    (Project_Writing_Implementation_Plan.md §7; Backend_Slice2_AI_Readiness_Review.md §8) -
    five lines of duplication is a smaller cost than a new cross-module dependency between two
    domains this project has repeatedly required stay independent.
    """
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnusableWritingStyleSampleError(document_id=document_id) from exc


def build_style_extraction_prompt(samples: list[str]) -> str:
    """Deterministic input preparation (Stage 4 prompt §16): bounded sample count, bounded
    characters per sample, and the caller's own supplied ordering is preserved (no reordering
    performed here) - no summarization pipeline, no dynamic limit.
    """
    bounded = [sample[:MAX_CHARACTERS_PER_SAMPLE] for sample in samples[:MAX_SAMPLES_PER_EXTRACTION]]
    joined = "\n\n---\n\n".join(bounded)
    return _PROMPT_TEMPLATE.format(samples=joined)


@dataclass(frozen=True)
class ExtractedCharacteristic:
    """Semantic data only - the provider returns this and nothing else. It never carries a
    document_id, characteristic_id, or any other persistence identifier (Stage 4 prompt §7/§10)
    - the application layer alone decides what gets persisted and how it is linked to sources.
    """

    characteristic_type: ProfileCharacteristicType
    signal: str
    confidence: float | None


def parse_style_extraction_response(raw_response: str) -> list[ExtractedCharacteristic]:
    """Never coerces an invalid value into a guessed one (mirrors
    app.modules.knowledge.domain.semantic_classification.parse_classification_response's own
    discipline) - any single malformed characteristic entry fails the entire response, before
    any persistence begins (Stage 4 prompt §14/§29 atomicity requirement).
    """
    cleaned = _CODE_FENCE.sub("", raw_response).strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise StyleExtractionError(reason="provider response was not valid JSON") from exc

    if not isinstance(payload, dict):
        raise StyleExtractionError(reason="provider response was not a JSON object")

    raw_characteristics = payload.get("characteristics")
    if not isinstance(raw_characteristics, list) or not raw_characteristics:
        raise StyleExtractionError(reason="response did not contain a non-empty 'characteristics' list")

    characteristics: list[ExtractedCharacteristic] = []
    for item in raw_characteristics:
        if not isinstance(item, dict):
            raise StyleExtractionError(reason="a characteristic entry was not a JSON object")

        try:
            characteristic_type = ProfileCharacteristicType(item.get("characteristic_type"))
        except ValueError as exc:
            raise StyleExtractionError(
                reason=f"characteristic_type {item.get('characteristic_type')!r} is not one of the approved values"
            ) from exc

        signal = item.get("signal")
        if not signal or not str(signal).strip():
            raise StyleExtractionError(reason="signal was missing or empty")

        confidence = item.get("confidence")
        if confidence is not None:
            is_number = isinstance(confidence, (int, float)) and not isinstance(confidence, bool)
            if not is_number or not (0.0 <= float(confidence) <= 1.0):
                raise StyleExtractionError(reason=f"confidence {confidence!r} is not a number between 0 and 1")
            confidence = float(confidence)

        characteristics.append(
            ExtractedCharacteristic(characteristic_type=characteristic_type, signal=str(signal).strip(), confidence=confidence)
        )

    return characteristics


def extract_style_characteristics(samples: list[str], provider: TextGenerationProvider) -> list[ExtractedCharacteristic]:
    prompt = build_style_extraction_prompt(samples)
    raw_response = provider.generate(prompt)
    return parse_style_extraction_response(raw_response)
