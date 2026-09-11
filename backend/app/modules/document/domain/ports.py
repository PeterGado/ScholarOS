from typing import Protocol


class ContentStore(Protocol):
    """Outbound port for content payload storage. `app.storage.filesystem.FilesystemStorage`
    satisfies this structurally (no inheritance needed) - the document module never imports
    it directly, only this Protocol (dependency inversion, ADR-002).

    `read`/`exists` added in Stage 4 (Backend_Slice2_Implementation_Plan.md): the Knowledge
    Processing Pipeline needs to read back what upload already wrote. `FilesystemStorage`
    already implements both structurally; only the port's declared surface was incomplete.
    """

    def save(self, content: bytes, *, extension: str = "") -> str: ...

    def read(self, reference: str) -> bytes: ...

    def exists(self, reference: str) -> bool: ...
