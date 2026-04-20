from __future__ import annotations

import math
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QCloseEvent, QIcon, QKeyEvent, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionTab,
    QStyleOptionToolButton,
    QStylePainter,
    QTabBar,
    QTabWidget,
    QToolButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pdfbread.i18n import set_language, tr
from pdfbread.ndi_output import NdiApplyResult, NdiOutputController
from pdfbread.paths import app_resource
from pdfbread.presentation_window import PresentationWindow, render_presentation_frame
from pdfbread.settings_tab import SettingsTab
from pdfbread.teleprompter_window import TeleprompterWindow, render_teleprompter_frame
from pdfbread.ui_theme import (
    main_window_stylesheet,
    output_status_icon_color,
    settings_stylesheet,
    transport_button_style,
    transport_icon_color,
)
from pdfbread.workspace import DeckWorkspace


APP_VERSION = "0.1.0"
TITLE_BAR_BG = "#0d1117"
TITLE_BAR_TEXT = "#e6edf3"


def _colorref(hex_color: str) -> int:
    color = QColor(hex_color)
    return color.red() | (color.green() << 8) | (color.blue() << 16)


def apply_windows_title_bar_color(widget: QWidget, *, background: str = TITLE_BAR_BG, text: str = TITLE_BAR_TEXT) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return

    hwnd = wintypes.HWND(int(widget.winId()))
    dwmapi = ctypes.windll.dwmapi

    def set_attribute(attribute: int, value: int) -> None:
        data = ctypes.c_int(value)
        dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(data), ctypes.sizeof(data))

    # Windows 10/11 DWM attributes. Older builds ignore unsupported attributes.
    set_attribute(20, 1)  # DWMWA_USE_IMMERSIVE_DARK_MODE
    set_attribute(35, _colorref(background))  # DWMWA_CAPTION_COLOR
    set_attribute(36, _colorref(text))  # DWMWA_TEXT_COLOR


class OffsetToolButton(QToolButton):
    def __init__(self, text_y_offset: int = 0) -> None:
        super().__init__()
        self._text_y_offset = text_y_offset

    def set_text_y_offset(self, offset: int) -> None:
        self._text_y_offset = offset
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        option = QStyleOptionToolButton()
        self.initStyleOption(option)
        button_text = option.text
        option.text = ""

        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ToolButton, option)
        painter.setPen(option.palette.buttonText().color())
        painter.setFont(self.font())
        painter.drawText(self.rect().adjusted(0, self._text_y_offset, 0, self._text_y_offset), Qt.AlignmentFlag.AlignCenter, button_text)


