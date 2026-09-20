from fastapi import UploadFile

from app.core.exceptions import UploadTooLargeError


async def read_upload_within_limit(file: UploadFile, *, max_bytes: int) -> bytes:
    """Reads an uploaded file's content, bounded to at most `max_bytes` + 1 in memory - never
    the unbounded `await file.read()` every upload route used before this, which held the
    entire file in memory regardless of size before any check ran at all. Reading one byte past
    the limit is enough to detect an oversized upload without ever materializing more than
    `max_bytes` + 1 bytes, real protection against a very large upload (real production finding,
    2026-09-19 security pass) rather than a courtesy check performed only after the damage is
    already done.
    """
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise UploadTooLargeError(max_bytes=max_bytes)
    return content
