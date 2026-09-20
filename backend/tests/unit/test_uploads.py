import asyncio
import io

import pytest
from fastapi import UploadFile

from app.core.exceptions import UploadTooLargeError
from app.core.uploads import read_upload_within_limit


def _upload_file(content: bytes) -> UploadFile:
    return UploadFile(filename="sample.txt", file=io.BytesIO(content))


def test_reads_content_within_the_limit():
    file = _upload_file(b"within limit")

    content = asyncio.run(read_upload_within_limit(file, max_bytes=1024))

    assert content == b"within limit"


def test_reads_content_exactly_at_the_limit():
    file = _upload_file(b"12345")

    content = asyncio.run(read_upload_within_limit(file, max_bytes=5))

    assert content == b"12345"


def test_raises_when_content_exceeds_the_limit():
    file = _upload_file(b"123456")

    with pytest.raises(UploadTooLargeError) as exc_info:
        asyncio.run(read_upload_within_limit(file, max_bytes=5))

    assert exc_info.value.max_bytes == 5


def test_never_reads_more_than_one_byte_past_the_limit():
    """The whole point of bounding the `read()` call itself (rather than reading everything and
    checking length afterward) is that a large upload never materializes past `max_bytes` + 1
    bytes in memory, no matter how large the real file is.
    """
    file = _upload_file(b"x" * 10_000_000)

    async def _read_then_inspect_remainder() -> bytes:
        with pytest.raises(UploadTooLargeError):
            await read_upload_within_limit(file, max_bytes=10)
        return await file.read()

    remaining = asyncio.run(_read_then_inspect_remainder())
    assert len(remaining) == 10_000_000 - 11
