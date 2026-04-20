from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QEasingCurve, QElapsedTimer, QPropertyAnimation, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap
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
    QProgressBar,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pdfbread.i18n import tr
from pdfbread.pdf_backend import PdfBackend, fit_pixmap
from pdfbread.state import PdfDocumentState
from pdfbread.ui_theme import (
    empty_preview_label_style,
    hint_label_style,
    preview_label_style,
    slide_card_style,
    workspace_stylesheet,
)


class ClickablePreviewLabel(QLabel):
    clicked = Signal()
    _PREVIEW_Y_OFFSET = 10

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
        self.setStyleSheet(preview_label_style())
        self.clear_preview()

    def reload_theme(self, *, empty: bool) -> None:
        self.setStyleSheet(empty_preview_label_style() if empty else preview_label_style())
        self._refresh()

    def set_title(self, title: str) -> None:
        self._title = title
        self._refresh()

    def set_preview(self, pixmap: QPixmap) -> None:
        was_empty = self._pixmap is None or self._pixmap.isNull()
        self._pixmap = pixmap
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMaximumHeight(16777215)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._refresh()
        self._fade.stop()
        self._fade.setDuration(240 if was_empty else 150)
        self._fade.setStartValue(0.0 if was_empty else 0.64)
        self._fade.setEndValue(1.0)
        self._fade.start()

    def clear_preview(self) -> None:
        self._pixmap = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMaximumHeight(16777215)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._fade.stop()
        self._opacity.setOpacity(1.0)
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
        content_width = max(1, self.width() - 28)
        content_height = max(1, self.height() - 28)
        fitted = fit_pixmap(self._pixmap, content_width, content_height)
        canvas = QPixmap(content_width, content_height)
        canvas.fill(Qt.GlobalColor.transparent)

        draw_x = (content_width - fitted.width()) // 2
        draw_y = (content_height - fitted.height()) // 2 + self._PREVIEW_Y_OFFSET

        painter = QPainter(canvas)
        painter.drawPixmap(draw_x, draw_y, fitted)
        painter.end()

        self.setPixmap(canvas)


