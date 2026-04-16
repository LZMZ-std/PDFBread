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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SettingsTab(QWidget):
    screens_changed = Signal()
    ndi_changed = Signal()
    timer_defaults_changed = Signal()
    apply_timer_defaults_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._build_ui()
        self._connect_signals()
        self._apply_theme()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(18)

        header = QLabel("Настройки показа")
        header.setObjectName("settingsHeader")
        subheader = QLabel("Здесь живут общие экраны, NDI и время по умолчанию для таймеров во вкладках PDF.")
        subheader.setObjectName("settingsSubheader")
        subheader.setWordWrap(True)
        root.addWidget(header)
        root.addWidget(subheader)

        top_row = QHBoxLayout()
        top_row.setSpacing(18)

        self.screen_group = QGroupBox("Экраны")
        screen_layout = QGridLayout(self.screen_group)
        self.presentation_screen_combo = QComboBox()
        self.teleprompter_screen_combo = QComboBox()
        screen_layout.addWidget(QLabel("Главный экран"), 0, 0)
        screen_layout.addWidget(self.presentation_screen_combo, 0, 1)
        screen_layout.addWidget(QLabel("Суфлёр"), 1, 0)
        screen_layout.addWidget(self.teleprompter_screen_combo, 1, 1)
        top_row.addWidget(self.screen_group, 1)

        self.ndi_group = QGroupBox("NDI")
        ndi_layout = QGridLayout(self.ndi_group)
        ndi_layout.setVerticalSpacing(10)
        self.ndi_main_checkbox = QCheckBox("Main в NDI")
        self.ndi_main_name = QLineEdit("PDFBread Main")
        self.ndi_teleprompter_checkbox = QCheckBox("Суфлёр в NDI")
        self.ndi_teleprompter_name = QLineEdit("PDFBread Teleprompter")
        self.ndi_status_label = QLabel("NDI выключен для всего приложения.")
        self.ndi_status_label.setObjectName("ndiStatusLabel")
        self.ndi_status_label.setWordWrap(True)
        ndi_layout.addWidget(self.ndi_main_checkbox, 0, 0)
        ndi_layout.addWidget(self.ndi_main_name, 0, 1)
        ndi_layout.addWidget(self.ndi_teleprompter_checkbox, 1, 0)
        ndi_layout.addWidget(self.ndi_teleprompter_name, 1, 1)
        ndi_layout.addWidget(self.ndi_status_label, 2, 0, 1, 2)
        top_row.addWidget(self.ndi_group, 1)

        root.addLayout(top_row)

        self.timer_defaults_group = QGroupBox("Таймер по умолчанию")
        timer_layout = QVBoxLayout(self.timer_defaults_group)

        self.timer_preview_label = QLabel("15:00")
        self.timer_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_preview_label.setObjectName("timerLabel")
        timer_layout.addWidget(self.timer_preview_label)

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

        self.apply_to_all_button = QPushButton("Применить ко всем вкладкам")
        self.apply_to_all_button.setObjectName("primaryUtilityButton")
        timer_layout.addWidget(self.apply_to_all_button)

        hint = QLabel("Новые вкладки будут получать это время автоматически. В отдельных вкладках его можно менять вручную.")
        hint.setObjectName("settingsHint")
        hint.setWordWrap(True)
        timer_layout.addWidget(hint)
        root.addWidget(self.timer_defaults_group)

        root.addStretch(1)

    def _connect_signals(self) -> None:
        self.presentation_screen_combo.currentIndexChanged.connect(self.screens_changed.emit)
        self.teleprompter_screen_combo.currentIndexChanged.connect(self.screens_changed.emit)
        self.ndi_main_checkbox.toggled.connect(self.ndi_changed.emit)
        self.ndi_teleprompter_checkbox.toggled.connect(self.ndi_changed.emit)
        self.ndi_main_name.textEdited.connect(self.ndi_changed.emit)
        self.ndi_teleprompter_name.textEdited.connect(self.ndi_changed.emit)
        self.minutes_spin.valueChanged.connect(self._on_timer_default_changed)
        self.seconds_spin.valueChanged.connect(self._on_timer_default_changed)
        self.apply_to_all_button.clicked.connect(self.apply_timer_defaults_requested.emit)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #040706;
                color: #F5F8F6;
                font-size: 14px;
            }
            QLabel#settingsHeader {
                font-size: 24px;
                font-weight: 700;
                color: #FFFFFF;
            }
            QLabel#settingsSubheader {
                color: #8FA59A;
                padding-bottom: 4px;
            }
            QLabel#settingsHint {
                color: #8FA59A;
                padding-top: 4px;
            }
            QPushButton, QComboBox, QSpinBox, QLineEdit {
                background: #0A100C;
                color: #F5F8F6;
                border: 1px solid #1C3925;
                border-radius: 12px;
                padding: 9px 12px;
                min-height: 18px;
            }
            QPushButton:hover, QComboBox:hover, QSpinBox:hover, QLineEdit:hover {
                border-color: #38B35A;
                background: #0E1611;
            }
            QPushButton#primaryUtilityButton {
                background: #0C1711;
                color: #B6F5C4;
                border-color: #2C7A40;
                font-weight: 700;
            }
            QPushButton#primaryUtilityButton:hover {
                background: #13241A;
            }
            QLineEdit:focus {
                border-color: #38B35A;
                background: #101813;
            }
            QCheckBox {
                spacing: 8px;
                color: #EEF5F0;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 5px;
                border: 1px solid #2A5234;
                background: #09110C;
            }
            QCheckBox::indicator:checked {
                background: #169A42;
                border-color: #2EC65B;
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
            QLabel#timerLabel {
                color: #41E06D;
                font-size: 40px;
                font-weight: 700;
            }
            QLabel#ndiStatusLabel {
                color: #93A49A;
                padding-top: 2px;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 20px;
                border: none;
                background: transparent;
            }
            """
        )

    def refresh_screen_choices(self, screens: list) -> None:
        previous_presentation = self.presentation_screen_combo.currentData()
        previous_teleprompter = self.teleprompter_screen_combo.currentData()

        self.presentation_screen_combo.blockSignals(True)
        self.teleprompter_screen_combo.blockSignals(True)
        self.presentation_screen_combo.clear()
        self.teleprompter_screen_combo.clear()

        for index, screen in enumerate(screens):
            label = f"{index + 1}. {screen.name()} ({screen.geometry().width()}x{screen.geometry().height()})"
            self.presentation_screen_combo.addItem(label, index)
            self.teleprompter_screen_combo.addItem(label, index)

        self.teleprompter_screen_combo.insertItem(0, "Не выводить", None)
        self._restore_combo_selection(self.presentation_screen_combo, previous_presentation, 0)

        if previous_teleprompter is not None and self.teleprompter_screen_combo.findData(previous_teleprompter) >= 0:
            self.teleprompter_screen_combo.setCurrentIndex(self.teleprompter_screen_combo.findData(previous_teleprompter))
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

    def ndi_config(self) -> dict[str, str | None]:
        return {
            "main_name": self.ndi_main_name.text().strip() if self.ndi_main_checkbox.isChecked() else None,
            "teleprompter_name": (
                self.ndi_teleprompter_name.text().strip() if self.ndi_teleprompter_checkbox.isChecked() else None
            ),
        }

    def set_ndi_status(self, text: str, *, tone: str = "muted") -> None:
        color = {
            "ok": "#41E06D",
            "error": "#F07E7E",
            "muted": "#93A49A",
        }.get(tone, "#93A49A")
        self.ndi_status_label.setText(text)
        self.ndi_status_label.setStyleSheet(f"color: {color}; padding-top: 2px;")

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
