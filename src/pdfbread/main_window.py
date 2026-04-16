from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeyEvent, QPainter, QPixmap
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
    QStylePainter,
    QTabBar,
    QTabWidget,
    QToolButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pdfbread.ndi_output import NdiApplyResult, NdiOutputController
from pdfbread.paths import app_resource
from pdfbread.presentation_window import PresentationWindow, render_presentation_frame
from pdfbread.settings_tab import SettingsTab
from pdfbread.teleprompter_window import TeleprompterWindow, render_teleprompter_frame
from pdfbread.workspace import DeckWorkspace


class CleanTabBar(QTabBar):
    def __init__(self) -> None:
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setDrawBase(False)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QStylePainter(self)
        option = QStyleOptionTab()
        for index in range(self.count()):
            self.initStyleOption(option, index)
            option.state &= ~QStyle.StateFlag.State_HasFocus
            painter.drawControl(QStyle.ControlElement.CE_TabBarTabShape, option)
            painter.drawControl(QStyle.ControlElement.CE_TabBarTabLabel, option)


class MainWindow(QMainWindow):
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
        self._ndi_status = NdiApplyResult(
            requested=False,
            available=self.ndi_controller.library.available,
            active_names=[],
            message="NDI выключен для этой вкладки.",
        )
        if not app_icon.isNull():
            self.presentation_window.setWindowIcon(app_icon)
            self.teleprompter_window.setWindowIcon(app_icon)
        self._presenting_workspace: DeckWorkspace | None = None

        self._build_ui()
        self._apply_theme()
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

        self.open_action = QAction("Открыть PDF", self)
        self.open_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.open_action.triggered.connect(self.open_pdf)
        toolbar.addAction(self.open_action)

        self.settings_button = QPushButton("Настройки")
        self.settings_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.settings_button.setObjectName("secondaryToolbarButton")
        self.settings_button.clicked.connect(self._open_settings_dialog)
        toolbar.addWidget(self.settings_button)

        self.toolbar_status = QWidget()
        self.toolbar_status_layout = QHBoxLayout(self.toolbar_status)
        self.toolbar_status_layout.setContentsMargins(10, 0, 10, 0)
        self.toolbar_status_layout.setSpacing(8)

        self.toolbar_file_label = QLabel("Пустая вкладка")
        self.toolbar_file_label.setObjectName("toolbarFilePill")
        self.toolbar_slide_label = QLabel("Слайд -")
        self.toolbar_slide_label.setObjectName("toolbarSlidePill")
        self.toolbar_status_layout.addWidget(self.toolbar_file_label)
        self.toolbar_status_layout.addWidget(self.toolbar_slide_label)
        toolbar.addWidget(self.toolbar_status)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        self._play_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        self._stop_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
        self.transport_toolbar_button = QPushButton("Запуск")
        self.transport_toolbar_button.setIcon(self._play_icon)
        self.transport_toolbar_button.setObjectName("transportButton")
        self.transport_toolbar_button.clicked.connect(self._toggle_outputs)
        toolbar.addWidget(self.transport_toolbar_button)

        self.tabs = QTabWidget()
        self.tabs.setTabBar(CleanTabBar())
        self.tabs.setMovable(True)
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.currentChanged.connect(self._on_current_tab_changed)
        self.tabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tabs.tabBar().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCentralWidget(self.tabs)
        self.settings_tab = SettingsTab()
        self.settings_tab.screens_changed.connect(self._on_settings_screens_changed)
        self.settings_tab.ndi_changed.connect(self._on_settings_ndi_changed)
        self.settings_tab.timer_defaults_changed.connect(self._on_timer_defaults_changed)
        self.settings_tab.apply_timer_defaults_requested.connect(self._apply_timer_defaults_to_all_tabs)
        self.settings_dialog = QDialog(self)
        self.settings_dialog.setWindowTitle("Настройки")
        self.settings_dialog.setModal(False)
        self.settings_dialog.resize(980, 760)
        settings_layout = QVBoxLayout(self.settings_dialog)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.addWidget(self.settings_tab)

        self.tabs_corner = QWidget()
        self.tabs_corner_layout = QHBoxLayout(self.tabs_corner)
        self.tabs_corner_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs_corner_layout.setSpacing(8)

        self.switch_tab_output_button = QPushButton("Вывести вкладку")
        self.switch_tab_output_button.setObjectName("switchOutputButton")
        self.switch_tab_output_button.clicked.connect(self._switch_output_to_current_tab)
        self.switch_tab_output_button.hide()
        self.tabs_corner_layout.addWidget(self.switch_tab_output_button)

        self.add_tab_button = QToolButton()
        self.add_tab_button.setText("+")
        self.add_tab_button.setObjectName("tabAddButton")
        self.add_tab_button.clicked.connect(lambda _checked=False: self._add_workspace())
        self.tabs_corner_layout.addWidget(self.add_tab_button)
        self.tabs.setCornerWidget(self.tabs_corner, Qt.Corner.TopRightCorner)

        self.presentation_window.escape_requested.connect(self.stop_outputs)
        self.teleprompter_window.escape_requested.connect(self.stop_outputs)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #030504;
                color: #F5F8F6;
                font-size: 14px;
            }
            QToolBar {
                background: #060908;
                border: none;
                spacing: 10px;
                padding: 10px 14px;
            }
            QLabel#toolbarFilePill, QLabel#toolbarSlidePill {
                background: #09110C;
                color: #D9F2DF;
                border: 1px solid #183223;
                border-radius: 12px;
                padding: 8px 12px;
            }
            QLabel#toolbarFilePill {
                min-width: 280px;
                font-weight: 600;
            }
            QLabel#toolbarSlidePill {
                color: #7CE494;
                font-weight: 700;
            }
            QToolButton, QPushButton {
                background: #0A0F0C;
                color: #F5F8F6;
                border: 1px solid #1D3B26;
                border-radius: 12px;
                padding: 9px 14px;
            }
            QToolButton:hover, QPushButton:hover {
                border-color: #38B35A;
                background: #0F1712;
            }
            QPushButton#transportButton {
                background: #169A42;
                border-color: #2EC65B;
                color: #FFFFFF;
                font-weight: 700;
                min-width: 112px;
            }
            QPushButton#transportButton:hover {
                background: #1CAF4B;
            }
            QPushButton#switchOutputButton {
                background: #0B1710;
                color: #A8F0B8;
                border: 1px solid #2F9C4D;
                border-radius: 12px;
                padding: 8px 14px;
                font-weight: 700;
            }
            QPushButton#switchOutputButton:hover {
                background: #13241A;
            }
            QPushButton#secondaryToolbarButton {
                background: #0A0F0C;
                color: #E8F4EB;
                border: 1px solid #1D3B26;
                border-radius: 12px;
                padding: 9px 14px;
            }
            QPushButton#secondaryToolbarButton:hover {
                border-color: #38B35A;
                background: #0F1712;
            }
            QTabWidget::pane {
                border: 1px solid #122318;
                border-radius: 16px;
                top: -2px;
                background: #040706;
            }
            QTabBar::tab {
                background: #07100B;
                color: #A8B7AE;
                border: 1px solid #16301F;
                padding: 11px 14px;
                margin-right: 8px;
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                min-width: 180px;
                max-width: 260px;
            }
            QTabBar::tab:selected {
                background: #0F1D15;
                color: #FFFFFF;
                border-color: #32B456;
            }
            QTabBar::tab:focus {
                outline: none;
            }
            QToolButton#tabAddButton {
                background: #0D1710;
                color: #46D96D;
                border: 1px solid #246F38;
                border-radius: 12px;
                padding: 5px 12px;
                font-size: 20px;
                font-weight: 700;
            }
            QToolButton#tabAddButton:hover {
                background: #14301B;
            }
            QToolButton#tabCloseButton {
                background: #101512;
                color: #7DE792;
                border: 1px solid #206F34;
                border-radius: 9px;
                min-width: 16px;
                max-width: 16px;
                min-height: 16px;
                max-height: 16px;
                padding: 0px;
                margin-left: 6px;
                font-size: 11px;
                font-weight: 700;
            }
            QToolButton#tabCloseButton:hover {
                background: #8F1F1F;
                color: #FFFFFF;
                border-color: #C63A3A;
            }
            """
        )

    def open_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите PDF",
            str(Path.home()),
            "PDF files (*.pdf)",
        )
        if not path:
            return
        workspace = self.current_workspace()
        if workspace is None:
            self._add_workspace(Path(path))
            return
        workspace.load_pdf(Path(path))
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
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def _rename_workspace_tab(self, workspace: DeckWorkspace, title: str) -> None:
        self._refresh_tab_titles()

    def _install_tab_close_button(self, workspace: DeckWorkspace) -> None:
        index = self.tabs.indexOf(workspace)
        if index < 0:
            return
        close_button = QToolButton()
        close_button.setText("×")
        close_button.setObjectName("tabCloseButton")
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setAutoRaise(True)
        close_button.setFixedSize(16, 16)
        close_button.clicked.connect(lambda: self._close_workspace(workspace))
        self.tabs.tabBar().setTabButton(index, self.tabs.tabBar().ButtonPosition.RightSide, close_button)
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

    def _toggle_outputs(self) -> None:
        if self._presenting_workspace is not None:
            self.stop_outputs()
            return
        self.start_outputs()

    def start_outputs(self) -> None:
        workspace = self.current_workspace()
        if workspace is None or not workspace.has_document:
            QMessageBox.information(self, "Нет документа", "Сначала откройте PDF-файл.")
            return

        screens = QApplication.screens()
        presentation_index = self.settings_tab.presentation_screen_index()
        teleprompter_index = self.settings_tab.teleprompter_screen_index()

        if presentation_index is None or presentation_index >= len(screens):
            QMessageBox.warning(self, "Экран недоступен", "Выберите экран для главного показа.")
            return

        self._show_fullscreen_on_screen(self.presentation_window, screens[presentation_index])
        if teleprompter_index is not None and teleprompter_index < len(screens):
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

        if presentation_index is None or presentation_index >= len(screens):
            QMessageBox.warning(self, "Экран недоступен", "Выберите экран для главного показа.")
            return

        self._show_fullscreen_on_screen(self.presentation_window, screens[presentation_index])
        if teleprompter_index is not None and teleprompter_index < len(screens):
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
        self._ndi_status = NdiApplyResult(
            requested=False,
            available=self.ndi_controller.library.available,
            active_names=[],
            message="NDI выключен для всего приложения.",
        )
        self._presenting_workspace = None
        self._refresh_ndi_status()
        self._update_transport_state()

    def _workspace_outputs_changed(self, workspace: DeckWorkspace) -> None:
        if workspace is self._presenting_workspace:
            self._refresh_outputs()
        self._update_transport_state()

    def _on_settings_screens_changed(self) -> None:
        if self._presenting_workspace is None:
            return
        screens = QApplication.screens()
        presentation_index = self.settings_tab.presentation_screen_index()
        teleprompter_index = self.settings_tab.teleprompter_screen_index()
        if presentation_index is not None and presentation_index < len(screens):
            self._show_fullscreen_on_screen(self.presentation_window, screens[presentation_index])
        if teleprompter_index is not None and teleprompter_index < len(screens):
            self._show_fullscreen_on_screen(self.teleprompter_window, screens[teleprompter_index])
        else:
            self.teleprompter_window.hide()

    def _on_settings_ndi_changed(self) -> None:
        self._apply_ndi_settings()
        if self._presenting_workspace is not None:
            self._refresh_outputs()

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
                    "NDI готов. Источники появятся после запуска показа."
                    if requested and self.ndi_controller.library.available
                    else (
                        self.ndi_controller.library.status_text
                        if requested
                        else "NDI выключен для всего приложения."
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
        self.settings_tab.set_ndi_status(self._ndi_status.message, tone=tone)

    def _refresh_outputs(self) -> None:
        if self._presenting_workspace is None:
            return

        payload = self._presenting_workspace.output_payload()
        if payload is None:
            return

        self.presentation_window.show_page(payload["current_pixmap"])  # type: ignore[arg-type]
        self.teleprompter_window.update_content(
            next_pixmap=payload["next_pixmap"],  # type: ignore[arg-type]
            current_pixmap=payload["current_pixmap"],  # type: ignore[arg-type]
            page_index=payload["page_index"],  # type: ignore[arg-type]
            page_count=payload["page_count"],  # type: ignore[arg-type]
            remaining_text=payload["remaining_text"],  # type: ignore[arg-type]
        )
        if self.ndi_controller.has_active_outputs:
            main_image = (
                render_presentation_frame(payload["current_pixmap"])  # type: ignore[arg-type]
                if self.ndi_controller.main_sender.active
                else None
            )
            teleprompter_image = (
                render_teleprompter_frame(
                    next_pixmap=payload["next_pixmap"],  # type: ignore[arg-type]
                    current_pixmap=payload["current_pixmap"],  # type: ignore[arg-type]
                    page_index=payload["page_index"],  # type: ignore[arg-type]
                    page_count=payload["page_count"],  # type: ignore[arg-type]
                    remaining_text=payload["remaining_text"],  # type: ignore[arg-type]
                )
                if self.ndi_controller.teleprompter_sender.active
                else None
            )
            self.ndi_controller.send(main_image=main_image, teleprompter_image=teleprompter_image)

    def _update_transport_state(self) -> None:
        if not hasattr(self, "switch_tab_output_button"):
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

        self.transport_toolbar_button.setEnabled(can_start or is_running)
        if is_running:
            self.transport_toolbar_button.setText("Стоп")
            self.transport_toolbar_button.setIcon(self._stop_icon)
            self.transport_toolbar_button.setStyleSheet(
                "background:#8F1F1F; color:#FFFFFF; border:1px solid #C63A3A; border-radius:10px; padding:8px 12px; font-weight:700;"
            )
        else:
            self.transport_toolbar_button.setText("Запуск")
            self.transport_toolbar_button.setIcon(self._play_icon)
            self.transport_toolbar_button.setStyleSheet(
                "background:#15913B; color:#FFFFFF; border:1px solid #22B04A; border-radius:10px; padding:8px 12px; font-weight:700;"
            )

        self.switch_tab_output_button.setVisible(is_running)
        if not is_running:
            self.switch_tab_output_button.setText("Вывести вкладку")
            self.switch_tab_output_button.setEnabled(False)
        elif current is None or not current.has_document:
            self.switch_tab_output_button.setText("Нет PDF в табе")
            self.switch_tab_output_button.setEnabled(False)
        elif current is self._presenting_workspace:
            self.switch_tab_output_button.setText("Эта вкладка в эфире")
            self.switch_tab_output_button.setEnabled(False)
        else:
            self.switch_tab_output_button.setText("Вывести вкладку")
            self.switch_tab_output_button.setEnabled(can_switch)

        self._refresh_tab_titles()
        self._update_status_strip()

    def _on_current_tab_changed(self, _index: int) -> None:
        self._update_transport_state()

    def _refresh_tab_titles(self) -> None:
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if not isinstance(widget, DeckWorkspace):
                continue
            title = widget.title
            if widget is self._presenting_workspace:
                title = f"{title} | Эфир"
            self.tabs.setTabText(index, title)

    def _update_status_strip(self) -> None:
        workspace = self.current_workspace()
        if workspace is None:
            self.toolbar_file_label.setText("Пустая вкладка")
            self.toolbar_slide_label.setText("Слайд -")
            return

        title = workspace.status_title_text()
        if workspace is self._presenting_workspace:
            title = f"{title} | В эфире"
        self.toolbar_file_label.setText(title)
        self.toolbar_slide_label.setText(workspace.current_slide_text())

    def _show_fullscreen_on_screen(self, widget: QWidget, screen) -> None:
        geometry = screen.geometry()
        widget.setGeometry(geometry)
        widget.show()
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
