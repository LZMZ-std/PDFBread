from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PdfDocumentState:
    pdf_path: Path | None = None
    page_count: int = 0
    current_page: int = 0
    notes: dict[int, str] = field(default_factory=dict)

    @property
    def has_document(self) -> bool:
        return self.pdf_path is not None and self.page_count > 0

    def note_for_page(self, index: int) -> str:
        return self.notes.get(index, "")

    def set_note_for_page(self, index: int, text: str) -> None:
        normalized = text.rstrip()
        if normalized:
            self.notes[index] = normalized
        elif index in self.notes:
            del self.notes[index]
