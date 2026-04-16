from __future__ import annotations

import json
from pathlib import Path

import fitz
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap


class PdfBackend:
    def __init__(self) -> None:
        self._document: fitz.Document | None = None
        self._path: Path | None = None

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def page_count(self) -> int:
        return 0 if self._document is None else self._document.page_count

    def load(self, path: str | Path) -> int:
        pdf_path = Path(path)
        self.close()
        self._document = fitz.open(pdf_path)
        self._path = pdf_path
        return self._document.page_count

    def close(self) -> None:
        if self._document is not None:
            self._document.close()
        self._document = None
        self._path = None

    def render_page(self, index: int, max_width: int, max_height: int) -> QPixmap:
        if self._document is None:
            raise RuntimeError("No PDF document loaded")

        page = self._document.load_page(index)
        rect = page.rect
        if rect.width == 0 or rect.height == 0:
            raise RuntimeError("Invalid page size")

        scale = min(max_width / rect.width, max_height / rect.height)
        scale = max(scale, 0.1)
        matrix = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        image = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format.Format_RGB888,
        ).copy()
        return QPixmap.fromImage(image)

    def thumbnail(self, index: int, width: int = 180, height: int = 240) -> QPixmap:
        return self.render_page(index, width, height)

    def notes_path(self) -> Path | None:
        if self._path is None:
            return None
        return self._path.with_suffix(".notes.json")

    def load_notes(self) -> dict[int, str]:
        notes_path = self.notes_path()
        if notes_path is None or not notes_path.exists():
            return {}
        payload = json.loads(notes_path.read_text(encoding="utf-8"))
        notes: dict[int, str] = {}
        for key, value in payload.get("pages", {}).items():
            if value:
                notes[int(key)] = str(value)
        return notes

    def save_notes(self, notes: dict[int, str]) -> None:
        notes_path = self.notes_path()
        if notes_path is None:
            return
        payload = {
            "pdf": str(self._path),
            "pages": {str(index): text for index, text in sorted(notes.items()) if text},
        }
        notes_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def fit_pixmap(pixmap: QPixmap, width: int, height: int) -> QPixmap:
    if pixmap.isNull():
        return pixmap
    return pixmap.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
