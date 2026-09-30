import io
import json
import re
import zipfile
from dataclasses import dataclass

import docx
import pypdf

from app.ai.providers.base import TextGenerationProvider
from app.modules.writing.domain.enums import ProfileCharacteristicType
from app.modules.writing.domain.exceptions import StyleExtractionError, UnusableWritingStyleSampleError

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_DOCX_MAGIC = b"PK\x03\x04"
_PDF_MAGIC = b"%PDF-"

MAX_SAMPLES_PER_EXTRACTION = 5
MAX_CHARACTERS_PER_SAMPLE = 4000

_PROMPT_TEMPLATE = '''You are analyzing writing samples to identify an author's recurring, observable writing-style characteristics. You are not evaluating quality, continuing or imitating the writing, or inferring anything about who the author is.

Analyze the writing sample(s) below and identify recurring characteristics of the writing style. Respond with ONLY a JSON object of this exact shape:
{{"characteristics": [{{"characteristic_type": "...", "signal": "...", "confidence": 0.0}}, ...]}}

- characteristic_type: exactly one of structure, vocabulary, transitions, explanation, citation
- signal: a concise, specific description of an observed, recurring PATTERN - never the sample's actual subject matter, terminology, variable names, abbreviations, section titles, numbers, or any other content specific to what the sample is about
- confidence: your confidence in this observation, a number between 0 and 1 (optional)

Example of what "signal" should look like:
- GOOD: "Introduces statistical results by first restating the hypothesis, then presenting the figure."
- BAD: "Introduces board governance variables (BSIZE, BIND, BGEND, BEXP) before presenting the correlation matrix." - this names the sample's actual subject matter and variable names instead of describing the pattern abstractly; it would apply this specific project's content to completely unrelated writing tasks.

A signal must remain true of the author's writing style no matter what topic they write about next. If a signal would stop making sense applied to a different subject, it is describing content, not style, and must not be included.

Do not:
- write new prose or continue the samples
- imitate the author's voice
- judge whether the writing is good or bad
- infer the author's identity, demographics, or any personal characteristic
- invent biographical facts
- reproduce sample text verbatim in "signal", including specific terms, names, abbreviations, or numbers from the sample
- describe anything other than observable writing-style characteristics

Writing sample(s):
"""
{samples}
"""
'''


def decode_sample_text(content: bytes, *, document_id: int) -> str:
    """Mirrors app.modules.knowledge.domain.text_extraction.PlainTextExtractor's own docx/PDF-
    aware extraction, duplicated deliberately rather than imported: Writing and Knowledge are
    architecturally separate pipelines that must never depend on each other (Project_Writing_
    Implementation_Plan.md §7; Backend_Slice2_AI_Readiness_Review.md §8) - some duplication is a
    smaller cost than a new cross-module dependency between two domains this project has
    repeatedly required stay independent.

    Originally a bare UTF-8 decode, which meant every real .docx/PDF writing sample (virtually
    all of them, in practice) failed with `UnusableWritingStyleSampleError` before ever reaching
    the AI provider - a real, blocking bug found via manual use, the same class of defect
    `PlainTextExtractor` itself was fixed for earlier. Magic bytes are sniffed before attempting
    a plain-UTF-8 decode for the same reason as there: a small, simple .docx/PDF can occasionally
    be byte-for-byte valid UTF-8, which would otherwise silently return raw file-format markup
    as if it were the sample's real text.
    """
    if content.startswith(_DOCX_MAGIC):
        try:
            return _extract_docx_text(content)
        except (zipfile.BadZipFile, KeyError, ValueError, docx.opc.exceptions.PackageNotFoundError) as exc:
            raise UnusableWritingStyleSampleError(document_id=document_id) from exc

    if content.startswith(_PDF_MAGIC):
        try:
            return _extract_pdf_text(content)
        except (pypdf.errors.PdfReadError, ValueError) as exc:
            raise UnusableWritingStyleSampleError(document_id=document_id) from exc

    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnusableWritingStyleSampleError(document_id=document_id) from exc


def _extract_docx_text(content: bytes) -> str:
    document = docx.Document(io.BytesIO(content))
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    text = "\n\n".join(paragraphs)
    if not text.strip():
        raise ValueError("The .docx file contained no extractable text")
    return text


def _extract_pdf_text(content: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(page.strip() for page in pages if page.strip())
    if not text.strip():
        raise ValueError("The PDF contained no extractable text (it may be a scanned/image-only PDF)")
    return text


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


_VERBATIM_LEAK_WORD_WINDOW = 6
"""2026-09-30, found via a real production incident: despite the prompt explicitly saying "do
not reproduce sample text verbatim in signal", the model did anyway - a 'vocabulary'
characteristic named a sample's actual domain-specific variable abbreviations (BSIZE, BIND,
BGEND, BEXP) instead of describing the pattern abstractly. That specific content then rendered
into every future generation's WRITING STYLE AND TONE section regardless of topic, derailing
unrelated replies toward the leaked sample's own subject matter - the user asked for the next
section after a thesis's background-of-the-study introduction and got a results-chapter
correlation-matrix section instead, because the "style" guidance was actually leaked content.
A prompt instruction alone isn't a reliable enough guarantee for something this consequential,
so this is a second, programmatic check below. 6 consecutive shared words is long enough that
only genuine reproduction triggers it, not coincidental short-phrase overlap.
"""


def extract_style_characteristics(samples: list[str], provider: TextGenerationProvider) -> list[ExtractedCharacteristic]:
    prompt = build_style_extraction_prompt(samples)
    raw_response = provider.generate(prompt)
    characteristics = parse_style_extraction_response(raw_response)
    _reject_verbatim_leaks(characteristics, samples)
    return characteristics


def _reject_verbatim_leaks(characteristics: list[ExtractedCharacteristic], samples: list[str]) -> None:
    sample_text = " ".join(" ".join(sample.lower().split()) for sample in samples)
    for characteristic in characteristics:
        if _shares_a_long_run_of_words(characteristic.signal, sample_text):
            raise StyleExtractionError(
                reason="a characteristic's signal appears to reproduce the sample's own content instead of "
                "describing a style pattern"
            )


def _shares_a_long_run_of_words(signal: str, sample_text: str) -> bool:
    words = signal.lower().split()
    if len(words) < _VERBATIM_LEAK_WORD_WINDOW:
        return False
    for start in range(len(words) - _VERBATIM_LEAK_WORD_WINDOW + 1):
        window = " ".join(words[start : start + _VERBATIM_LEAK_WORD_WINDOW])
        if window in sample_text:
            return True
    return False
