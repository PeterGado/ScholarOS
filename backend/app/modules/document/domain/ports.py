from typing import Protocol


class ContentStore(Protocol):
    """Outbound port for content payload storage. `app.storage.filesystem.FilesystemStorage`
    satisfies this structurally (no inheritance needed) - the document module never imports
    it directly, only this Protocol (dependency inversion, ADR-002).
    """

    def save(self, content: bytes, *, extension: str = "") -> str: ...