class CleanTabBar(QTabBar):
    def __init__(self) -> None:
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setDrawBase(False)
        self._add_button: QToolButton | None = None
        self._add_button_host: QWidget | None = None
        self._add_button_spacing = 30
        self._add_button_left_padding = 80
        self._add_button_right_padding = -35
        self._presenting_index = -1
        self._pulse_phase = 0.0
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(33)
        self._pulse_timer.timeout.connect(self._tick_pulse)

    def set_presenting_index(self, index: int) -> None:
        if self._presenting_index == index:
            return
        self._presenting_index = index
        self._pulse_phase = 0.0
        if index >= 0:
            self._pulse_timer.start()
        else:
            self._pulse_timer.stop()
        self.update()

    def _tick_pulse(self) -> None:
        self._pulse_phase = (self._pulse_phase + 0.075) % (math.pi * 2)
        if self._presenting_index >= 0:
            self.update(self.tabRect(self._presenting_index).adjusted(-4, -4, 4, 4))

    def set_add_button(self, button: QToolButton, host: QWidget | None = None) -> None:
        self._add_button = button
        self._add_button_host = host if host is not None else self
        button.setParent(self._add_button_host)
        button.show()
        self._reposition_add_button()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QStylePainter(self)
        option = QStyleOptionTab()
        for index in range(self.count()):
            self.initStyleOption(option, index)
            option.state &= ~QStyle.StateFlag.State_HasFocus
            painter.drawControl(QStyle.ControlElement.CE_TabBarTabShape, option)
            if index == self._presenting_index:
                self._draw_presenting_glow(painter, self.tabRect(index))
            painter.drawControl(QStyle.ControlElement.CE_TabBarTabLabel, option)

    def _draw_presenting_glow(self, painter: QStylePainter, rect: QRect) -> None:
        pulse = (math.sin(self._pulse_phase) + 1.0) / 2.0
        border_alpha = int(120 + 90 * pulse)
        glow_rect = rect.adjusted(1, 1, -1, -2)

        live_color = "#f85149"
        border_color = QColor(live_color)
        border_color.setAlpha(border_alpha)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(border_color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        left = glow_rect.left()
        right = glow_rect.right()
        top = glow_rect.top()
        bottom = glow_rect.bottom()
        radius = 12
        painter.drawArc(QRect(left, top, radius * 2, radius * 2), 90 * 16, 90 * 16)
        painter.drawArc(QRect(right - radius * 2, top, radius * 2, radius * 2), 0, 90 * 16)
        painter.drawLine(left + radius, top, right - radius, top)
        painter.drawLine(left, top + radius, left, bottom + 3)
        painter.drawLine(right, top + radius, right, bottom + 3)
        painter.restore()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._reposition_add_button()

    def moveEvent(self, event) -> None:  # type: ignore[override]
        super().moveEvent(event)
        self._reposition_add_button()

    def tabInserted(self, index: int) -> None:  # type: ignore[override]
        super().tabInserted(index)
        self._reposition_add_button()

    def tabRemoved(self, index: int) -> None:  # type: ignore[override]
        super().tabRemoved(index)
        self._reposition_add_button()

    def _reposition_add_button(self) -> None:
        if self._add_button is None or self._add_button_host is None:
            return

        hint = self._add_button.sizeHint()
        button_width = max(hint.width(), self._add_button.width())
        button_height = max(hint.height(), self._add_button.height())
        button_y = max(0, (self.height() - button_height) // 2) + 2

        if self.count() > 0:
            last_rect = self.tabRect(self.count() - 1)
            button_x = last_rect.x() + last_rect.width() + self._add_button_spacing
            if button_x + button_width > self.width() - 8:
                button_x = self.width() + 8
        else:
            button_x = self._add_button_left_padding

        host_pos = self.mapTo(self._add_button_host, self.rect().topLeft())
        max_x = max(
            self._add_button_left_padding,
            self._add_button_host.width() - host_pos.x() - button_width - 8,
        )
        button_x = min(button_x, max_x)
        self._add_button.setGeometry(
            host_pos.x() + button_x,
            host_pos.y() + button_y,
            button_width,
            button_height,
        )
        self._add_button.raise_()


class MainWindow(QMainWindow):
    _NDI_SUPERSAMPLE_FACTOR = 2
    _TAB_CLOSE_BUTTON_OFFSET = 1
    _TAB_CLOSE_BUTTON_AREA_WIDTH = 60
    _TAB_CLOSE_BUTTON_SIZE = 22

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDFBread")
        self.resize(1500, 940)
        app_icon = load_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self.presentation_window = PresentationWindow()
        self.teleprompter_window = TeleprompterWindow()
        self.ndi_controller = NdiOutputController()
        self._ndi_frame_note = ""
        self._ndi_status = NdiApplyResult(
            requested=False,
            available=self.ndi_controller.library.available,
            active_names=[],
            message=tr("ndi.off_tab"),
        )
        if not app_icon.isNull():
            self.presentation_window.setWindowIcon(app_icon)
            self.teleprompter_window.setWindowIcon(app_icon)
        self._presenting_workspace: DeckWorkspace | None = None

        self._build_ui()
        self._apply_theme()
        apply_windows_title_bar_color(self)
        self._refresh_screen_choices()
        self._apply_ndi_settings()
        self._add_workspace()
        self._update_transport_state()
        app = QApplication.instance()
        if app is not None:
            app.screenAdded.connect(lambda _screen: self._refresh_screen_choices())
            app.screenRemoved.connect(lambda _screen: self._refresh_screen_choices())

    def _build_ui(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        self.open_button = QPushButton()
        self.open_button.setObjectName("toolbarActionButton")
        self.open_button.clicked.connect(self.open_pdf)
        toolbar.addWidget(self.open_button)

        self.settings_button = QPushButton()
        self.settings_button.setObjectName("toolbarActionButton")
        self.settings_button.clicked.connect(self._open_settings_dialog)
        toolbar.addWidget(self.settings_button)

        self.about_button = QPushButton()
        self.about_button.setObjectName("toolbarActionButton")
        self.about_button.clicked.connect(self._open_about_dialog)
        toolbar.addWidget(self.about_button)

        self.toolbar_status = QWidget()
        self.toolbar_status_layout = QHBoxLayout(self.toolbar_status)
        self.toolbar_status_layout.setContentsMargins(10, 0, 10, 0)
        self.toolbar_status_layout.setSpacing(8)

        self.toolbar_file_label = QLabel()
        self.toolbar_file_label.setObjectName("toolbarFilePill")
        self.toolbar_slide_label = QLabel()
        self.toolbar_slide_label.setObjectName("toolbarSlidePill")
        self.toolbar_status_layout.addWidget(self.toolbar_file_label)
        self.toolbar_status_layout.addWidget(self.toolbar_slide_label)
        self.toolbar_credit_label = QLabel("Developed by LZMZ")
        self.toolbar_credit_label.setObjectName("toolbarCreditLabel")
        self.toolbar_status_layout.addWidget(self.toolbar_credit_label)
        self.presentation_status_icon = self._create_output_status_icon(tr("status.main_screen"), "monitor")
        self.teleprompter_status_icon = self._create_output_status_icon(tr("status.teleprompter"), "prompter")
        self.ndi_status_icon = self._create_output_status_icon(tr("status.ndi"), "ndi")
        self.toolbar_status_layout.addWidget(self.presentation_status_icon)
        self.toolbar_status_layout.addWidget(self.teleprompter_status_icon)
        self.toolbar_status_layout.addWidget(self.ndi_status_icon)
        self.toolbar_switch_output_button = QPushButton()
        self.toolbar_switch_output_button.setObjectName("switchOutputButton")
        self.toolbar_switch_output_button.clicked.connect(self._switch_output_to_current_tab)
        self.toolbar_switch_output_button.hide()
        self.toolbar_status_layout.addWidget(self.toolbar_switch_output_button)
        toolbar.addWidget(self.toolbar_status)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        self._refresh_transport_icons()
        self._stop_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
        self.transport_toolbar_button = QPushButton("")
        self.transport_toolbar_button.setIcon(self._play_icon)
        self.transport_toolbar_button.setObjectName("transportButton")
        self.transport_toolbar_button.setFixedSize(42, 42)
        self.transport_toolbar_button.clicked.connect(self._toggle_outputs)
        toolbar.addWidget(self.transport_toolbar_button)

        self.tabs = QTabWidget()
        self.tabs_tab_bar = CleanTabBar()
        self.tabs.setTabBar(self.tabs_tab_bar)
        self.tabs.setMovable(True)
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().tabMoved.connect(lambda _from, _to: self._refresh_tab_titles())
        self.tabs.currentChanged.connect(self._on_current_tab_changed)
        self.tabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tabs.tabBar().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCentralWidget(self.tabs)
        self.settings_tab = SettingsTab()
        self.settings_tab.screens_changed.connect(self._on_settings_screens_changed)
        self.settings_tab.ndi_changed.connect(self._on_settings_ndi_changed)
        self.settings_tab.timer_defaults_changed.connect(self._on_timer_defaults_changed)
        self.settings_tab.apply_timer_defaults_requested.connect(self._apply_timer_defaults_to_all_tabs)
        self.settings_tab.language_changed.connect(self._on_language_changed)
        self.settings_dialog = QDialog(self)
        self.settings_dialog.setObjectName("settingsDialog")
        self.settings_dialog.setModal(False)
        self.settings_dialog.resize(980, 760)
        settings_layout = QVBoxLayout(self.settings_dialog)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.addWidget(self.settings_tab)
        apply_windows_title_bar_color(self.settings_dialog)
        self._build_about_dialog()

        self.add_tab_button = OffsetToolButton(text_y_offset=-2)
        self.add_tab_button.setText("+")
        self.add_tab_button.setObjectName("tabAddButton")
        self.add_tab_button.setFixedSize(34, 34)
        self.add_tab_button.clicked.connect(lambda _checked=False: self._add_workspace())
        self.tabs_tab_bar.set_add_button(self.add_tab_button, self.tabs)
        self.tab_add_reserve = QWidget()
        self.tab_add_reserve.setObjectName("tabAddReserve")
        self.tab_add_reserve.setFixedWidth(56)
        self.tabs.setCornerWidget(self.tab_add_reserve, Qt.Corner.TopRightCorner)

        self.presentation_window.escape_requested.connect(self.stop_outputs)
        self.teleprompter_window.escape_requested.connect(self.stop_outputs)
        self.retranslate()

    def _build_about_dialog(self) -> None:
        self.about_dialog = QDialog(self)
        self.about_dialog.setObjectName("aboutDialog")
        self.about_dialog.setModal(False)
        self.about_dialog.resize(520, 360)

        layout = QVBoxLayout(self.about_dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        self.about_title_label = QLabel()
        self.about_title_label.setObjectName("settingsHeader")
        layout.addWidget(self.about_title_label)

        self.about_subtitle_label = QLabel()
        self.about_subtitle_label.setObjectName("settingsSubheader")
        self.about_subtitle_label.setWordWrap(True)
        layout.addWidget(self.about_subtitle_label)

        self.about_info_label = QLabel()
        self.about_info_label.setObjectName("sectionTitleLabel")
        self.about_info_label.setWordWrap(True)
        layout.addWidget(self.about_info_label)

        self.about_tech_label = QLabel()
        self.about_tech_label.setObjectName("settingsHint")
        self.about_tech_label.setWordWrap(True)
        layout.addWidget(self.about_tech_label)
        layout.addStretch(1)

        self.about_close_button = QPushButton()
        self.about_close_button.setObjectName("primaryUtilityButton")
        self.about_close_button.clicked.connect(self.about_dialog.close)
        layout.addWidget(self.about_close_button)
        apply_windows_title_bar_color(self.about_dialog)

    def _create_output_status_icon(self, tooltip: str, kind: str) -> QLabel:
        icon = QLabel("")
        icon.setObjectName("outputStatusIcon")
        icon.setProperty("kind", kind)
        icon.setProperty("status", "off")
        icon.setToolTip(tooltip)
        icon.setFixedSize(24, 20)
        icon.setPixmap(make_output_status_icon(kind, output_status_icon_color("off")))
        return icon

    @staticmethod
    def _set_output_status_icon(icon: QLabel, status: str, tooltip: str | None = None) -> None:
        icon.setProperty("status", status)
        if tooltip is not None:
            icon.setToolTip(tooltip)
        icon.setPixmap(make_output_status_icon(str(icon.property("kind")), output_status_icon_color(status)))
        icon.style().unpolish(icon)
        icon.style().polish(icon)
        icon.update()

    def _apply_theme(self) -> None:
        self.setStyleSheet(main_window_stylesheet())
        self.settings_dialog.setStyleSheet(settings_stylesheet())
        self.about_dialog.setStyleSheet(settings_stylesheet())
        self._refresh_transport_icons()

    def _refresh_transport_icons(self) -> None:
        self._play_icon = make_play_icon(transport_icon_color(False))
        self._play_ready_icon = make_play_icon(transport_icon_color(True))

    def retranslate(self) -> None:
        self.open_button.setText(tr("open_pdf"))
        self.settings_button.setText(tr("app.settings"))
        self.about_button.setText(tr("app.about"))
        self.settings_dialog.setWindowTitle(tr("app.settings"))
        self.about_dialog.setWindowTitle(tr("about.title"))
        self.about_title_label.setText(tr("about.title"))
        self.about_subtitle_label.setText(tr("about.subtitle"))
        self.about_info_label.setText(tr("about.info", version=APP_VERSION))
        self.about_tech_label.setText(tr("about.tech"))
        self.about_close_button.setText(tr("about.close"))
        self.presentation_status_icon.setToolTip(tr("status.main_screen"))
        self.teleprompter_status_icon.setToolTip(tr("status.teleprompter"))
        self.ndi_status_icon.setToolTip(tr("status.ndi"))
        self.toolbar_switch_output_button.setText(tr("switch_tab"))
        self.settings_tab.retranslate()
        self.teleprompter_window.retranslate()
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if isinstance(widget, DeckWorkspace):
                widget.retranslate()
        self._refresh_tab_titles()
        self._refresh_ndi_status()
        self._update_transport_state()

    def open_pdf(self) -> None:
        workspace = self.current_workspace()
        if workspace is not None and workspace is self._presenting_workspace:
            QMessageBox.warning(
                self,
                tr("dialog.live_tab_locked.title"),
                tr("dialog.live_tab_locked.body"),
            )
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("dialog.choose_pdf"),
            str(Path.home()),
            "PDF files (*.pdf)",
        )
        if not path:
            return
        pdf_path = Path(path)
        workspace = self.current_workspace()
        if workspace is None:
            self._add_workspace(pdf_path)
            return
        workspace.load_pdf(pdf_path)
        self._update_transport_state()

    def _add_workspace(self, path: Path | None = None) -> None:
        workspace = DeckWorkspace(path, QApplication.screens())
        workspace.outputs_changed.connect(lambda ws=workspace: self._workspace_outputs_changed(ws))
        workspace.timer_defaults_requested.connect(lambda ws=workspace: self._apply_timer_defaults_to_workspace(ws))
        workspace.state_changed.connect(self._update_transport_state)
        workspace.title_changed.connect(lambda title, ws=workspace: self._rename_workspace_tab(ws, title))

        index = self.tabs.addTab(workspace, workspace.title)
        self._install_tab_close_button(workspace)
        self.tabs.setCurrentIndex(index)
        workspace.set_timer_defaults(*self.settings_tab.timer_defaults())
        self._refresh_ndi_status()
        self._update_transport_state()

    def _open_settings_dialog(self) -> None:
        self.settings_dialog.show()
        apply_windows_title_bar_color(self.settings_dialog)
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def _open_about_dialog(self) -> None:
        self.about_dialog.show()
        apply_windows_title_bar_color(self.about_dialog)
        self.about_dialog.raise_()
        self.about_dialog.activateWindow()

    def _rename_workspace_tab(self, workspace: DeckWorkspace, title: str) -> None:
        self._refresh_tab_titles()

    def _install_tab_close_button(self, workspace: DeckWorkspace) -> None:
        index = self.tabs.indexOf(workspace)
        if index < 0:
            return
        close_container = QWidget()
        close_container.setObjectName("tabCloseContainer")
        close_container.setFixedSize(self._TAB_CLOSE_BUTTON_AREA_WIDTH, self._TAB_CLOSE_BUTTON_SIZE + 6)
        close_layout = QHBoxLayout(close_container)
        close_layout.setContentsMargins(self._TAB_CLOSE_BUTTON_OFFSET, 2, 0, 2)
        close_layout.setSpacing(0)
        close_button = OffsetToolButton(text_y_offset=-1)
        close_button.setText("×")
        close_button.setObjectName("tabCloseButton")
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setAutoRaise(True)
        close_button.setFixedSize(self._TAB_CLOSE_BUTTON_SIZE, self._TAB_CLOSE_BUTTON_SIZE)
        close_button.clicked.connect(lambda: self._close_workspace(workspace))
        close_layout.addWidget(close_button)
        self.tabs.tabBar().setTabButton(index, self.tabs.tabBar().ButtonPosition.RightSide, close_container)
        self._refresh_tab_titles()

    def _close_workspace(self, workspace: DeckWorkspace) -> None:
        index = self.tabs.indexOf(workspace)
        if index < 0:
            return

        if workspace is self._presenting_workspace:
            self.stop_outputs()

        workspace.close_backend()
        self.tabs.removeTab(index)
        workspace.deleteLater()
        if self.tabs.count() == 0:
            self._add_workspace()
        self._update_transport_state()

    def current_workspace(self) -> DeckWorkspace | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, DeckWorkspace) else None

    def _refresh_screen_choices(self) -> None:
        self.settings_tab.refresh_screen_choices(QApplication.screens())
        self._update_transport_state()

    def _selected_output_screens(self) -> tuple[bool, bool]:
        screens = QApplication.screens()
        presentation_index = self.settings_tab.presentation_screen_index()
        teleprompter_index = self.settings_tab.teleprompter_screen_index()
        return (
            presentation_index is not None and presentation_index < len(screens),
            teleprompter_index is not None and teleprompter_index < len(screens),
        )

    def _toggle_outputs(self) -> None:
        if self._presenting_workspace is not None:
            self.stop_outputs()
            return
        self.start_outputs()

    def start_outputs(self) -> None:
        workspace = self.current_workspace()
        if workspace is None or not workspace.has_document:
            QMessageBox.information(self, tr("dialog.no_document.title"), tr("dialog.no_document.body"))
            return

        screens = QApplication.screens()
        presentation_index = self.settings_tab.presentation_screen_index()
        teleprompter_index = self.settings_tab.teleprompter_screen_index()
        has_presentation, has_teleprompter = self._selected_output_screens()

        if has_presentation:
            self._show_fullscreen_on_screen(self.presentation_window, screens[presentation_index])
        else:
            self.presentation_window.hide()
        if has_teleprompter:
            self._show_fullscreen_on_screen(self.teleprompter_window, screens[teleprompter_index])
        else:
            self.teleprompter_window.hide()

        self._presenting_workspace = workspace
        self._apply_ndi_settings(notify=True)
        self._refresh_outputs()
        self._update_transport_state()

    def _switch_output_to_current_tab(self) -> None:
        workspace = self.current_workspace()
        if workspace is None or not workspace.has_document:
            return
        if workspace is self._presenting_workspace:
            return

        screens = QApplication.screens()
        presentation_index = self.settings_tab.presentation_screen_index()
        teleprompter_index = self.settings_tab.teleprompter_screen_index()
        has_presentation, has_teleprompter = self._selected_output_screens()

        if has_presentation:
            self._show_fullscreen_on_screen(self.presentation_window, screens[presentation_index])
        else:
            self.presentation_window.hide()
        if has_teleprompter:
            self._show_fullscreen_on_screen(self.teleprompter_window, screens[teleprompter_index])
        else:
            self.teleprompter_window.hide()

        self._presenting_workspace = workspace
        self._apply_ndi_settings(notify=True)
        self._refresh_outputs()
        self._update_transport_state()

    def stop_outputs(self) -> None:
        self.presentation_window.hide()
        self.teleprompter_window.hide()
        self.ndi_controller.stop()
        self._ndi_frame_note = ""
        self._ndi_status = NdiApplyResult(
            requested=False,
            available=self.ndi_controller.library.available,
            active_names=[],
            message=tr("ndi.off_app"),
        )
        self._presenting_workspace = None
        self._refresh_ndi_status()
        self._update_transport_state()

    def _workspace_outputs_changed(self, workspace: DeckWorkspace) -> None:
        if workspace is self._presenting_workspace:
            self._refresh_outputs()
        self._update_transport_state()

    def _on_settings_screens_changed(self) -> None:
        self._update_transport_state()
        if self._presenting_workspace is None:
            return
        screens = QApplication.screens()
        presentation_index = self.settings_tab.presentation_screen_index()
        teleprompter_index = self.settings_tab.teleprompter_screen_index()
        if presentation_index is not None and presentation_index < len(screens):
            self._show_fullscreen_on_screen(self.presentation_window, screens[presentation_index])
        else:
            self.presentation_window.hide()
        if teleprompter_index is not None and teleprompter_index < len(screens):
            self._show_fullscreen_on_screen(self.teleprompter_window, screens[teleprompter_index])
        else:
            self.teleprompter_window.hide()
        self._refresh_outputs()

    def _on_settings_ndi_changed(self) -> None:
        self._apply_ndi_settings()
        if self._presenting_workspace is not None:
            self._refresh_outputs()
        self._update_transport_state()

    def _on_language_changed(self, value: str) -> None:
        set_language(value)
        self.settings_tab.retranslate()
        self._refresh_screen_choices()
        self._apply_ndi_settings()
        self.retranslate()

    def _on_timer_defaults_changed(self) -> None:
        self._update_transport_state()

    def _apply_timer_defaults_to_workspace(self, workspace: DeckWorkspace) -> None:
        workspace.set_timer_defaults(*self.settings_tab.timer_defaults())
        if workspace is self._presenting_workspace:
            self._refresh_outputs()

    def _apply_timer_defaults_to_all_tabs(self) -> None:
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if isinstance(widget, DeckWorkspace):
                widget.set_timer_defaults(*self.settings_tab.timer_defaults())
        if self._presenting_workspace is not None:
            self._refresh_outputs()

    def _apply_ndi_settings(self, *, notify: bool = False) -> None:
        config = self.settings_tab.ndi_config()
        requested = bool(config["main_name"] or config["teleprompter_name"])

        if self._presenting_workspace is None:
            self.ndi_controller.stop()
            self._ndi_status = NdiApplyResult(
                requested=requested,
                available=self.ndi_controller.library.available,
                active_names=[],
                message=(
                    tr("ndi.ready")
                    if requested and self.ndi_controller.library.available
                    else (
                        self.ndi_controller.library.status_text
                        if requested
                        else tr("ndi.off_app")
                    )
                ),
            )
            self._refresh_ndi_status()
            return

        self._ndi_status = self.ndi_controller.apply(
            main_name=config["main_name"],
            teleprompter_name=config["teleprompter_name"],
        )
        self._refresh_ndi_status()
        if notify and self._ndi_status.warning:
            QMessageBox.warning(self, "NDI", self._ndi_status.warning)

    def _refresh_ndi_status(self) -> None:
        tone = "ok" if self._ndi_status.available and (self._ndi_status.active_names or self._ndi_status.requested) else "error"
        if not self._ndi_status.requested:
            tone = "muted"
        status_text = self._ndi_status.message
        if tone == "ok" and self._ndi_status.active_names:
            source_names = " + ".join(self._compact_ndi_source_name(name) for name in self._ndi_status.active_names)
            status_text = tr("ndi.live", sources=source_names)
            if self._ndi_frame_note:
                status_text = f"{status_text}\n{self._ndi_frame_note}"
        self.settings_tab.set_ndi_status(status_text, tone=tone)

    @staticmethod
    def _compact_ndi_source_name(name: str) -> str:
        return name.removeprefix("PDFBread ").strip() or name

    @staticmethod
    def _physical_size_for_widget(widget: QWidget, fallback: tuple[int, int]) -> tuple[int, int]:
        width = max(widget.width(), 0)
        height = max(widget.height(), 0)

        handle = widget.windowHandle()
        screen = handle.screen() if handle is not None else None
        if screen is None:
            screen = widget.screen()

        if screen is not None:
            geometry = screen.geometry()
            width = max(width, geometry.width())
            height = max(height, geometry.height())

        if width <= 0 or height <= 0:
            width, height = fallback

        device_pixel_ratio = screen.devicePixelRatio() if screen is not None else 1.0
        return (
            max(1, int(round(width * device_pixel_ratio))),
            max(1, int(round(height * device_pixel_ratio))),
        )

    def _frame_render_sizes(self) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]]:
        presentation_size = self._physical_size_for_widget(self.presentation_window, (1920, 1080))
        teleprompter_size = self._physical_size_for_widget(self.teleprompter_window, (1920, 1080))

        current_render_size = (
            max(2600, presentation_size[0] * self._NDI_SUPERSAMPLE_FACTOR),
            max(1800, presentation_size[1] * self._NDI_SUPERSAMPLE_FACTOR),
        )
        next_render_size = (
            max(1400, teleprompter_size[0] * self._NDI_SUPERSAMPLE_FACTOR // 2),
            max(1000, max(1, teleprompter_size[1] - 160) * self._NDI_SUPERSAMPLE_FACTOR),
        )
        return presentation_size, teleprompter_size, current_render_size, next_render_size

    def _refresh_outputs(self) -> None:
        if self._presenting_workspace is None:
            return

        presentation_size, teleprompter_size, current_render_size, next_render_size = self._frame_render_sizes()
        payload = self._presenting_workspace.output_payload(
            current_size=current_render_size,
            next_size=next_render_size,
        )
        if payload is None:
            return

        self.presentation_window.show_page(payload["current_pixmap"])  # type: ignore[arg-type]
        teleprompter_mirror = self.settings_tab.teleprompter_mode() == "mirror"
        if teleprompter_mirror:
            self.teleprompter_window.show_duplicate(payload["current_pixmap"])  # type: ignore[arg-type]
        else:
            self.teleprompter_window.update_content(
                next_pixmap=payload["next_pixmap"],  # type: ignore[arg-type]
                current_pixmap=payload["current_pixmap"],  # type: ignore[arg-type]
                page_index=payload["page_index"],  # type: ignore[arg-type]
                page_count=payload["page_count"],  # type: ignore[arg-type]
                remaining_text=payload["remaining_text"],  # type: ignore[arg-type]
            )
        if self.ndi_controller.has_active_outputs:
            main_image = (
                render_presentation_frame(
                    payload["current_pixmap"],  # type: ignore[arg-type]
                    width=presentation_size[0],
                    height=presentation_size[1],
                )
                if self.ndi_controller.main_sender.active
                else None
            )
            teleprompter_image = (
                (
                    render_presentation_frame(
                        payload["current_pixmap"],  # type: ignore[arg-type]
                        width=teleprompter_size[0],
                        height=teleprompter_size[1],
                    )
                    if teleprompter_mirror
                    else render_teleprompter_frame(
                        next_pixmap=payload["next_pixmap"],  # type: ignore[arg-type]
                        current_pixmap=payload["current_pixmap"],  # type: ignore[arg-type]
                        page_index=payload["page_index"],  # type: ignore[arg-type]
                        page_count=payload["page_count"],  # type: ignore[arg-type]
                        remaining_text=payload["remaining_text"],  # type: ignore[arg-type]
                        width=teleprompter_size[0],
                        height=teleprompter_size[1],
                    )
                )
                if self.ndi_controller.teleprompter_sender.active
                else None
            )
            frame_notes: list[str] = []
            if main_image is not None:
                frame_notes.append(f"Main: {main_image.width()}x{main_image.height()}")
            if teleprompter_image is not None:
                frame_notes.append(f"Teleprompter: {teleprompter_image.width()}x{teleprompter_image.height()}")
            self._ndi_frame_note = "  |  ".join(frame_notes)
            self._refresh_ndi_status()
            self.ndi_controller.send(main_image=main_image, teleprompter_image=teleprompter_image)

    def _update_transport_state(self) -> None:
        if not hasattr(self, "toolbar_switch_output_button"):
            return
        current = self.current_workspace()
        can_start = current is not None and current.has_document
        is_running = self._presenting_workspace is not None
        can_switch = (
            is_running
            and current is not None
            and current.has_document
            and current is not self._presenting_workspace
        )
        presentation_hidden = is_running and not self.presentation_window.isVisible()
        teleprompter_hidden = is_running and not self.teleprompter_window.isVisible()
        presentation_status = "active" if is_running and not presentation_hidden else ("error" if is_running else "off")
        teleprompter_status = "active" if is_running and not teleprompter_hidden else ("error" if is_running else "off")
        ndi_status = "active" if is_running and self.ndi_controller.has_active_outputs else ("error" if is_running else "off")
        self._set_output_status_icon(
            self.presentation_status_icon,
            presentation_status,
            self._output_status_tooltip("main", presentation_status),
        )
        self._set_output_status_icon(
            self.teleprompter_status_icon,
            teleprompter_status,
            self._output_status_tooltip("teleprompter", teleprompter_status),
        )
        self._set_output_status_icon(
            self.ndi_status_icon,
            ndi_status,
            self._output_status_tooltip("ndi", ndi_status, self._ndi_status.message),
        )

        self.transport_toolbar_button.setEnabled(can_start or is_running)
        if is_running:
            self.transport_toolbar_button.setText("")
            self.transport_toolbar_button.setIcon(self._stop_icon)
            self.transport_toolbar_button.setStyleSheet(transport_button_style(True))
            self.transport_toolbar_button.setToolTip(tr("transport.running"))
        else:
            self.transport_toolbar_button.setText("")
            self.transport_toolbar_button.setIcon(self._play_ready_icon if can_start else self._play_icon)
            self.transport_toolbar_button.setStyleSheet(transport_button_style(False, can_start))
            self.transport_toolbar_button.setToolTip(tr("transport.ready") if can_start else tr("transport.disabled"))

        self.toolbar_switch_output_button.setText(tr("switch_tab"))
        self.toolbar_switch_output_button.setVisible(is_running)
        self.toolbar_switch_output_button.setEnabled(can_switch)

        self._refresh_tab_titles()
        self._refresh_workspace_output_states()
        self._update_status_strip()

    @staticmethod
    def _output_status_tooltip(kind: str, status: str, details: str = "") -> str:
        text = tr(f"status.{kind}.{status}")
        return f"{text}\n{details}" if details else text

    def _refresh_workspace_output_states(self) -> None:
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if isinstance(widget, DeckWorkspace):
                widget.set_output_active(widget is self._presenting_workspace)

    def _on_current_tab_changed(self, _index: int) -> None:
        self.tabs_tab_bar._reposition_add_button()
        self._update_transport_state()

    def _refresh_tab_titles(self) -> None:
        presenting_index = -1
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if not isinstance(widget, DeckWorkspace):
                continue
            title = widget.title
            if widget is self._presenting_workspace:
                presenting_index = index
                title = f"{title} | {tr('on_air')}"
            self.tabs.setTabText(index, title)
        self.tabs_tab_bar.set_presenting_index(presenting_index)

    def _update_status_strip(self) -> None:
        workspace = self.current_workspace()
        if workspace is None:
            self.toolbar_file_label.setText(tr("empty_tab"))
            self.toolbar_slide_label.setText(tr("slide_dash"))
            return

        title = workspace.status_title_text()
        if workspace is self._presenting_workspace:
            title = f"{title} | {tr('in_air')}"
        self.toolbar_file_label.setText(title)
        self.toolbar_slide_label.setText(workspace.current_slide_text())

    def _show_fullscreen_on_screen(self, widget: QWidget, screen) -> None:
        geometry = screen.availableGeometry()
        handle = widget.windowHandle()
        if handle is None:
            widget.winId()
            handle = widget.windowHandle()
        if handle is not None:
            handle.setScreen(screen)
        widget.setGeometry(geometry)
        widget.showFullScreen()

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        self.stop_outputs()
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if isinstance(widget, DeckWorkspace):
                widget.close_backend()
        self.ndi_controller.shutdown()
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        workspace = self.current_workspace()
        if workspace is None:
            super().keyPressEvent(event)
            return

        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_PageDown, Qt.Key.Key_Space):
            workspace.next_slide()
            event.accept()
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_PageUp, Qt.Key.Key_Backspace):
            workspace.previous_slide()
            event.accept()
            return
        super().keyPressEvent(event)


