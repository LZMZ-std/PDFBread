from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QKeyEvent, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from pdfbread.pdf_backend import fit_pixmap


def render_presentation_frame(pixmap: QPixmap, width: int = 1920, height: int = 1080) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#000000"))
    if pixmap.isNull():
        return image

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    scaled = fit_pixmap(pixmap, width, height)
    x = (width - scaled.width()) // 2
    y = (height - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)
    painter.end()
    return image


class PresentationWindow(QWidget):
    escape_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDFBread Presentation")
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#000000"))
        self.setPalette(palette)

        self._pixmap = QPixmap()
        self._label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("background:#000000;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

    def show_page(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self._refresh()

    def _refresh(self) -> None:
        if self._pixmap.isNull():
            self._label.clear()
            return
        self._label.setPixmap(fit_pixmap(self._pixmap, self.width(), self.height()))

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.escape_requested.emit()
            return
        super().keyPressEvent(event)
