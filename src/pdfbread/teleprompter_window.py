from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QKeyEvent, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from pdfbread.pdf_backend import fit_pixmap


def _draw_slide_card(painter: QPainter, pixmap: QPixmap, x: int, y: int, width: int, height: int) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor("#173B1D"), 2))
    painter.setBrush(QColor("#090B0C"))
    painter.drawRoundedRect(x, y, width, height, 16, 16)
    if not pixmap.isNull():
        scaled = fit_pixmap(pixmap, width - 28, height - 28)
        draw_x = x + (width - scaled.width()) // 2
        draw_y = y + (height - scaled.height()) // 2
        painter.drawPixmap(draw_x, draw_y, scaled)
    painter.restore()


def render_teleprompter_frame(
    *,
    next_pixmap: QPixmap,
    current_pixmap: QPixmap,
    page_index: int,
    page_count: int,
    remaining_text: str,
    width: int = 1920,
    height: int = 1080,
) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#010201"))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    margin = 22
    title_gap = 12
    slides_gap = 18
    timer_height = 62
    meta_height = 34
    title_height = 34

    timer_font = QFont("Segoe UI", 30, QFont.Weight.Bold)
    meta_font = QFont("Segoe UI", 13)
    title_font = QFont("Segoe UI", 18, QFont.Weight.Bold)

    timer_rect = (margin, margin, width - margin * 2, timer_height)
    meta_rect = (margin, margin + timer_height + 10, width - margin * 2, meta_height)
    slides_top = meta_rect[1] + meta_height + 14
    slides_height = max(260, height - slides_top - margin - title_height - title_gap)
    slide_width = (width - margin * 2 - slides_gap) // 2

    current_rect = (margin, slides_top, slide_width, slides_height)
    next_rect = (margin + slide_width + slides_gap, slides_top, slide_width, slides_height)

    painter.setPen(QColor("#35D35F"))
    painter.setFont(timer_font)
    painter.drawText(*timer_rect, Qt.AlignmentFlag.AlignCenter, remaining_text)

    painter.setPen(QColor("#FFFFFF"))
    painter.setFont(meta_font)
    painter.drawText(*meta_rect, Qt.AlignmentFlag.AlignCenter, f"Слайд {page_index + 1} из {page_count}")

    _draw_slide_card(painter, current_pixmap, *current_rect)
    _draw_slide_card(painter, next_pixmap, *next_rect)

    title_y = slides_top + slides_height + title_gap
    painter.setPen(QColor("#35D35F"))
    painter.setFont(title_font)
    painter.drawText(current_rect[0], title_y, current_rect[2], title_height, Qt.AlignmentFlag.AlignCenter, "Текущий")
    painter.drawText(next_rect[0], title_y, next_rect[2], title_height, Qt.AlignmentFlag.AlignCenter, "Следующий")

    painter.end()
    return image


class SlidePanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._pixmap = QPixmap()
        self.setMinimumSize(260, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(
            """
            QWidget {
                background:#090B0C;
                border:1px solid #173B1D;
                border-radius:16px;
            }
            """
        )

    def set_slide(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        if self._pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        scaled = fit_pixmap(self._pixmap, self.width() - 28, self.height() - 28)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)


class TeleprompterWindow(QWidget):
    escape_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDFBread Teleprompter")
        self.setAutoFillBackground(True)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#010201"))
        self.setPalette(palette)

        self._timer_label = QLabel("15:00", alignment=Qt.AlignmentFlag.AlignCenter)
        self._timer_label.setStyleSheet("color:#35D35F;")
        self._timer_label.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))

        self._meta_label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self._meta_label.setStyleSheet("color:#FFFFFF;")
        self._meta_label.setFont(QFont("Segoe UI", 13))

        slides_row = QHBoxLayout()
        slides_row.setSpacing(18)
        self._current_slide = SlidePanel()
        self._next_slide = SlidePanel()
        slides_row.addWidget(self._current_slide, 1)
        slides_row.addWidget(self._next_slide, 1)

        titles_row = QHBoxLayout()
        self._current_title = QLabel("Текущий", alignment=Qt.AlignmentFlag.AlignCenter)
        self._next_title = QLabel("Следующий", alignment=Qt.AlignmentFlag.AlignCenter)
        self._current_title.setStyleSheet("color:#35D35F; font-size:18px; font-weight:700;")
        self._next_title.setStyleSheet("color:#35D35F; font-size:18px; font-weight:700;")
        titles_row.addWidget(self._current_title, 1)
        titles_row.addWidget(self._next_title, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(16)
        layout.addWidget(self._timer_label)
        layout.addWidget(self._meta_label)
        layout.addLayout(slides_row, 1)
        layout.addLayout(titles_row)

    def update_content(
        self,
        next_pixmap: QPixmap,
        current_pixmap: QPixmap,
        page_index: int,
        page_count: int,
        remaining_text: str,
    ) -> None:
        self._next_slide.set_slide(next_pixmap)
        self._current_slide.set_slide(current_pixmap)
        self._meta_label.setText(f"Слайд {page_index + 1} из {page_count}")
        self._timer_label.setText(remaining_text)

    def update_timer(self, remaining_text: str) -> None:
        self._timer_label.setText(remaining_text)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.escape_requested.emit()
            return
        super().keyPressEvent(event)