def run() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("PDFBread")
    icon = load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    window = MainWindow()
    window.show()
    return app.exec()


def make_play_icon(color: str) -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))

        left = max(3, size // 5)
        top = max(3, size // 6)
        right = size - max(2, size // 6)
        bottom = size - top
        painter.drawPolygon(
            QPolygon(
                [
                    QPoint(left, top),
                    QPoint(right, size // 2),
                    QPoint(left, bottom),
                ]
            )
        )
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def make_output_status_icon(kind: str, color: str) -> QPixmap:
    pixmap = QPixmap(24, 20)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color), 2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if kind == "monitor":
        painter.drawRoundedRect(QRect(4, 4, 16, 10), 2, 2)
        painter.drawLine(12, 14, 12, 16)
        painter.drawLine(8, 17, 16, 17)
    elif kind == "prompter":
        painter.drawPolygon(QPolygon([QPoint(5, 5), QPoint(19, 5), QPoint(17, 14), QPoint(7, 14)]))
        painter.drawLine(9, 16, 15, 16)
        painter.drawLine(12, 14, 12, 17)
    else:
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPoint(12, 10), 2, 2)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRect(7, 5, 10, 10), 135 * 16, 90 * 16)
        painter.drawArc(QRect(7, 5, 10, 10), -45 * 16, 90 * 16)
        painter.drawArc(QRect(4, 2, 16, 16), 135 * 16, 90 * 16)
        painter.drawArc(QRect(4, 2, 16, 16), -45 * 16, 90 * 16)

    painter.end()
    return pixmap


def load_app_icon() -> QIcon:
    icon_path = app_resource("icon.png")
    if not icon_path.exists():
        return QIcon()
    source = QPixmap(str(icon_path))
    if source.isNull():
        return QIcon()

    icon = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        icon.addPixmap(
            source.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
    return icon
