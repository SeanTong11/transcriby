#!/usr/bin/env python3
"""Qt settings/about/shortcuts dialog."""

from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from transcriby.app_constants import (
    APP_TITLE,
    APP_URL,
    APP_VERSION,
    DEFAULT_SEEK_STEP_COARSE_MS,
    DEFAULT_SEEK_STEP_FINE_MS,
    MAX_SEEK_STEP_MS,
    MIN_SEEK_STEP_MS,
    UI_TEXT_MUTED,
)
from transcriby.qt_controller import PlaybackController
from transcriby.qt_widgets import ShortcutStepDoubleSpinBox, ShortcutStepSpinBox


SHORTCUT_ROWS = [
    ("Ctrl+O", "Open media file"),
    ("Ctrl+R", "Open recent files dialog"),
    ("Ctrl+S", "Save session (.tby)"),
    ("Ctrl+Shift+S", "Save session as (.tby)"),
    ("Ctrl+Q", "Quit"),
    ("F1", "Open shortcuts help"),
    ("Space", "Restart from A (loop on) or play/pause"),
    ("Enter", "Play/Pause"),
    ("L", "Toggle loop"),
    ("A / B", "Set loop start / end"),
    ("Ctrl+A / Ctrl+B", "Reset loop start / end"),
    ("M / Shift+M", "Add / delete favorite"),
    ("Ctrl+[ / Ctrl+]", "Jump previous / next favorite"),
    ("[ ]", "Seek -/+ coarse step"),
    (", .", "Seek -/+ fine step"),
    ("Numpad 1/3/4/6/7/9", "Seek 5/10/15s backward/forward"),
    ("Numpad 8/2/5", "Speed +0.1/-0.1/reset"),
    ("Numpad + / -", "Transpose semitone +/-"),
    ("Numpad / *", "Set loop A / B"),
    ("Numpad 0", "Play/Pause"),
    ("Timeline left click", "Seek to cursor"),
    ("Timeline marker click", "Jump to favorite marker"),
    ("Timeline right click", "Context: set A/B here"),
    ("Timeline right drag", "Select loop A-B range"),
]


