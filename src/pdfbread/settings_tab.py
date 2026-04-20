from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pdfbread.i18n import language, language_options, tr
from pdfbread.ui_theme import ndi_status_style, settings_stylesheet


class SettingsTab(QWidget):
    screens_changed = Signal()
    ndi_changed = Signal()
    timer_defaults_changed = Signal()
    apply_timer_defaults_requested = Signal()
    language_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("settingsRoot")
        self._build_ui()
        self._connect_signals()
        self._apply_theme()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        self.header_label = QLabel()
        self.header_label.setObjectName("settingsHeader")
        self.subheader_label = QLabel()
        self.subheader_label.setObjectName("settingsSubheader")
        self.subheader_label.setWordWrap(True)
        root.addWidget(self.header_label)
        root.addWidget(self.subheader_label)

        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        self.screen_group = QGroupBox()
        self.screen_group.setObjectName("screensGroup")
        screen_layout = QGridLayout(self.screen_group)
        self.screens_title_label = self._section_title("")
        screen_layout.addWidget(self.screens_title_label, 0, 0, 1, 2, Qt.AlignmentFlag.AlignTop)
        self.language_label = QLabel()
        self.language_combo = QComboBox()
        for code, label in language_options():
            self.language_combo.addItem(label, code)
        language_index = self.language_combo.findData(language())
        if language_index >= 0:
            self.language_combo.setCurrentIndex(language_index)
        self.presentation_screen_combo = QComboBox()
        self.teleprompter_screen_combo = QComboBox()
        self.teleprompter_mode_combo = QComboBox()
        self.teleprompter_mode_combo.addItem(tr("settings.teleprompter_mode_prompt"), "prompt")
        self.teleprompter_mode_combo.addItem(tr("settings.teleprompter_mode_mirror"), "mirror")
        self.presentation_screen_label = QLabel()
        self.teleprompter_screen_label = QLabel()
        self.teleprompter_mode_label = QLabel()
        screen_layout.addWidget(self.language_label, 1, 0)
        screen_layout.addWidget(self.language_combo, 1, 1)
        screen_layout.addWidget(self.presentation_screen_label, 2, 0)
        screen_layout.addWidget(self.presentation_screen_combo, 2, 1)
        screen_layout.addWidget(self.teleprompter_screen_label, 3, 0)
        screen_layout.addWidget(self.teleprompter_screen_combo, 3, 1)
        screen_layout.addWidget(self.teleprompter_mode_label, 4, 0)
        screen_layout.addWidget(self.teleprompter_mode_combo, 4, 1)
        top_row.addWidget(self.screen_group, 1)

        self.ndi_group = QGroupBox()
        self.ndi_group.setObjectName("ndiGroup")
        ndi_layout = QGridLayout(self.ndi_group)
        ndi_layout.setVerticalSpacing(10)
        self.ndi_title_label = self._section_title("NDI")
        ndi_layout.addWidget(self.ndi_title_label, 0, 0, 1, 2, Qt.AlignmentFlag.AlignTop)
        self.ndi_main_checkbox = QCheckBox()
        self.ndi_main_name = QLineEdit("PDFBread Main")
        self.ndi_teleprompter_checkbox = QCheckBox()
        self.ndi_teleprompter_name = QLineEdit("PDFBread Teleprompter")
        self.ndi_status_label = QLabel(tr("ndi.off_app"))
        self.ndi_status_label.setObjectName("ndiStatusLabel")
        self.ndi_status_label.setWordWrap(True)
        ndi_layout.addWidget(self.ndi_main_checkbox, 1, 0)
        ndi_layout.addWidget(self.ndi_main_name, 1, 1)
        ndi_layout.addWidget(self.ndi_teleprompter_checkbox, 2, 0)
        ndi_layout.addWidget(self.ndi_teleprompter_name, 2, 1)
        ndi_layout.addWidget(self.ndi_status_label, 3, 0, 1, 2)
        top_row.addWidget(self.ndi_group, 1)

        root.addLayout(top_row)

        self.timer_defaults_group = QGroupBox()
        self.timer_defaults_group.setObjectName("timerDefaultsGroup")
        timer_layout = QVBoxLayout(self.timer_defaults_group)
        self.timer_defaults_title_label = self._section_title("")
        timer_layout.addWidget(self.timer_defaults_title_label, 0, Qt.AlignmentFlag.AlignTop)

        self.timer_preview_label = QLabel("15:00")
        self.timer_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_preview_label.setObjectName("timerLabel")
        timer_layout.addWidget(self.timer_preview_label)
        self.timer_preview_progress = QProgressBar()
        self.timer_preview_progress.setObjectName("timerProgressBar")
        self.timer_preview_progress.setRange(0, 1000)
        self.timer_preview_progress.setValue(1000)
        self.timer_preview_progress.setTextVisible(False)
        timer_layout.addWidget(self.timer_preview_progress)

        duration_row = QHBoxLayout()
        duration_row.setSpacing(14)
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setObjectName("settingsTimerSpin")
        self.minutes_spin.setRange(0, 599)
        self.minutes_spin.setValue(15)
        self.seconds_spin = QSpinBox()
        self.seconds_spin.setObjectName("settingsTimerSpin")
        self.seconds_spin.setRange(0, 59)
        self.minutes_field, self.minutes_label = self._timer_field(self.minutes_spin)
        self.seconds_field, self.seconds_label = self._timer_field(self.seconds_spin)
        duration_row.addWidget(self.minutes_field)
        duration_row.addWidget(self.seconds_field)
        timer_layout.addLayout(duration_row)

        self.apply_to_all_button = QPushButton()
        self.apply_to_all_button.setObjectName("primaryUtilityButton")
        timer_layout.addWidget(self.apply_to_all_button)

        self.hint_label = QLabel()
        self.hint_label.setObjectName("settingsHint")
        self.hint_label.setWordWrap(True)
        timer_layout.addWidget(self.hint_label)
        root.addWidget(self.timer_defaults_group)

        root.addStretch(1)
        self.retranslate()

    @staticmethod
    def _section_title(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitleLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return label

    @staticmethod
    def _timer_field(spinbox: QSpinBox) -> tuple[QWidget, QLabel]:
        field = QWidget()
        field.setObjectName("timerField")
        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = QLabel()
        label.setObjectName("timerFieldLabel")
        layout.addWidget(label)
        layout.addWidget(spinbox)
        return field, label

    def _connect_signals(self) -> None:
        self.presentation_screen_combo.currentIndexChanged.connect(self._on_screens_changed)
        self.teleprompter_screen_combo.currentIndexChanged.connect(self._on_screens_changed)
        self.teleprompter_mode_combo.currentIndexChanged.connect(self._on_screens_changed)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        self.ndi_main_checkbox.toggled.connect(self._on_ndi_changed)
        self.ndi_teleprompter_checkbox.toggled.connect(self._on_ndi_changed)
        self.ndi_main_name.textEdited.connect(self._on_ndi_changed)
        self.ndi_teleprompter_name.textEdited.connect(self._on_ndi_changed)
        self.minutes_spin.valueChanged.connect(self._on_timer_default_changed)
        self.seconds_spin.valueChanged.connect(self._on_timer_default_changed)
        self.apply_to_all_button.clicked.connect(self.apply_timer_defaults_requested.emit)

    def _apply_theme(self) -> None:
        self.setStyleSheet(settings_stylesheet())

    def reload_theme(self) -> None:
        self._apply_theme()

    def retranslate(self) -> None:
        self.header_label.setText(tr("settings.title"))
        self.subheader_label.setText(tr("settings.subtitle"))
        self.screens_title_label.setText(tr("settings.screens"))
        self.language_label.setText(tr("settings.language"))
        self.presentation_screen_label.setText(tr("settings.main_screen"))
        self.teleprompter_screen_label.setText(tr("settings.teleprompter"))
        self.teleprompter_mode_label.setText(tr("settings.teleprompter_mode"))
        current_mode = self.teleprompter_mode()
        self.teleprompter_mode_combo.blockSignals(True)
        self.teleprompter_mode_combo.setItemText(0, tr("settings.teleprompter_mode_prompt"))
        self.teleprompter_mode_combo.setItemText(1, tr("settings.teleprompter_mode_mirror"))
        mode_index = self.teleprompter_mode_combo.findData(current_mode)
        if mode_index >= 0:
            self.teleprompter_mode_combo.setCurrentIndex(mode_index)
        self.teleprompter_mode_combo.blockSignals(False)
        self.ndi_main_checkbox.setText(tr("settings.main_ndi"))
        self.ndi_teleprompter_checkbox.setText(tr("settings.teleprompter_ndi"))
        self.timer_defaults_title_label.setText(tr("settings.timer_defaults"))
        self.minutes_label.setText(tr("settings.minutes"))
        self.seconds_label.setText(tr("settings.seconds"))
        self.apply_to_all_button.setText(tr("settings.apply_all"))
        self.hint_label.setText(tr("settings.hint"))
        if not self.ndi_status_label.text():
            self.ndi_status_label.setText(tr("ndi.off_app"))

    def _on_language_changed(self, _index: int = -1) -> None:
        selected = self.language_combo.currentData()
        if isinstance(selected, str):
            self.language_changed.emit(selected)

    def _on_screens_changed(self, _index: int = -1) -> None:
        self.screens_changed.emit()

    def _on_ndi_changed(self, *args) -> None:
        self.ndi_changed.emit()

    def refresh_screen_choices(self, screens: list) -> None:
        previous_presentation = self.presentation_screen_combo.currentData()
        previous_teleprompter = self.teleprompter_screen_combo.currentData()

        self.presentation_screen_combo.blockSignals(True)
        self.teleprompter_screen_combo.blockSignals(True)
        self.presentation_screen_combo.clear()
        self.teleprompter_screen_combo.clear()

        self.presentation_screen_combo.insertItem(0, tr("settings.no_output"), None)

        for index, screen in enumerate(screens):
            label = f"{index + 1}. {screen.name()} ({screen.geometry().width()}x{screen.geometry().height()})"
            self.presentation_screen_combo.addItem(label, index)
            self.teleprompter_screen_combo.addItem(label, index)

        self.teleprompter_screen_combo.insertItem(0, tr("settings.no_output"), None)
        presentation_target = previous_presentation
        teleprompter_target = previous_teleprompter

        self._restore_combo_selection(self.presentation_screen_combo, presentation_target, 0)

        if teleprompter_target is not None and self.teleprompter_screen_combo.findData(teleprompter_target) >= 0:
            self.teleprompter_screen_combo.setCurrentIndex(self.teleprompter_screen_combo.findData(teleprompter_target))
        elif len(screens) > 1 and self.teleprompter_screen_combo.findData(1) >= 0:
            self.teleprompter_screen_combo.setCurrentIndex(self.teleprompter_screen_combo.findData(1))
        else:
            self.teleprompter_screen_combo.setCurrentIndex(0)

        self.presentation_screen_combo.blockSignals(False)
        self.teleprompter_screen_combo.blockSignals(False)
        self.screens_changed.emit()

    @staticmethod
    def _restore_combo_selection(combo: QComboBox, target_data, fallback_index: int) -> None:
        if combo.count() == 0:
            return
        if target_data is not None:
            match_index = combo.findData(target_data)
            if match_index >= 0:
                combo.setCurrentIndex(match_index)
                return
        combo.setCurrentIndex(min(fallback_index, combo.count() - 1))

    def presentation_screen_index(self) -> int | None:
        return self.presentation_screen_combo.currentData()

    def teleprompter_screen_index(self) -> int | None:
        return self.teleprompter_screen_combo.currentData()

    def teleprompter_mode(self) -> str:
        mode = self.teleprompter_mode_combo.currentData()
        return mode if mode in {"prompt", "mirror"} else "prompt"

    def ndi_config(self) -> dict[str, str | None]:
        return {
            "main_name": self.ndi_main_name.text().strip() if self.ndi_main_checkbox.isChecked() else None,
            "teleprompter_name": (
                self.ndi_teleprompter_name.text().strip() if self.ndi_teleprompter_checkbox.isChecked() else None
            ),
        }

    def set_ndi_status(self, text: str, *, tone: str = "muted") -> None:
        color = {
            "ok": "#58A6FF",
            "error": "#F85149",
            "muted": "#8B949E",
        }.get(tone, "#8B949E")
        self.ndi_status_label.setText(text)
        self.ndi_status_label.setStyleSheet(ndi_status_style(color))

    def timer_defaults(self) -> tuple[int, int]:
        return self.minutes_spin.value(), self.seconds_spin.value()

    def timer_defaults_text(self) -> str:
        minutes, seconds = self.timer_defaults()
        total_minutes = minutes
        if total_minutes >= 60:
            hours, rem_minutes = divmod(total_minutes, 60)
            return f"{hours:02d}:{rem_minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _on_timer_default_changed(self) -> None:
        self.timer_preview_label.setText(self.timer_defaults_text())
        self.timer_defaults_changed.emit()