class SlideCardWidget(QWidget):
    clicked = Signal()
    _CONTENT_MARGIN = 12
    _CONTENT_Y_OFFSET = -2

    def __init__(self, pixmap: QPixmap) -> None:
        super().__init__()
        self._pixmap = pixmap
        self._fitted_pixmap = QPixmap()
        self._active = False
        self._live = False
        self._hover_progress = 0.0
        self._hover_animation = QPropertyAnimation(self, b"hoverProgress", self)
        self._hover_animation.setDuration(140)
        self._hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()
        self._refresh()

    def get_hover_progress(self) -> float:
        return self._hover_progress

    def set_hover_progress(self, value: float) -> None:
        self._hover_progress = max(0.0, min(1.0, value))
        self.update()

    hoverProgress = Property(float, get_hover_progress, set_hover_progress)

    def set_active(self, active: bool) -> None:
        self.set_state(active=active, live=self._live)

    def set_state(self, *, active: bool, live: bool) -> None:
        self._active = active
        self._live = live
        self._apply_style()
        self.update()

    def reload_theme(self) -> None:
        self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet(slide_card_style(self._active))

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        if self._fitted_pixmap.isNull():
            return

        content_rect = self.contentsRect().adjusted(
            self._CONTENT_MARGIN,
            self._CONTENT_MARGIN,
            -self._CONTENT_MARGIN,
            -self._CONTENT_MARGIN,
        )
        draw_x = content_rect.x() + (content_rect.width() - self._fitted_pixmap.width()) // 2
        draw_y = (
            content_rect.y()
            + (content_rect.height() - self._fitted_pixmap.height()) // 2
            + self._CONTENT_Y_OFFSET
        )

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.drawPixmap(draw_x, draw_y, self._fitted_pixmap)
        if self._live or self._active or self._hover_progress > 0:
            border = QColor("#f85149" if self._live else ("#58a6ff" if self._active else "#8b949e"))
            border.setAlpha(255 if (self._live or self._active) else int(80 + 90 * self._hover_progress))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(border, 2 if self._live else 1.5))
            painter.drawRoundedRect(self.rect().adjusted(4, 4, -5, -7), 12, 12)
        painter.end()

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            return
        super().mousePressEvent(event)

    def _animate_hover(self, target: float) -> None:
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_progress)
        self._hover_animation.setEndValue(target)
        self._hover_animation.start()

    def _refresh(self) -> None:
        if self._pixmap.isNull():
            self._fitted_pixmap = QPixmap()
            self.update()
            return
        content_rect = self.contentsRect().adjusted(
            self._CONTENT_MARGIN,
            self._CONTENT_MARGIN,
            -self._CONTENT_MARGIN,
            -self._CONTENT_MARGIN,
        )
        content_width = max(1, content_rect.width())
        content_height = max(1, content_rect.height())
        self._fitted_pixmap = fit_pixmap(self._pixmap, content_width, content_height)
        self.update()


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
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setSpacing(10)
        self.setMinimumWidth(160)
        self._update_metrics()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._update_metrics():
            self.resized.emit()

    def _update_metrics(self) -> bool:
        available_width = max(1, self.viewport().contentsRect().width())
        width = max(96, available_width - 44)
        height = max(68, int(width * 0.62))
        card_size = QSize(width, height)
        if self.iconSize() == card_size and self.gridSize() == card_size:
            return False
        self.setIconSize(card_size)
        self.setGridSize(card_size)
        return True

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
    _EMPTY_PREVIEW_GROUP_HEIGHT = 430
    _LOADED_PREVIEW_MAX_HEIGHT = 700
    def __init__(self, path: Path | None, screens: list) -> None:
        super().__init__()
        self.backend = PdfBackend()
        self.state = PdfDocumentState()
        self._slide_cards: list[SlideCardWidget] = []
        self._page_render_cache: dict[tuple[int, int, int], QPixmap] = {}

        self._timer_duration_ms = 15 * 60 * 1000
        self._timer_remaining_ms = self._timer_duration_ms
        self._timer_base_remaining_ms = self._timer_duration_ms
        self._timer_running = False
        self._timer_elapsed = QElapsedTimer()
        self._timer_tick = QTimer(self)
        self._timer_tick.setInterval(200)
        self._timer_tick.timeout.connect(self._refresh_timer_views)
        self._output_active = False

        self._build_ui()
        self._preview_group_animation = QPropertyAnimation(self.preview_group, b"maximumHeight", self)
        self._preview_group_animation.setDuration(220)
        self._preview_group_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._connect_signals()
        self._apply_theme()
        self._sync_timer_duration_from_inputs()
        if path is not None:
            self.load_pdf(path)
        else:
            self.side_panel.setMinimumWidth(360)
            self.side_panel.setMaximumWidth(430)
            self._apply_empty_preview_group_height()
            self.state_changed.emit()

    @property
    def title(self) -> str:
        if self.state.pdf_path is None:
            return tr("new_tab")
        return self.state.pdf_path.name

    @property
    def has_document(self) -> bool:
        return self.state.has_document

    def current_slide_text(self) -> str:
        if not self.has_document:
            return tr("slide_dash")
        return tr("slide_counter", current=self.state.current_page + 1, total=self.state.page_count)

    def status_title_text(self) -> str:
        if not self.has_document:
            return tr("empty_tab")
        return self.title

    @staticmethod
    def _section_title(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitleLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return label

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

        preview_group = QGroupBox()
        preview_group.setObjectName("previewGroup")
        self.preview_group = preview_group
        preview_layout = QVBoxLayout(preview_group)
        self.preview_title_label = self._section_title("")
        preview_layout.addWidget(self.preview_title_label, 0, Qt.AlignmentFlag.AlignTop)
        self.current_preview = ClickablePreviewLabel("")
        self.current_preview.setObjectName("currentPreviewLabel")
        preview_layout.addWidget(self.current_preview, 0, Qt.AlignmentFlag.AlignTop)
        center_layout.addWidget(preview_group, 1)

        hint_label = QLabel()
        self.hint_label = hint_label
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet(hint_label_style())
        center_layout.addWidget(hint_label)

        root.addWidget(center_panel, 3)

        self.side_panel = QWidget()
        self.side_panel.setObjectName("sidePanel")
        side_layout = QVBoxLayout(self.side_panel)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(16)
        self.side_panel.setMinimumWidth(360)
        self.side_panel.setMaximumWidth(430)

        self.deck_group = QGroupBox()
        self.deck_group.setObjectName("deckGroup")
        deck_layout = QVBoxLayout(self.deck_group)
        self.deck_title_label = self._section_title("")
        deck_layout.addWidget(self.deck_title_label, 0, Qt.AlignmentFlag.AlignTop)
        self.file_label = QLabel()
        self.file_label.setObjectName("fileInfoLabel")
        self.file_label.setWordWrap(True)
        self.slide_label = QLabel()
        self.slide_label.setObjectName("slideInfoLabel")
        deck_layout.addWidget(self.file_label)
        deck_layout.addWidget(self.slide_label)
        side_layout.addWidget(self.deck_group)

        self.timer_group = QGroupBox()
        self.timer_group.setObjectName("timerGroup")
        timer_layout = QVBoxLayout(self.timer_group)
        self.timer_title_label = self._section_title("")
        timer_layout.addWidget(self.timer_title_label, 0, Qt.AlignmentFlag.AlignTop)
        self.timer_label = QLabel("15:00")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setObjectName("timerLabel")
        timer_layout.addWidget(self.timer_label)
        self.timer_progress = QProgressBar()
        self.timer_progress.setObjectName("timerProgressBar")
        self.timer_progress.setRange(0, 1000)
        self.timer_progress.setValue(1000)
        self.timer_progress.setTextVisible(False)
        timer_layout.addWidget(self.timer_progress)

        duration_row = QHBoxLayout()
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(0, 599)
        self.minutes_spin.setValue(15)
        self.seconds_spin = QSpinBox()
        self.seconds_spin.setRange(0, 59)
        self.minutes_label = QLabel()
        self.seconds_label = QLabel()
        duration_row.addWidget(self.minutes_label)
        duration_row.addWidget(self.minutes_spin)
        duration_row.addWidget(self.seconds_label)
        duration_row.addWidget(self.seconds_spin)
        timer_layout.addLayout(duration_row)

        timer_buttons = QHBoxLayout()
        self.timer_toggle_button = QPushButton()
        self.timer_toggle_button.setObjectName("timerToggleButton")
        self.timer_toggle_button.setProperty("timerState", "start")
        self.reset_timer_button = QPushButton()
        self.reset_timer_button.setObjectName("dangerButton")
        timer_buttons.addWidget(self.timer_toggle_button)
        timer_buttons.addWidget(self.reset_timer_button)
        timer_layout.addLayout(timer_buttons)

        self.timer_defaults_button = QPushButton()
        self.timer_defaults_button.setObjectName("timerDefaultsButton")
        timer_layout.addWidget(self.timer_defaults_button)
        side_layout.addWidget(self.timer_group)

        self.nav_group = QGroupBox()
        self.nav_group.setObjectName("navGroup")
        nav_layout = QGridLayout(self.nav_group)
        self.nav_title_label = self._section_title("")
        nav_layout.addWidget(self.nav_title_label, 0, 0, 1, 2, Qt.AlignmentFlag.AlignTop)
        self.prev_button = QPushButton()
        self.prev_button.setObjectName("prevButton")
        self.next_button = QPushButton()
        self.next_button.setObjectName("nextButton")
        nav_layout.addWidget(self.prev_button, 1, 0)
        nav_layout.addWidget(self.next_button, 1, 1)
        side_layout.addWidget(self.nav_group)
        side_layout.addStretch(1)

        root.addWidget(self.side_panel, 1)
        self.retranslate()
        self._apply_responsive_layout()

    def _apply_empty_preview_group_height(self) -> None:
        self.preview_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.preview_group.setMaximumHeight(self._EMPTY_PREVIEW_GROUP_HEIGHT)

    def _loaded_preview_height_cap(self) -> int:
        return min(self._LOADED_PREVIEW_MAX_HEIGHT, max(320, self.height() - 140))

    def _target_preview_group_height(self, pixmap: QPixmap) -> int:
        available_width = max(1, self.current_preview.width() - 28)
        fitted = fit_pixmap(pixmap, available_width, 10000)
        height_cap = self._loaded_preview_height_cap()
        preview_height = min(height_cap, max(320, fitted.height() + 28))
        self.current_preview.setMinimumHeight(preview_height)
        self.current_preview.setMaximumHeight(preview_height)
        self.current_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = self.preview_group.layout()
        if layout is not None:
            layout.activate()
        return self.preview_group.sizeHint().height()

    def _apply_loaded_preview_group_height(self, pixmap: QPixmap, *, animated: bool) -> None:
        target_height = self._target_preview_group_height(pixmap)
        self.preview_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._preview_group_animation.stop()
        if animated:
            self._preview_group_animation.setStartValue(self.preview_group.maximumHeight())
            self._preview_group_animation.setEndValue(target_height)
            self._preview_group_animation.start()
        else:
            self.preview_group.setMaximumHeight(target_height)

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
        self.setStyleSheet(workspace_stylesheet())

    def reload_theme(self) -> None:
        self._apply_theme()
        self.hint_label.setStyleSheet(hint_label_style())
        self.current_preview.reload_theme(empty=not self.has_document)
        for card in self._slide_cards:
            card.reload_theme()
        self._refresh_preview()

    def set_output_active(self, active: bool) -> None:
        if self._output_active == active:
            return
        self._output_active = active
        self._refresh_thumbnail_layout()

    def retranslate(self) -> None:
        self.preview_title_label.setText(tr("workspace.current_slide"))
        self.current_preview.set_title(tr("workspace.open_hint"))
        self.hint_label.setText(tr("workspace.navigation_hint"))
        self.deck_title_label.setText(tr("workspace.document"))
        self.timer_title_label.setText(tr("workspace.timer"))
        self.nav_title_label.setText(tr("workspace.navigation"))
        self.minutes_label.setText(tr("settings.minutes"))
        self.seconds_label.setText(tr("settings.seconds"))
        self.reset_timer_button.setText(tr("timer.reset"))
        self.timer_defaults_button.setText(tr("timer.from_settings"))
        self.prev_button.setText(tr("workspace.previous"))
        self.next_button.setText(tr("workspace.next"))
        self._update_document_labels()
        self._update_timer_button()
        if not self.has_document:
            self.slide_label.setText(tr("workspace.no_slides"))
        else:
            self.slide_label.setText(tr("slide_label", current=self.state.current_page + 1, total=self.state.page_count))
            for index in range(self.thumbnail_list.count()):
                item = self.thumbnail_list.item(index)
                item.setToolTip(tr("slide_counter", current=index + 1, total=self.state.page_count))

    def _update_document_labels(self) -> None:
        if self.state.pdf_path is None:
            self.file_label.setText(tr("workspace.open_pdf_here"))
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
            QMessageBox.critical(self, tr("dialog.open_error"), str(exc))
            return

        self._page_render_cache.clear()
        self.state = PdfDocumentState(pdf_path=path, page_count=page_count, current_page=0, notes={})
        self._update_document_labels()
        self._populate_thumbnails()
        self._set_current_page(0)
        self.title_changed.emit(self.title)
        self.state_changed.emit()

    def close_backend(self) -> None:
        self._page_render_cache.clear()
        self.backend.close()

    def _render_page_cached(self, index: int, width: int, height: int) -> QPixmap:
        width = max(1, width)
        height = max(1, height)
        cache_key = (index, width, height)
        cached = self._page_render_cache.get(cache_key)
        if cached is not None:
            return cached

        pixmap = self.backend.render_page(index, width, height)
        self._page_render_cache[cache_key] = pixmap
        return pixmap

    def _populate_thumbnails(self) -> None:
        self.thumbnail_list.clear()
        self._slide_cards.clear()
        card_size = self.thumbnail_list.gridSize()
        row_size = QSize(card_size.width(), card_size.height() + 4)
        preview_width = max(320, card_size.width() - 24)
        preview_height = max(180, card_size.height() - 24)
        for index in range(self.state.page_count):
            pixmap = self._render_page_cached(index, preview_width, preview_height)
            item = QListWidgetItem("")
            item.setToolTip(tr("slide_counter", current=index + 1, total=self.state.page_count))
            item.setSizeHint(row_size)
            self.thumbnail_list.addItem(item)
            card = SlideCardWidget(pixmap)
            card.setFixedSize(self.thumbnail_list.iconSize())
            card.clicked.connect(lambda _checked=False, row=index: self.thumbnail_list.setCurrentRow(row))
            row_host = QWidget()
            row_layout = QHBoxLayout(row_host)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)
            row_layout.addStretch(1)
            row_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            row_layout.addStretch(1)
            self.thumbnail_list.setItemWidget(item, row_host)
            self._slide_cards.append(card)
        self._refresh_thumbnail_layout()

    def _refresh_thumbnail_layout(self) -> None:
        card_size = self.thumbnail_list.gridSize()
        row_size = QSize(card_size.width(), card_size.height() + 4)
        for row in range(self.thumbnail_list.count()):
            item = self.thumbnail_list.item(row)
            item.setSizeHint(row_size)
        for row, card in enumerate(self._slide_cards):
            card.setFixedSize(self.thumbnail_list.iconSize())
            is_current = row == self.state.current_page
            card.set_state(active=is_current, live=self._output_active and is_current)

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
            self._apply_empty_preview_group_height()
            self.current_preview.clear_preview()
            self._update_document_labels()
            self.slide_label.setText(tr("workspace.no_slides"))
            self.current_preview.setStyleSheet(empty_preview_label_style())
            self.state_changed.emit()
            return

        current = self.state.current_page
        first_load = self.preview_group.maximumHeight() == self._EMPTY_PREVIEW_GROUP_HEIGHT
        self.current_preview.setStyleSheet(preview_label_style())
        current_pixmap = self._render_page_cached(current, 1800, 1200)
        self._apply_loaded_preview_group_height(current_pixmap, animated=first_load)
        self.current_preview.set_preview(current_pixmap)
        self._update_document_labels()
        self.slide_label.setText(tr("slide_label", current=current + 1, total=self.state.page_count))
        self._refresh_thumbnail_layout()
        self.outputs_changed.emit()
        self.state_changed.emit()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_responsive_layout()
        if self.has_document:
            current = self.state.current_page
            current_pixmap = self._render_page_cached(current, 1800, 1200)
            self._apply_loaded_preview_group_height(current_pixmap, animated=False)

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
        progress = 0 if self._timer_duration_ms <= 0 else int((self._timer_remaining_ms / self._timer_duration_ms) * 1000)
        self.timer_progress.setValue(max(0, min(1000, progress)))
        self.minutes_spin.setEnabled(not self._timer_running)
        self.seconds_spin.setEnabled(not self._timer_running)
        self._update_timer_button()
        self.outputs_changed.emit()
        self.state_changed.emit()

    def _update_timer_button(self) -> None:
        if self._timer_running:
            self._set_timer_button_state("pause", tr("timer.pause"))
            return
        if self._timer_remaining_ms == self._timer_duration_ms or self._timer_remaining_ms == 0:
            self._set_timer_button_state("start", tr("timer.start"))
            return
        self._set_timer_button_state("continue", tr("timer.continue"))

    def _set_timer_button_state(self, state: str, text: str) -> None:
        self.timer_toggle_button.setText(text)
        self.timer_toggle_button.setProperty("timerState", state)
        self.timer_toggle_button.style().unpolish(self.timer_toggle_button)
        self.timer_toggle_button.style().polish(self.timer_toggle_button)
        self.timer_toggle_button.update()

    def remaining_text(self) -> str:
        total_seconds = max(0, self._timer_remaining_ms) // 1000
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def output_payload(
        self,
        *,
        current_size: tuple[int, int] = (2600, 1800),
        next_size: tuple[int, int] = (1400, 1000),
    ) -> dict[str, object] | None:
        if not self.has_document:
            return None

        current_index = self.state.current_page
        current_pixmap = self._render_page_cached(current_index, *current_size)
        if current_index + 1 < self.state.page_count:
            next_pixmap = self._render_page_cached(current_index + 1, *next_size)
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

    def _apply_responsive_layout(self) -> None:
        if not hasattr(self, "side_panel"):
            return
        width = self.width()
        hide_side = width < 980
        compact_side = width < 1220
        self.side_panel.setVisible(not hide_side)
        if compact_side:
            self.side_panel.setMinimumWidth(280)
            self.side_panel.setMaximumWidth(330)
        else:
            self.side_panel.setMinimumWidth(360)
            self.side_panel.setMaximumWidth(430)
