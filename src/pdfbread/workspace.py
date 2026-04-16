from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QElapsedTimer, QPropertyAnimation, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGraphicsOpacityEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pdfbread.pdf_backend import PdfBackend, fit_pixmap
from pdfbread.state import PdfDocumentState


class ClickablePreviewLabel(QLabel):
    clicked = Signal()

    def __init__(self, title: str) -> None:
        super().__init__()
        self._title = title
        self._pixmap: QPixmap | None = None
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)
        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setDuration(180)
        self._fade.setStartValue(0.55)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(520, 320)
        self.setStyleSheet(
            """
            QLabel {
                background: #07090B;
                color: #B7C0C8;
                border: 1px solid #16361E;
                border-radius: 16px;
                padding: 14px;
            }
            """
        )
        self.clear_preview()

    def set_preview(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self._refresh()
        self._fade.stop()
        self._fade.start()

    def clear_preview(self) -> None:
        self._pixmap = None
        self.setPixmap(QPixmap())
        self.setText(self._title)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            return
        super().mousePressEvent(event)

    def _refresh(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            self.setPixmap(QPixmap())
            self.setText(self._title)
            return
        self.setText("")
        self.setPixmap(fit_pixmap(self._pixmap, self.width() - 28, self.height() - 28))


class SlideCardWidget(QWidget):
    clicked = Signal()

    def __init__(self, pixmap: QPixmap) -> None:
        super().__init__()
        self._pixmap = pixmap
        self._active = False

        self._preview = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self._preview)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()
        self._refresh()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply_style()

    def _apply_style(self) -> None:
        border = "#2EAF4E" if self._active else "#184524"
        bg = "#0E1711" if self._active else "#060908"
        self.setStyleSheet(
            f"""
            SlideCardWidget {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            """
        )

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            return
        super().mousePressEvent(event)

    def _refresh(self) -> None:
        if self._pixmap.isNull():
            self._preview.clear()
            return
        self._preview.setPixmap(fit_pixmap(self._pixmap, self.width() - 24, self.height() - 24))


class SlideListWidget(QListWidget):
    resized = Signal()
    next_requested = Signal()
    previous_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setViewMode(QListWidget.ViewMode.ListMode)
        self.setFlow(QListWidget.Flow.TopToBottom)
        self.setWrapping(False)
        self.setMovement(QListWidget.Movement.Static)
        self.setUniformItemSizes(False)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSpacing(10)
        self.setMinimumWidth(250)
        self._update_metrics()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_metrics()
        self.resized.emit()

    def _update_metrics(self) -> None:
        width = max(190, self.viewport().width() - 32)
        height = max(135, int(width * 0.62))
        self.setIconSize(QSize(width, height))
        self.setGridSize(QSize(width + 8, height + 8))

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_PageDown, Qt.Key.Key_Space):
            self.next_requested.emit()
            event.accept()
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_PageUp, Qt.Key.Key_Backspace):
            self.previous_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class DeckWorkspace(QWidget):
    outputs_changed = Signal()
    title_changed = Signal(str)
    state_changed = Signal()
    timer_defaults_requested = Signal()

    def __init__(self, path: Path | None, screens: list) -> None:
        super().__init__()
        self.backend = PdfBackend()
        self.state = PdfDocumentState()
        self._slide_cards: list[SlideCardWidget] = []

        self._timer_duration_ms = 15 * 60 * 1000
        self._timer_remaining_ms = self._timer_duration_ms
        self._timer_base_remaining_ms = self._timer_duration_ms
        self._timer_running = False
        self._timer_elapsed = QElapsedTimer()
        self._timer_tick = QTimer(self)
        self._timer_tick.setInterval(200)
        self._timer_tick.timeout.connect(self._refresh_timer_views)

        self._build_ui()
        self._connect_signals()
        self._apply_theme()
        self._sync_timer_duration_from_inputs()
        if path is not None:
            self.load_pdf(path)
        else:
            self.side_panel.setMinimumWidth(360)
            self.side_panel.setMaximumWidth(430)
            self.state_changed.emit()

    @property
    def title(self) -> str:
        if self.state.pdf_path is None:
            return "Новая вкладка"
        return self.state.pdf_path.name

    @property
    def has_document(self) -> bool:
        return self.state.has_document

    def current_slide_text(self) -> str:
        if not self.has_document:
            return "Слайд -"
        return f"Слайд {self.state.current_page + 1} / {self.state.page_count}"

    def status_title_text(self) -> str:
        if not self.has_document:
            return "Пустая вкладка"
        return self.title

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        self.thumbnail_list = SlideListWidget()
        root.addWidget(self.thumbnail_list, 1)

        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(16)

        preview_group = QGroupBox("Текущий слайд")
        preview_layout = QVBoxLayout(preview_group)
        self.current_preview = ClickablePreviewLabel("Открой PDF или нажми + для новой вкладки")
        preview_layout.addWidget(self.current_preview)
        center_layout.addWidget(preview_group, 1)

        hint_label = QLabel(
            "Перемотка: клик по большому слайду, стрелки Left/Right/Down, PageUp/PageDown или выбор миниатюры слева."
        )
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #90A097; padding: 0 2px;")
        center_layout.addWidget(hint_label)

        root.addWidget(center_panel, 3)

        self.side_panel = QWidget()
        self.side_panel.setObjectName("sidePanel")
        side_layout = QVBoxLayout(self.side_panel)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(16)
        self.side_panel.setMinimumWidth(360)
        self.side_panel.setMaximumWidth(430)

        self.deck_group = QGroupBox("Документ")
        deck_layout = QVBoxLayout(self.deck_group)
        self.file_label = QLabel("Открой PDF в этой вкладке")
        self.file_label.setWordWrap(True)
        self.slide_label = QLabel("Слайды пока не загружены")
        deck_layout.addWidget(self.file_label)
        deck_layout.addWidget(self.slide_label)
        side_layout.addWidget(self.deck_group)

        self.timer_group = QGroupBox("Таймер")
        timer_layout = QVBoxLayout(self.timer_group)
        self.timer_label = QLabel("15:00")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setObjectName("timerLabel")
        timer_layout.addWidget(self.timer_label)

        duration_row = QHBoxLayout()
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(0, 599)
        self.minutes_spin.setValue(15)
        self.seconds_spin = QSpinBox()
        self.seconds_spin.setRange(0, 59)
        duration_row.addWidget(QLabel("Мин"))
        duration_row.addWidget(self.minutes_spin)
        duration_row.addWidget(QLabel("Сек"))
        duration_row.addWidget(self.seconds_spin)
        timer_layout.addLayout(duration_row)

        timer_buttons = QHBoxLayout()
        self.timer_toggle_button = QPushButton("Старт")
        self.reset_timer_button = QPushButton("Сброс")
        self.reset_timer_button.setObjectName("dangerButton")
        timer_buttons.addWidget(self.timer_toggle_button)
        timer_buttons.addWidget(self.reset_timer_button)
        timer_layout.addLayout(timer_buttons)

        self.timer_defaults_button = QPushButton("Из настроек")
        self.timer_defaults_button.setObjectName("modeButton")
        timer_layout.addWidget(self.timer_defaults_button)
        side_layout.addWidget(self.timer_group)

        self.nav_group = QGroupBox("Навигация")
        nav_layout = QGridLayout(self.nav_group)
        self.prev_button = QPushButton("Предыдущий")
        self.next_button = QPushButton("Следующий")
        nav_layout.addWidget(self.prev_button, 0, 0)
        nav_layout.addWidget(self.next_button, 0, 1)
        side_layout.addWidget(self.nav_group)
        side_layout.addStretch(1)

        root.addWidget(self.side_panel, 1)

    def _connect_signals(self) -> None:
        self.thumbnail_list.currentRowChanged.connect(self._on_thumbnail_selected)
        self.thumbnail_list.resized.connect(self._refresh_thumbnail_layout)
        self.thumbnail_list.next_requested.connect(self.next_slide)
        self.thumbnail_list.previous_requested.connect(self.previous_slide)
        self.current_preview.clicked.connect(self.next_slide)
        self.prev_button.clicked.connect(self.previous_slide)
        self.next_button.clicked.connect(self.next_slide)
        self.timer_toggle_button.clicked.connect(self.toggle_timer)
        self.reset_timer_button.clicked.connect(self.reset_timer)
        self.timer_defaults_button.clicked.connect(self.timer_defaults_requested.emit)
        self.minutes_spin.valueChanged.connect(self._sync_timer_duration_from_inputs)
        self.seconds_spin.valueChanged.connect(self._sync_timer_duration_from_inputs)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #040706;
                color: #F5F8F6;
                font-size: 14px;
            }
            QPushButton, QSpinBox {
                background: #0A100C;
                color: #F5F8F6;
                border: 1px solid #1C3925;
                border-radius: 12px;
                padding: 9px 12px;
                min-height: 18px;
            }
            QPushButton:hover, QSpinBox:hover {
                border-color: #38B35A;
                background: #0E1611;
            }
            QPushButton#modeButton {
                background: #09120D;
                color: #A7EFB8;
                border-color: #245C33;
                font-weight: 700;
            }
            QPushButton#modeButton:checked {
                background: #169A42;
                color: #FFFFFF;
                border-color: #2EC65B;
            }
            QPushButton#dangerButton {
                background: #8F1F1F;
                border-color: #C63A3A;
                color: #FFFFFF;
                font-weight: 700;
            }
            QPushButton#dangerButton:hover {
                background: #A72626;
            }
            QGroupBox {
                background: #070B09;
                border: 1px solid #12261A;
                border-radius: 18px;
                margin-top: 14px;
                padding: 14px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #F7FBF8;
                font-size: 15px;
            }
            QListWidget {
                background: #050807;
                border: 1px solid #102116;
                border-radius: 20px;
                padding: 14px;
                outline: none;
            }
            QListWidget::item {
                background: transparent;
                border: none;
                margin: 3px 0;
                padding: 0;
            }
            QListWidget::item:selected {
                background: #0E1712;
                border: 1px solid #279447;
                border-radius: 16px;
            }
            QScrollBar:vertical {
                background: #040505;
                width: 10px;
                margin: 10px 2px 10px 2px;
            }
            QScrollBar::handle:vertical {
                background: #1F7A37;
                min-height: 48px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QLabel#timerLabel {
                color: #41E06D;
                font-size: 38px;
                font-weight: 700;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 20px;
                border: none;
                background: transparent;
            }
            QLabel {
                color: #EEF5F0;
            }
            """
        )

    def _update_document_labels(self) -> None:
        if self.state.pdf_path is None:
            self.file_label.setText("Открой PDF в этой вкладке")
            return
        self.file_label.setText(str(self.state.pdf_path))

    def set_timer_defaults(self, minutes: int, seconds: int) -> None:
        self.minutes_spin.blockSignals(True)
        self.seconds_spin.blockSignals(True)
        self.minutes_spin.setValue(minutes)
        self.seconds_spin.setValue(seconds)
        self.minutes_spin.blockSignals(False)
        self.seconds_spin.blockSignals(False)
        self._sync_timer_duration_from_inputs()

    def load_pdf(self, path: Path) -> None:
        try:
            page_count = self.backend.load(path)
        except Exception as exc:  # pragma: no cover - GUI error path
            QMessageBox.critical(self, "Ошибка открытия", str(exc))
            return

        self.state = PdfDocumentState(pdf_path=path, page_count=page_count, current_page=0, notes={})
        self._update_document_labels()
        self._populate_thumbnails()
        self._set_current_page(0)
        self.title_changed.emit(self.title)
        self.state_changed.emit()

    def close_backend(self) -> None:
        self.backend.close()

    def _populate_thumbnails(self) -> None:
        self.thumbnail_list.clear()
        self._slide_cards.clear()
        card_size = self.thumbnail_list.gridSize()
        preview_width = max(320, card_size.width() - 24)
        preview_height = max(180, card_size.height() - 24)
        for index in range(self.state.page_count):
            pixmap = self.backend.render_page(index, preview_width, preview_height)
            item = QListWidgetItem("")
            item.setToolTip(f"Слайд {index + 1}")
            item.setSizeHint(card_size)
            self.thumbnail_list.addItem(item)
            card = SlideCardWidget(pixmap)
            card.clicked.connect(lambda _checked=False, row=index: self.thumbnail_list.setCurrentRow(row))
            self.thumbnail_list.setItemWidget(item, card)
            self._slide_cards.append(card)
        self._refresh_thumbnail_layout()

    def _refresh_thumbnail_layout(self) -> None:
        card_size = self.thumbnail_list.gridSize()
        for row in range(self.thumbnail_list.count()):
            item = self.thumbnail_list.item(row)
            item.setSizeHint(card_size)
        for row, card in enumerate(self._slide_cards):
            card.set_active(row == self.state.current_page)

    def next_slide(self) -> None:
        if not self.has_document:
            return
        self._set_current_page(min(self.state.current_page + 1, self.state.page_count - 1))

    def previous_slide(self) -> None:
        if not self.has_document:
            return
        self._set_current_page(max(self.state.current_page - 1, 0))

    def _set_current_page(self, index: int) -> None:
        if not self.has_document or index < 0 or index >= self.state.page_count:
            return
        self.state.current_page = index
        if self.thumbnail_list.currentRow() != index:
            self.thumbnail_list.blockSignals(True)
            self.thumbnail_list.setCurrentRow(index)
            self.thumbnail_list.blockSignals(False)
        self._refresh_preview()

    def _on_thumbnail_selected(self, row: int) -> None:
        self._set_current_page(row)

    def _refresh_preview(self) -> None:
        if not self.has_document:
            self.current_preview.clear_preview()
            self._update_document_labels()
            self.slide_label.setText("Слайды пока не загружены")
            self.current_preview.setStyleSheet(
                """
                QLabel {
                    background: #07100B;
                    color: #7FA08B;
                    border: 1px dashed #21512E;
                    border-radius: 18px;
                    padding: 14px;
                }
                """
            )
            self.state_changed.emit()
            return

        current = self.state.current_page
        self.current_preview.setStyleSheet(
            """
            QLabel {
                background: #07090B;
                color: #B7C0C8;
                border: 1px solid #16361E;
                border-radius: 16px;
                padding: 14px;
            }
            """
        )
        current_pixmap = self.backend.render_page(current, 1800, 1200)
        self.current_preview.set_preview(current_pixmap)
        self._update_document_labels()
        self.slide_label.setText(f"Слайд: {current + 1} / {self.state.page_count}")
        self._refresh_thumbnail_layout()
        self.outputs_changed.emit()
        self.state_changed.emit()

    def _sync_timer_duration_from_inputs(self) -> None:
        self._timer_duration_ms = ((self.minutes_spin.value() * 60) + self.seconds_spin.value()) * 1000
        if not self._timer_running:
            self._timer_remaining_ms = self._timer_duration_ms
            self._timer_base_remaining_ms = self._timer_duration_ms
            self._refresh_timer_views()

    def start_timer(self) -> None:
        if self._timer_running:
            return
        if self._timer_remaining_ms <= 0:
            self._timer_remaining_ms = self._timer_duration_ms
        self._timer_base_remaining_ms = self._timer_remaining_ms
        self._timer_elapsed.start()
        self._timer_running = True
        self._timer_tick.start()
        self._refresh_timer_views()

    def pause_timer(self) -> None:
        if not self._timer_running:
            return
        self._timer_remaining_ms = self._current_remaining_ms()
        self._timer_base_remaining_ms = self._timer_remaining_ms
        self._timer_running = False
        self._timer_tick.stop()
        self._refresh_timer_views()

    def toggle_timer(self) -> None:
        if self._timer_running:
            self.pause_timer()
            return
        self.start_timer()

    def reset_timer(self) -> None:
        self._timer_running = False
        self._timer_tick.stop()
        self._timer_remaining_ms = self._timer_duration_ms
        self._timer_base_remaining_ms = self._timer_duration_ms
        self._refresh_timer_views()

    def _current_remaining_ms(self) -> int:
        if not self._timer_running:
            return max(0, self._timer_remaining_ms)
        return max(0, self._timer_base_remaining_ms - self._timer_elapsed.elapsed())

    def _refresh_timer_views(self) -> None:
        if self._timer_running:
            self._timer_remaining_ms = self._current_remaining_ms()
            if self._timer_remaining_ms == 0:
                self._timer_running = False
                self._timer_tick.stop()

        self.timer_label.setText(self.remaining_text())
        self.minutes_spin.setEnabled(not self._timer_running)
        self.seconds_spin.setEnabled(not self._timer_running)
        self._update_timer_button()
        self.outputs_changed.emit()
        self.state_changed.emit()

    def _update_timer_button(self) -> None:
        if self._timer_running:
            self.timer_toggle_button.setText("Пауза")
            return
        if self._timer_remaining_ms == self._timer_duration_ms or self._timer_remaining_ms == 0:
            self.timer_toggle_button.setText("Старт")
            return
        self.timer_toggle_button.setText("Продолжить")

    def remaining_text(self) -> str:
        total_seconds = max(0, self._timer_remaining_ms) // 1000
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def output_payload(self) -> dict[str, object] | None:
        if not self.has_document:
            return None

        current_index = self.state.current_page
        current_pixmap = self.backend.render_page(current_index, 2600, 1800)
        if current_index + 1 < self.state.page_count:
            next_pixmap = self.backend.render_page(current_index + 1, 1400, 1000)
        else:
            next_pixmap = QPixmap()
        return {
            "current_pixmap": current_pixmap,
            "next_pixmap": next_pixmap,
            "page_index": current_index,
            "page_count": self.state.page_count,
            "remaining_text": self.remaining_text(),
        }

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_PageDown, Qt.Key.Key_Space):
            self.next_slide()
            event.accept()
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_PageUp, Qt.Key.Key_Backspace):
            self.previous_slide()
            event.accept()
            return
        super().keyPressEvent(event)
