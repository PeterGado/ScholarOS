from __future__ import annotations

import hashlib
from pathlib import Path


class FilesystemStorage:
    """Local filesystem object store (ADR-004 MVP choice for the object-store category).

    Content-addressed: identical content is written once and referenced by its hash
    (06_Physical_Design_Strategy.md §5 - "the same source content is stored once and
    referenced, never duplicated"). No document-processing, extraction, or AI logic here -
    this is byte storage only.
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, content: bytes, *, extension: str = "") -> str:
        digest = hashlib.sha256(content).hexdigest()
        suffix = f".{extension.lstrip('.')}" if extension else ""
        reference = f"{digest}{suffix}"
        path = self._resolve(reference)
        if not path.exists():
            path.write_bytes(content)
        return reference

    def read(self, reference: str) -> bytes:
        return self._resolve(reference).read_bytes()

    def exists(self, reference: str) -> bool:
        return self._resolve(reference).exists()

    def delete(self, reference: str) -> None:
        path = self._resolve(reference)
        if path.exists():
            path.unlink()

    def _resolve(self, reference: str) -> Path:
        path = (self._root / reference).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError(f"Reference escapes storage root: {reference!r}")
        return path