class SettingsDialog(QDialog):
    def __init__(self, controller: PlaybackController, parent=None, open_tab: str = "playback"):
        super().__init__(parent)
        self.controller = controller

        self.setWindowTitle("Settings")
        self.setMinimumSize(760, 560)

        root = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        root.addWidget(self.tabs, 1)

        self.playback_tab = QWidget(self.tabs)
        self.about_tab = QWidget(self.tabs)
        self.shortcuts_tab = QWidget(self.tabs)

        self.tabs.addTab(self.playback_tab, "Playback")
        self.tabs.addTab(self.about_tab, "About")
        self.tabs.addTab(self.shortcuts_tab, "Shortcuts")

        self._build_playback_tab()
        self._build_about_tab()
        self._build_shortcuts_tab()

        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

        tab_index = {"playback": 0, "about": 1, "shortcuts": 2}.get(str(open_tab).lower(), 0)
        self.tabs.setCurrentIndex(tab_index)

    def _build_playback_tab(self):
        layout = QVBoxLayout(self.playback_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Loop Restart Delay")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)

        desc = QLabel("Configure delayed restart when pressing Space with loop enabled.")
        desc.setStyleSheet(f"color: {UI_TEXT_MUTED};")
        layout.addWidget(desc)

        enabled, seconds = self.controller.get_loop_restart_delay_settings()
        self.delay_enabled = QCheckBox("Enable delayed restart")
        self.delay_enabled.setChecked(enabled)
        layout.addWidget(self.delay_enabled)

        form = QFormLayout()
        self.delay_seconds = ShortcutStepDoubleSpinBox()
        self.delay_seconds.setRange(0.0, 10.0)
        self.delay_seconds.setSingleStep(0.05)
        self.delay_seconds.setDecimals(2)
        self.delay_seconds.setValue(seconds)
        form.addRow("Delay (seconds)", self.delay_seconds)

        seek_fine_ms, seek_coarse_ms = self.controller.get_seek_step_settings_ms()
        self.seek_step_fine_ms = ShortcutStepSpinBox()
        self.seek_step_fine_ms.setRange(MIN_SEEK_STEP_MS, MAX_SEEK_STEP_MS)
        self.seek_step_fine_ms.setSingleStep(10)
        self.seek_step_fine_ms.setValue(int(seek_fine_ms))
        form.addRow("Seek fine (ms)", self.seek_step_fine_ms)

        self.seek_step_coarse_ms = ShortcutStepSpinBox()
        self.seek_step_coarse_ms.setRange(MIN_SEEK_STEP_MS, MAX_SEEK_STEP_MS)
        self.seek_step_coarse_ms.setSingleStep(50)
        self.seek_step_coarse_ms.setValue(int(seek_coarse_ms))
        form.addRow("Seek coarse (ms)", self.seek_step_coarse_ms)
        layout.addLayout(form)

        self.debug_title = QLabel("Troubleshooting")
        self.debug_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(self.debug_title)

        debug_enabled, debug_path = self.controller.get_debug_logging_settings()
        self.debug_enabled = QCheckBox("Enable debug logging")
        self.debug_enabled.setChecked(debug_enabled)
        layout.addWidget(self.debug_enabled)

        self.debug_path_label = QLabel(f"Debug log path: {debug_path}")
        self.debug_path_label.setStyleSheet(f"color: {UI_TEXT_MUTED};")
        self.debug_path_label.setWordWrap(True)
        layout.addWidget(self.debug_path_label)

        row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_playback_settings)
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._reset_playback_settings)
        row.addWidget(save_btn)
        row.addWidget(reset_btn)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)

    def _build_about_tab(self):
        layout = QVBoxLayout(self.about_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(APP_TITLE)
        title.setStyleSheet("font-size: 28px; font-weight: 700;")
        layout.addWidget(title, 0, Qt.AlignHCenter)

        version = QLabel(APP_VERSION)
        version.setStyleSheet("font-size: 18px;")
        layout.addWidget(version, 0, Qt.AlignHCenter)

        subtitle = QLabel("Maintained by Sean Tong")
        subtitle.setStyleSheet(f"color: {UI_TEXT_MUTED};")
        layout.addWidget(subtitle, 0, Qt.AlignHCenter)

        link = QLabel(f"<a href='{APP_URL}'>{APP_URL}</a>")
        link.setOpenExternalLinks(False)
        link.linkActivated.connect(lambda _url: webbrowser.open(APP_URL))
        layout.addWidget(link, 0, Qt.AlignHCenter)

    def _build_shortcuts_tab(self):
        layout = QVBoxLayout(self.shortcuts_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel("Keyboard Shortcuts")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)

        grid_host = QWidget(self.shortcuts_tab)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)

        for idx, (key, desc) in enumerate(SHORTCUT_ROWS):
            key_label = QLabel(key)
            key_label.setStyleSheet("font-weight: 600;")
            desc_label = QLabel(desc)
            desc_label.setWordWrap(True)
            grid.addWidget(key_label, idx, 0)
            grid.addWidget(desc_label, idx, 1)

        grid.setColumnStretch(1, 1)
        layout.addWidget(grid_host, 1)

    def _save_playback_settings(self):
        enabled = self.delay_enabled.isChecked()
        seconds = float(self.delay_seconds.value())
        enabled, normalized = self.controller.set_loop_restart_delay_settings(enabled, seconds)
        self.delay_enabled.setChecked(enabled)
        self.delay_seconds.setValue(normalized)
        normalized_fine_ms, normalized_coarse_ms = self.controller.set_seek_step_settings_ms(
            int(self.seek_step_fine_ms.value()),
            int(self.seek_step_coarse_ms.value()),
        )
        self.seek_step_fine_ms.setValue(int(normalized_fine_ms))
        self.seek_step_coarse_ms.setValue(int(normalized_coarse_ms))
        debug_enabled, debug_path = self.controller.set_debug_logging_settings(self.debug_enabled.isChecked())
        self.debug_enabled.setChecked(debug_enabled)
        self.debug_path_label.setText(f"Debug log path: {debug_path}")

    def _reset_playback_settings(self):
        self.delay_enabled.setChecked(False)
        self.delay_seconds.setValue(0.25)
        self.seek_step_fine_ms.setValue(DEFAULT_SEEK_STEP_FINE_MS)
        self.seek_step_coarse_ms.setValue(DEFAULT_SEEK_STEP_COARSE_MS)
        self.debug_enabled.setChecked(False)
        self._save_playback_settings()
