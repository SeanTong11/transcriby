#!/usr/bin/env python3
"""PySide6 main window for Transcriby."""

from __future__ import annotations

import datetime as dt
import os

from PySide6.QtCore import QSignalBlocker, QSize, Signal, Slot, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDragEnterEvent, QDropEvent, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from transcriby.app_constants import (
    APP_TITLE,
    INITIAL_GEOMETRY,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    MAX_PITCH_CENTS,
    MAX_PITCH_SEMITONES,
    MAX_SPEED_PERCENT,
    MAX_VOLUME,
    MIN_PITCH_CENTS,
    MIN_PITCH_SEMITONES,
    MIN_SPEED_PERCENT,
    MIN_VOLUME,
    MOVE_LOOP_POINTS_COARSE,
    MOVE_LOOP_POINTS_FINE,
    OPEN_EXTENSIONS_FILTER,
    SAVE_DEFAULT_EXTENSION,
    SAVE_EXTENSIONS_FILTER,
    SPEED_SLIDER_MIN,
    STEPS_SEC_MOVE_1,
    STEPS_SEC_MOVE_2,
    STEPS_SEC_MOVE_3,
    STEPS_SEMITONES,
    STEPS_SPEED,
    UI_ACCENT,
    UI_ACCENT_HOVER,
    UI_BG_APP,
    UI_BG_CARD,
    UI_BG_CARD_ALT,
    UI_BORDER_COLOR,
    UI_FAVORITE_COLORS,
    UI_TEXT_MUTED,
    UPDATE_INTERVAL,
    WAVEFORM_HEIGHT,
)
from transcriby.debuglog import debug_log
from transcriby.platform_utils import get_resources_dir
from transcriby.qt_controller import PlaybackController, PlaybackSnapshot
from transcriby.qt_settings_dialog import SettingsDialog
from transcriby.qt_timeline import QtTimelineWidget
from transcriby.qt_widgets import ShortcutStepDoubleSpinBox, ShortcutStepSpinBox


def format_seconds_text(seconds: float | None) -> str:
    if seconds is None:
        return "---"
    seconds = max(0.0, float(seconds))
    integral = int(seconds)
    frac = int(round((seconds - integral) * 1000))
    if frac >= 1000:
        integral += 1
        frac = 0
    return f"{dt.timedelta(seconds=integral)}.{frac:03d}"


def build_open_filter() -> str:
    wildcard = " ".join([f"*.{ext}" for ext in OPEN_EXTENSIONS_FILTER])
    return f"Supported Files ({wildcard} *.tby);;All Files (*)"


def build_audio_save_filter() -> str:
    wildcard = " ".join([f"*.{ext}" for ext in SAVE_EXTENSIONS_FILTER])
    return f"Audio Files ({wildcard});;All Files (*)"


def build_tby_filter() -> str:
    return "Session Files (*.tby);;All Files (*)"


class TranscribyQtWindow(QMainWindow):
    _mpv_shortcut_signal = Signal(object)

    def __init__(self, controller: PlaybackController, args):
        super().__init__()
        self.controller = controller
        self.args = args

        self._scrubbing_progress = False
        self._syncing_favorites = False
        self._favorites_revision_seen = -1
        self._loop_context_seconds = None
        self._play_icon = QIcon()
        self._pause_icon = QIcon()

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(UPDATE_INTERVAL)
        self._tick_timer.timeout.connect(self._on_tick)

        self._loop_restart_timer = QTimer(self)
        self._loop_restart_timer.setSingleShot(True)
        self._loop_restart_timer.timeout.connect(self._on_delayed_loop_restart)
        self._mpv_shortcut_signal.connect(
            self._dispatch_mpv_shortcut,
            Qt.ConnectionType.QueuedConnection,
        )

        self._setup_window()
        self._build_ui()
        self._apply_styles()
        self._bind_shortcuts()
        self._bind_mpv_shortcuts()
        self._rebuild_recent_menu()

        if self.args.media:
            if str(self.args.media).lower().endswith(".tby"):
                self._open_tby_path(self.args.media)
            else:
                self.open_media_path(self.args.media, apply_recent_options=False)
        else:
            self._open_startup_session()

        self._on_tick()
        self._tick_timer.start()

    def _setup_window(self):
        width, height = INITIAL_GEOMETRY.split("x")
        self.resize(int(width), int(height))
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.setWindowTitle(APP_TITLE)
        self.setAcceptDrops(True)

        resources_dir = get_resources_dir()
        icon_path = os.path.join(resources_dir, "Icona.ico")
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        play_icon_path = os.path.join(resources_dir, "play-control.svg")
        if os.path.isfile(play_icon_path):
            self._play_icon = QIcon(play_icon_path)
        pause_icon_path = os.path.join(resources_dir, "pause-control.svg")
        if os.path.isfile(pause_icon_path):
            self._pause_icon = QIcon(pause_icon_path)

    def _build_ui(self):
        root_widget = QWidget(self)
        root_widget.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setCentralWidget(root_widget)
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(14, 12, 14, 8)
        root.setSpacing(8)

        self.time_label = QLabel("0:00:00.000")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("font-size: 34px; font-weight: 600;")
        root.addWidget(self.time_label)

        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 1000000)
        self.progress_slider.sliderPressed.connect(self._on_progress_pressed)
        self.progress_slider.sliderReleased.connect(self._on_progress_released)
        self.progress_slider.sliderMoved.connect(self._on_progress_moved)
        root.addWidget(self.progress_slider)

        self.timeline = QtTimelineWidget(
            self,
            on_seek=self._on_timeline_seek,
            on_loop_select=self._on_timeline_loop_select,
            on_context_request=self._on_timeline_context_request,
            on_marker_activate=self._on_timeline_marker_activate,
            height=WAVEFORM_HEIGHT,
        )
        root.addWidget(self.timeline)

        playback_box = QGroupBox("Playback Control")
        playback_layout = QHBoxLayout(playback_box)
        playback_layout.setContentsMargins(10, 12, 10, 10)
        playback_layout.setSpacing(8)

        self.seek_back_1_button = QPushButton("<<")
        self.seek_back_1_button.clicked.connect(self._seek_backward_coarse)
        self.seek_back_01_button = QPushButton("<")
        self.seek_back_01_button.clicked.connect(self._seek_backward_fine)
        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("playButton")
        self.play_button.setMinimumWidth(132)
        self.play_button.setIconSize(QSize(16, 16))
        self.play_button.setContentsMargins(8, 0, 8, 0)
        self.play_button.clicked.connect(self._on_toggle_play_clicked)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.rewind_button = QPushButton("Rewind")
        self.rewind_button.clicked.connect(self._on_rewind_clicked)
        self.seek_fwd_01_button = QPushButton(">")
        self.seek_fwd_01_button.clicked.connect(self._seek_forward_fine)
        self.seek_fwd_1_button = QPushButton(">>")
        self.seek_fwd_1_button.clicked.connect(self._seek_forward_coarse)
        for btn in (
            self.seek_back_1_button,
            self.seek_back_01_button,
            self.seek_fwd_01_button,
            self.seek_fwd_1_button,
        ):
            btn.setFixedWidth(42)
        playback_layout.addStretch(1)
        playback_layout.addWidget(self.rewind_button)
        playback_layout.addWidget(self.seek_back_1_button)
        playback_layout.addWidget(self.seek_back_01_button)
        playback_layout.addWidget(self.play_button)
        playback_layout.addWidget(self.stop_button)
        playback_layout.addWidget(self.seek_fwd_01_button)
        playback_layout.addWidget(self.seek_fwd_1_button)
        playback_layout.addStretch(1)
        root.addWidget(playback_box)

        loop_box = QGroupBox("Loop Control")
        loop_layout = QVBoxLayout(loop_box)
        loop_layout.setContentsMargins(10, 12, 10, 10)
        loop_layout.setSpacing(8)

        loop_body_row = QHBoxLayout()
        loop_body_row.setSpacing(14)

        loop_left_col = QVBoxLayout()
        loop_left_col.setSpacing(6)
        self.loop_a_label = QLabel("A: ---")
        loop_left_col.addWidget(self.loop_a_label, 0, Qt.AlignLeft)
        loop_a_buttons = QHBoxLayout()
        loop_a_buttons.setSpacing(6)
        self.reset_a_button = QPushButton("Reset A")
        self.reset_a_button.clicked.connect(self._on_reset_loop_start_clicked)
        self.set_a_button = QPushButton("Set A")
        self.set_a_button.clicked.connect(self._on_set_loop_start_clicked)
        self.loop_a_back_coarse_button = QPushButton("<<")
        self.loop_a_back_coarse_button.clicked.connect(lambda: self._on_move_loop_start_clicked(-MOVE_LOOP_POINTS_COARSE))
        self.loop_a_back_fine_button = QPushButton("<")
        self.loop_a_back_fine_button.clicked.connect(lambda: self._on_move_loop_start_clicked(-MOVE_LOOP_POINTS_FINE))
        self.loop_a_fwd_fine_button = QPushButton(">")
        self.loop_a_fwd_fine_button.clicked.connect(lambda: self._on_move_loop_start_clicked(MOVE_LOOP_POINTS_FINE))
        self.loop_a_fwd_coarse_button = QPushButton(">>")
        self.loop_a_fwd_coarse_button.clicked.connect(lambda: self._on_move_loop_start_clicked(MOVE_LOOP_POINTS_COARSE))
        for btn in (
            self.loop_a_back_coarse_button,
            self.loop_a_back_fine_button,
            self.loop_a_fwd_fine_button,
            self.loop_a_fwd_coarse_button,
        ):
            btn.setFixedWidth(42)
        loop_a_buttons.addWidget(self.reset_a_button)
        loop_a_buttons.addWidget(self.set_a_button)
        loop_a_buttons.addWidget(self.loop_a_back_coarse_button)
        loop_a_buttons.addWidget(self.loop_a_back_fine_button)
        loop_a_buttons.addWidget(self.loop_a_fwd_fine_button)
        loop_a_buttons.addWidget(self.loop_a_fwd_coarse_button)
        loop_left_col.addLayout(loop_a_buttons)
        loop_body_row.addLayout(loop_left_col, 1)

        loop_center_col = QVBoxLayout()
        loop_center_col.setSpacing(6)
        loop_toggle_row = QHBoxLayout()
        self.loop_toggle_switch = QCheckBox("Enable loop")
        self.loop_toggle_switch.toggled.connect(self._on_loop_toggle_toggled)
        self.loop_help_button = QPushButton("?")
        self.loop_help_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.loop_help_button.setFixedWidth(28)
        self.loop_help_button.clicked.connect(self._show_shortcuts_help)
        loop_toggle_row.addStretch(1)
        loop_toggle_row.addWidget(self.loop_toggle_switch)
        loop_toggle_row.addWidget(self.loop_help_button)
        loop_toggle_row.addStretch(1)
        loop_center_col.addLayout(loop_toggle_row)
        self.loop_hint_label = QLabel("Loop is off")
        self.loop_hint_label.setAlignment(Qt.AlignCenter)
        self.loop_hint_label.setWordWrap(True)
        self.loop_hint_label.setStyleSheet(f"color: {UI_TEXT_MUTED};")
        loop_center_col.addWidget(self.loop_hint_label, 0, Qt.AlignCenter)
        loop_body_row.addLayout(loop_center_col, 1)

        loop_right_col = QVBoxLayout()
        loop_right_col.setSpacing(6)
        self.loop_b_label = QLabel("B: ---")
        self.loop_b_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        loop_right_col.addWidget(self.loop_b_label, 0, Qt.AlignRight)
        loop_b_buttons = QHBoxLayout()
        loop_b_buttons.setSpacing(6)
        self.set_b_button = QPushButton("Set B")
        self.set_b_button.clicked.connect(self._on_set_loop_end_clicked)
        self.reset_b_button = QPushButton("Reset B")
        self.reset_b_button.clicked.connect(self._on_reset_loop_end_clicked)
        self.loop_b_back_coarse_button = QPushButton("<<")
        self.loop_b_back_coarse_button.clicked.connect(lambda: self._on_move_loop_end_clicked(-MOVE_LOOP_POINTS_COARSE))
        self.loop_b_back_fine_button = QPushButton("<")
        self.loop_b_back_fine_button.clicked.connect(lambda: self._on_move_loop_end_clicked(-MOVE_LOOP_POINTS_FINE))
        self.loop_b_fwd_fine_button = QPushButton(">")
        self.loop_b_fwd_fine_button.clicked.connect(lambda: self._on_move_loop_end_clicked(MOVE_LOOP_POINTS_FINE))
        self.loop_b_fwd_coarse_button = QPushButton(">>")
        self.loop_b_fwd_coarse_button.clicked.connect(lambda: self._on_move_loop_end_clicked(MOVE_LOOP_POINTS_COARSE))
        for btn in (
            self.loop_b_back_coarse_button,
            self.loop_b_back_fine_button,
            self.loop_b_fwd_fine_button,
            self.loop_b_fwd_coarse_button,
        ):
            btn.setFixedWidth(42)
        loop_b_buttons.addWidget(self.set_b_button)
        loop_b_buttons.addWidget(self.reset_b_button)
        loop_b_buttons.addWidget(self.loop_b_back_coarse_button)
        loop_b_buttons.addWidget(self.loop_b_back_fine_button)
        loop_b_buttons.addWidget(self.loop_b_fwd_fine_button)
        loop_b_buttons.addWidget(self.loop_b_fwd_coarse_button)
        loop_right_col.addLayout(loop_b_buttons)
        loop_body_row.addLayout(loop_right_col, 1)

        loop_layout.addLayout(loop_body_row)
        root.addWidget(loop_box)

        favorites_box = QGroupBox("Favorites")
        favorites_layout = QVBoxLayout(favorites_box)
        favorites_layout.setContentsMargins(10, 12, 10, 10)
        favorites_layout.setSpacing(8)

        favorites_actions_row = QHBoxLayout()
        self.favorite_add_button = QPushButton("Add")
        self.favorite_add_button.clicked.connect(self._on_add_favorite_clicked)
        self.favorite_delete_button = QPushButton("Delete")
        self.favorite_delete_button.clicked.connect(self._on_delete_favorite_clicked)
        self.favorite_prev_button = QPushButton("Prev")
        self.favorite_prev_button.clicked.connect(self._on_jump_previous_favorite_clicked)
        self.favorite_next_button = QPushButton("Next")
        self.favorite_next_button.clicked.connect(self._on_jump_next_favorite_clicked)
        self.favorite_count_label = QLabel("0 total")
        self.favorite_count_label.setStyleSheet(f"color: {UI_TEXT_MUTED};")

        favorites_actions_row.addWidget(self.favorite_add_button)
        favorites_actions_row.addWidget(self.favorite_delete_button)
        favorites_actions_row.addWidget(self.favorite_prev_button)
        favorites_actions_row.addWidget(self.favorite_next_button)
        favorites_actions_row.addStretch(1)
        favorites_actions_row.addWidget(self.favorite_count_label)
        favorites_layout.addLayout(favorites_actions_row)

        self.favorite_list = QListWidget()
        self.favorite_list.setAlternatingRowColors(True)
        self.favorite_list.currentRowChanged.connect(self._on_favorite_row_changed)
        favorites_layout.addWidget(self.favorite_list)

        root.addWidget(favorites_box)

        audio_box = QGroupBox("Audio Controls")
        audio_form = QFormLayout(audio_box)
        audio_form.setHorizontalSpacing(14)
        audio_form.setVerticalSpacing(8)

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(int(SPEED_SLIDER_MIN * 10), int(MAX_SPEED_PERCENT * 10))
        self.speed_slider.valueChanged.connect(self._on_speed_slider_changed)
        self.speed_spin = ShortcutStepDoubleSpinBox()
        self.speed_spin.setDecimals(1)
        self.speed_spin.setSingleStep(STEPS_SPEED)
        self.speed_spin.setRange(MIN_SPEED_PERCENT, MAX_SPEED_PERCENT)
        self.speed_spin.valueChanged.connect(self._on_speed_changed)
        self.speed_reset_button = QPushButton("Reset")
        self.speed_reset_button.clicked.connect(self._on_reset_speed_clicked)
        speed_row = QHBoxLayout()
        speed_row.addWidget(self.speed_slider, 1)
        speed_row.addWidget(self.speed_spin)
        speed_row.addWidget(self.speed_reset_button)
        audio_form.addRow("Speed", speed_row)

        self.semitones_slider = QSlider(Qt.Horizontal)
        self.semitones_slider.setRange(MIN_PITCH_SEMITONES, MAX_PITCH_SEMITONES)
        self.semitones_slider.valueChanged.connect(self._on_semitones_slider_changed)
        self.semitones_spin = ShortcutStepSpinBox()
        self.semitones_spin.setRange(MIN_PITCH_SEMITONES, MAX_PITCH_SEMITONES)
        self.semitones_spin.valueChanged.connect(self._on_semitones_changed)
        self.semitones_reset_button = QPushButton("Reset")
        self.semitones_reset_button.clicked.connect(self._on_reset_semitones_clicked)
        semitone_row = QHBoxLayout()
        semitone_row.addWidget(self.semitones_slider, 1)
        semitone_row.addWidget(self.semitones_spin)
        semitone_row.addWidget(self.semitones_reset_button)
        audio_form.addRow("Transpose", semitone_row)

        self.cents_slider = QSlider(Qt.Horizontal)
        self.cents_slider.setRange(MIN_PITCH_CENTS, MAX_PITCH_CENTS)
        self.cents_slider.valueChanged.connect(self._on_cents_slider_changed)
        self.cents_spin = ShortcutStepSpinBox()
        self.cents_spin.setRange(MIN_PITCH_CENTS, MAX_PITCH_CENTS)
        self.cents_spin.valueChanged.connect(self._on_cents_changed)
        self.cents_reset_button = QPushButton("Reset")
        self.cents_reset_button.clicked.connect(self._on_reset_cents_clicked)
        cents_row = QHBoxLayout()
        cents_row.addWidget(self.cents_slider, 1)
        cents_row.addWidget(self.cents_spin)
        cents_row.addWidget(self.cents_reset_button)
        audio_form.addRow("Pitch (cents)", cents_row)

        volume_row = QHBoxLayout()
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(MIN_VOLUME, MAX_VOLUME)
        self.volume_slider.valueChanged.connect(self._on_volume_slider_changed)
        self.volume_spin = ShortcutStepSpinBox()
        self.volume_spin.setRange(MIN_VOLUME, MAX_VOLUME)
        self.volume_spin.valueChanged.connect(self._on_volume_spin_changed)
        self.volume_reset_button = QPushButton("Reset")
        self.volume_reset_button.clicked.connect(self._on_reset_volume_clicked)
        volume_row.addWidget(self.volume_slider, 1)
        volume_row.addWidget(self.volume_spin)
        volume_row.addWidget(self.volume_reset_button)
        audio_form.addRow("Volume", volume_row)

        root.addWidget(audio_box)

        root.addStretch(1)

        self.media_info_label = QLabel("No media loaded")
        self.media_info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.media_info_label.setStyleSheet(f"color: {UI_TEXT_MUTED};")
        root.addWidget(self.media_info_label)

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        open_action = QAction("Open...", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._on_open_clicked)
        file_menu.addAction(open_action)

        open_tby_action = QAction("Open .tby...", self)
        open_tby_action.triggered.connect(self._on_open_tby_clicked)
        file_menu.addAction(open_tby_action)

        open_recent_action = QAction("Open Recent...", self)
        open_recent_action.setShortcut(QKeySequence("Ctrl+R"))
        open_recent_action.triggered.connect(self._on_open_recent_dialog)
        file_menu.addAction(open_recent_action)

        self.recent_menu = file_menu.addMenu("Open Recent")
        file_menu.addSeparator()

        save_session_action = QAction("Save Session", self)
        save_session_action.setShortcut(QKeySequence("Ctrl+S"))
        save_session_action.triggered.connect(self._on_save_session_clicked)
        file_menu.addAction(save_session_action)

        save_session_as_action = QAction("Save Session As...", self)
        save_session_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_session_as_action.triggered.connect(self._on_save_session_as_clicked)
        file_menu.addAction(save_session_as_action)

        export_audio_action = QAction("Export Audio As...", self)
        export_audio_action.triggered.connect(self._on_export_audio_as_clicked)
        file_menu.addAction(export_audio_action)

        file_menu.addSeparator()

        clear_recent_action = QAction("Clear Recent", self)
        clear_recent_action.triggered.connect(self._on_clear_recent_clicked)
        file_menu.addAction(clear_recent_action)
        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = menu_bar.addMenu("Help")
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._open_settings_dialog)
        help_menu.addAction(settings_action)

        about_action = QAction("About", self)
        about_action.triggered.connect(self._open_about_dialog)
        help_menu.addAction(about_action)

        shortcuts_action = QAction("Shortcuts", self)
        shortcuts_action.setShortcut(QKeySequence("F1"))
        shortcuts_action.triggered.connect(self._show_shortcuts_help)
        help_menu.addAction(shortcuts_action)

        self._configure_tooltips()
        self.statusBar().showMessage("Ready")

    def _apply_styles(self):
        resources_dir = get_resources_dir()
        switch_off_path = os.path.join(resources_dir, "switch-off.svg").replace("\\", "/")
        switch_on_path = os.path.join(resources_dir, "switch-on.svg").replace("\\", "/")
        switch_off_image = f'image: url("{switch_off_path}");' if os.path.isfile(switch_off_path) else "image: none;"
        switch_on_image = f'image: url("{switch_on_path}");' if os.path.isfile(switch_on_path) else "image: none;"

        self.setStyleSheet(
            f"""
            QWidget {{
                background: {UI_BG_APP};
                color: #F2E5C6;
            }}
            QGroupBox {{
                border: 1px solid {UI_BORDER_COLOR};
                border-radius: 8px;
                margin-top: 6px;
                padding-top: 8px;
                background: {UI_BG_CARD};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }}
            QPushButton {{
                background: {UI_BG_CARD_ALT};
                border: 1px solid {UI_BORDER_COLOR};
                border-radius: 6px;
                padding: 6px 10px;
            }}
            QPushButton:hover {{
                background: {UI_ACCENT};
                color: #19130E;
            }}
            QPushButton:checked {{
                background: {UI_ACCENT};
                color: #19130E;
                border-color: {UI_ACCENT_HOVER};
            }}
            QPushButton#playButton {{
                padding: 6px 18px;
                min-width: 132px;
            }}
            QCheckBox {{
                spacing: 8px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 38px;
                height: 20px;
                border: none;
                background: transparent;
            }}
            QCheckBox::indicator:unchecked {{
                {switch_off_image}
            }}
            QCheckBox::indicator:checked {{
                {switch_on_image}
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {UI_BORDER_COLOR};
                height: 5px;
                border-radius: 2px;
                background: {UI_BG_CARD_ALT};
            }}
            QSlider::sub-page:horizontal {{
                background: #D6BC82;
                border-radius: 2px;
            }}
            QSlider::add-page:horizontal {{
                background: #1F1812;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: #F1D9A0;
                border: 1px solid #1A140F;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QSpinBox, QDoubleSpinBox {{
                background: {UI_BG_CARD_ALT};
                border: 1px solid {UI_BORDER_COLOR};
                border-radius: 6px;
                padding: 2px 6px;
            }}
            QListWidget {{
                background: {UI_BG_CARD_ALT};
                border: 1px solid {UI_BORDER_COLOR};
                border-radius: 6px;
            }}
            QListWidget::item:selected {{
                background: {UI_ACCENT};
                color: #19130E;
            }}
            QListWidget::item:hover {{
                background: #8A6A3A;
                color: #F2E5C6;
            }}
            """
        )

    def _configure_tooltips(self):
        self.rewind_button.setToolTip(
            "Restart from A when loop range is active, otherwise toggle Play/Pause\nShortcut: Space"
        )
        self._configure_seek_tooltips()
        self.play_button.setToolTip("Play / Pause\nShortcuts: Enter, Numpad 0")
        self.stop_button.setToolTip("Stop playback")

        self.loop_toggle_switch.setToolTip(
            "Toggle loop playing\nShortcut: L\nTip: right-click and drag on timeline to set A/B"
        )
        self.loop_help_button.setToolTip(
            "How to set loop A/B:\n- Press A to set loop start\n- Press B to set loop end\n"
            "- Or right-click and drag on timeline"
        )
        self.reset_a_button.setToolTip("Reset loop start point\nShortcut: Ctrl+A")
        self.set_a_button.setToolTip("Set loop start point\nShortcut: A")
        self.loop_a_label.setToolTip("Loop start point (A). Fine: 10 ms, Coarse: 100 ms")
        self.reset_b_button.setToolTip("Reset loop end point\nShortcut: Ctrl+B")
        self.set_b_button.setToolTip("Set loop end point\nShortcut: B")
        self.loop_b_label.setToolTip("Loop end point (B). Fine: 10 ms, Coarse: 100 ms")
        self.loop_a_back_coarse_button.setToolTip(f"Move loop start left by {MOVE_LOOP_POINTS_COARSE} ms")
        self.loop_a_back_fine_button.setToolTip(f"Move loop start left by {MOVE_LOOP_POINTS_FINE} ms")
        self.loop_a_fwd_fine_button.setToolTip(f"Move loop start right by {MOVE_LOOP_POINTS_FINE} ms")
        self.loop_a_fwd_coarse_button.setToolTip(f"Move loop start right by {MOVE_LOOP_POINTS_COARSE} ms")
        self.loop_b_back_coarse_button.setToolTip(f"Move loop end left by {MOVE_LOOP_POINTS_COARSE} ms")
        self.loop_b_back_fine_button.setToolTip(f"Move loop end left by {MOVE_LOOP_POINTS_FINE} ms")
        self.loop_b_fwd_fine_button.setToolTip(f"Move loop end right by {MOVE_LOOP_POINTS_FINE} ms")
        self.loop_b_fwd_coarse_button.setToolTip(f"Move loop end right by {MOVE_LOOP_POINTS_COARSE} ms")

        self.favorite_add_button.setToolTip("Add favorite at current position\nShortcut: M")
        self.favorite_delete_button.setToolTip("Delete selected favorite\nShortcut: Shift+M")
        self.favorite_prev_button.setToolTip("Jump to previous favorite\nShortcut: Ctrl+[")
        self.favorite_next_button.setToolTip("Jump to next favorite\nShortcut: Ctrl+]")

        self.speed_slider.setToolTip("Playback speed")
        self.speed_spin.setToolTip("Playback speed value")
        self.speed_reset_button.setToolTip("Reset playback speed to 100%\nShortcut: Numpad 5")
        self.semitones_slider.setToolTip("Transpose in semitones")
        self.semitones_spin.setToolTip("Transpose value")
        self.semitones_reset_button.setToolTip("Reset transpose")
        self.cents_slider.setToolTip("Fine pitch in cents")
        self.cents_spin.setToolTip("Pitch cents value")
        self.cents_reset_button.setToolTip("Reset pitch cents")
        self.volume_slider.setToolTip("Playback volume")
        self.volume_spin.setToolTip("Volume percent")
        self.volume_reset_button.setToolTip("Reset volume")

    def _configure_seek_tooltips(self):
        fine_seconds, coarse_seconds = self.controller.get_seek_step_settings_seconds()
        fine_ms = int(round(fine_seconds * 1000.0))
        coarse_ms = int(round(coarse_seconds * 1000.0))
        self.seek_back_1_button.setToolTip(f"Seek backward (coarse): {coarse_ms} ms\nShortcut: [")
        self.seek_back_01_button.setToolTip(f"Seek backward (fine): {fine_ms} ms\nShortcut: ,")
        self.seek_fwd_01_button.setToolTip(f"Seek forward (fine): {fine_ms} ms\nShortcut: .")
        self.seek_fwd_1_button.setToolTip(f"Seek forward (coarse): {coarse_ms} ms\nShortcut: ]")

    def _bind_shortcuts(self):
        self._add_shortcut("Space", self._on_restart_loop_clicked)
        self._add_shortcut("F1", self._show_shortcuts_help, allow_when_typing=True)
        self._add_shortcut("Return", self._on_toggle_play_clicked)
        self._add_shortcut("Enter", self._on_toggle_play_clicked)
        self._add_shortcut("L", self._toggle_loop_shortcut)
        self._add_shortcut("A", self._on_set_loop_start_clicked)
        self._add_shortcut("B", self._on_set_loop_end_clicked)
        self._add_shortcut("Ctrl+A", self._on_reset_loop_start_clicked)
        self._add_shortcut("Ctrl+B", self._on_reset_loop_end_clicked)
        self._add_shortcut("Left", lambda: self._seek_relative(-STEPS_SEC_MOVE_1))
        self._add_shortcut("Right", lambda: self._seek_relative(STEPS_SEC_MOVE_1))
        self._add_shortcut("[", self._seek_backward_coarse)
        self._add_shortcut("]", self._seek_forward_coarse)
        self._add_shortcut(",", self._seek_backward_fine)
        self._add_shortcut(".", self._seek_forward_fine)
        self._add_shortcut("Ctrl+[", self._on_jump_previous_favorite_clicked)
        self._add_shortcut("Ctrl+]", self._on_jump_next_favorite_clicked)
        self._add_shortcut("M", self._on_add_favorite_clicked)
        self._add_shortcut("Shift+M", self._on_delete_favorite_clicked)
        self._add_shortcut("C", lambda: self._nudge_speed(STEPS_SPEED))
        self._add_shortcut("X", lambda: self._nudge_speed(-STEPS_SPEED))
        self._add_shortcut("+", lambda: self._nudge_semitones(STEPS_SEMITONES))
        self._add_shortcut("-", lambda: self._nudge_semitones(-STEPS_SEMITONES))

        self._add_keypad_shortcut(Qt.Key.Key_0, self._on_toggle_play_clicked)
        self._add_keypad_shortcut(Qt.Key.Key_1, lambda: self._seek_relative(-STEPS_SEC_MOVE_1))
        self._add_keypad_shortcut(Qt.Key.Key_4, lambda: self._seek_relative(-STEPS_SEC_MOVE_2))
        self._add_keypad_shortcut(Qt.Key.Key_7, lambda: self._seek_relative(-STEPS_SEC_MOVE_3))
        self._add_keypad_shortcut(Qt.Key.Key_3, lambda: self._seek_relative(STEPS_SEC_MOVE_1))
        self._add_keypad_shortcut(Qt.Key.Key_6, lambda: self._seek_relative(STEPS_SEC_MOVE_2))
        self._add_keypad_shortcut(Qt.Key.Key_9, lambda: self._seek_relative(STEPS_SEC_MOVE_3))
        self._add_keypad_shortcut(Qt.Key.Key_8, lambda: self._nudge_speed(STEPS_SPEED))
        self._add_keypad_shortcut(Qt.Key.Key_2, lambda: self._nudge_speed(-STEPS_SPEED))
        self._add_keypad_shortcut(Qt.Key.Key_5, self._on_reset_speed_clicked)
        self._add_keypad_shortcut(Qt.Key.Key_Plus, lambda: self._nudge_semitones(STEPS_SEMITONES))
        self._add_keypad_shortcut(Qt.Key.Key_Minus, lambda: self._nudge_semitones(-STEPS_SEMITONES))
        self._add_keypad_shortcut(Qt.Key.Key_Slash, self._on_set_loop_start_clicked)
        self._add_keypad_shortcut(Qt.Key.Key_Asterisk, self._on_set_loop_end_clicked)

    def _bind_mpv_shortcuts(self):
        keymap = [
            ("SPACE", self._on_restart_loop_clicked),
            ("ENTER", self._on_toggle_play_clicked),
            ("l", self._toggle_loop_shortcut),
            ("a", self._on_set_loop_start_clicked),
            ("b", self._on_set_loop_end_clicked),
            ("Ctrl+a", self._on_reset_loop_start_clicked),
            ("Ctrl+b", self._on_reset_loop_end_clicked),
            ("LEFT", lambda: self._seek_relative(-STEPS_SEC_MOVE_1)),
            ("RIGHT", lambda: self._seek_relative(STEPS_SEC_MOVE_1)),
            ("[", self._seek_backward_coarse),
            ("]", self._seek_forward_coarse),
            (",", self._seek_backward_fine),
            (".", self._seek_forward_fine),
            ("m", self._on_add_favorite_clicked),
            ("M", self._on_delete_favorite_clicked),
            ("Ctrl+[", self._on_jump_previous_favorite_clicked),
            ("Ctrl+]", self._on_jump_next_favorite_clicked),
            ("c", lambda: self._nudge_speed(STEPS_SPEED)),
            ("x", lambda: self._nudge_speed(-STEPS_SPEED)),
        ]

        bound_count = 0
        failed_keys = []
        for keydef, callback in keymap:
            ok = self.controller.player.register_window_key_binding(
                keydef,
                lambda cb=callback, key=keydef: self._queue_mpv_shortcut(key, cb),
            )
            if ok:
                bound_count += 1
            else:
                failed_keys.append(keydef)

        debug_log(
            "ui",
            "mpv_keybind_summary",
            total=len(keymap),
            bound=bound_count,
            failed=",".join(failed_keys) if failed_keys else "none",
        )
        if failed_keys or self.controller.get_debug_logging_settings()[0]:
            self.statusBar().showMessage(
                f"mpv shortcuts bound: {bound_count}/{len(keymap)}",
                2500,
            )

    def _queue_mpv_shortcut(self, keydef: str, callback):
        try:
            self._mpv_shortcut_signal.emit((str(keydef), callback))
            debug_log("ui", "mpv_shortcut_queued", key=keydef)
        except Exception as ex:
            debug_log("ui", "mpv_shortcut_queue_error", key=keydef, error=str(ex))

    @Slot(object)
    def _dispatch_mpv_shortcut(self, payload):
        try:
            keydef, callback = payload
        except Exception:
            debug_log("ui", "mpv_shortcut_dispatch_error", error="invalid_payload")
            return
        try:
            debug_log("ui", "mpv_shortcut_dispatch", key=str(keydef))
            callback()
        except Exception as ex:
            debug_log("ui", "mpv_shortcut_dispatch_error", key=str(keydef), error=str(ex))

    def _add_shortcut(self, key: str, callback, allow_when_typing: bool = False):
        shortcut = QShortcut(QKeySequence(key), self)
        shortcut.setContext(Qt.ApplicationShortcut)
        shortcut.activated.connect(lambda: self._run_shortcut_action(callback, allow_when_typing))

    def _add_keypad_shortcut(self, key, callback):
        modifier = Qt.KeyboardModifier.KeypadModifier
        modifier_value = int(getattr(modifier, "value", modifier))
        key_value = int(getattr(key, "value", key))
        sequence_value = modifier_value | key_value
        shortcut = QShortcut(QKeySequence(sequence_value), self)
        shortcut.setContext(Qt.ApplicationShortcut)
        shortcut.activated.connect(lambda: self._run_shortcut_action(callback, allow_when_typing=False))

    def _run_shortcut_action(self, callback, allow_when_typing: bool):
        if not allow_when_typing and self._is_text_input_focused():
            return
        callback()

    def _is_text_input_focused(self) -> bool:
        focused = QApplication.focusWidget()
        return isinstance(focused, (QLineEdit, QAbstractSpinBox))

    def _seek_relative(self, seconds: float):
        if not self.controller.seek_relative(seconds):
            self.statusBar().showMessage("Please open a file...", 1200)

    def _seek_backward_fine(self):
        fine_seconds, _coarse_seconds = self.controller.get_seek_step_settings_seconds()
        self._seek_relative(-float(fine_seconds))

    def _seek_forward_fine(self):
        fine_seconds, _coarse_seconds = self.controller.get_seek_step_settings_seconds()
        self._seek_relative(float(fine_seconds))

    def _seek_backward_coarse(self):
        _fine_seconds, coarse_seconds = self.controller.get_seek_step_settings_seconds()
        self._seek_relative(-float(coarse_seconds))

    def _seek_forward_coarse(self):
        _fine_seconds, coarse_seconds = self.controller.get_seek_step_settings_seconds()
        self._seek_relative(float(coarse_seconds))

    def _speed_to_slider_value(self, speed_value: float) -> int:
        clamped = max(SPEED_SLIDER_MIN, min(MAX_SPEED_PERCENT, float(speed_value)))
        return int(round(clamped * 10.0))

    def _slider_value_to_speed(self, slider_value: int) -> float:
        ui_speed = max(SPEED_SLIDER_MIN, min(MAX_SPEED_PERCENT, float(slider_value) / 10.0))
        return max(MIN_SPEED_PERCENT, ui_speed)

    def _nudge_speed(self, step: float):
        new_value = round(self.speed_spin.value() + step, 1)
        new_value = max(MIN_SPEED_PERCENT, min(MAX_SPEED_PERCENT, new_value))
        self.speed_spin.setValue(new_value)

    def _nudge_semitones(self, step: int):
        new_value = self.semitones_spin.value() + int(step)
        new_value = max(MIN_PITCH_SEMITONES, min(MAX_PITCH_SEMITONES, new_value))
        self.semitones_spin.setValue(new_value)

    def _on_reset_speed_clicked(self):
        self.speed_spin.setValue(1.0)

    def _toggle_loop_shortcut(self):
        self.loop_toggle_switch.setChecked(not self.loop_toggle_switch.isChecked())

    def _open_startup_session(self):
        loaded, message = self.controller.load_last_session_or_media()
        if loaded:
            self._sync_file_title()
            self._rebuild_recent_menu()
            if message:
                self.statusBar().showMessage(message, 1200)
            self._on_tick()

    def _on_open_clicked(self):
        initial_dir = self.controller.settings.getVal("App", "LastOpenDir", os.path.expanduser("~"))
        filename, _selected = QFileDialog.getOpenFileName(
            self,
            "Open a file",
            initial_dir,
            build_open_filter(),
        )
        if not filename:
            return
        self._open_path(filename, apply_recent_options=False)

    def _on_open_tby_clicked(self):
        initial_dir = self.controller.settings.getVal("App", "LastOpenDir", os.path.expanduser("~"))
        filename, _selected = QFileDialog.getOpenFileName(
            self,
            "Open a .tby file",
            initial_dir,
            build_tby_filter(),
        )
        if not filename:
            return
        self._open_tby_path(filename)

    def _open_tby_path(self, tby_path: str) -> bool:
        ok, message = self.controller.open_tby_session(tby_path)
        if not ok:
            QMessageBox.critical(self, "Error", message or "Unable to open .tby file")
            return False

        self._sync_file_title()
        self._rebuild_recent_menu()
        self.statusBar().showMessage(message or "Loaded .tby session", 1500)
        self._on_tick()
        return True

    def _default_session_stem(self) -> str:
        if self.controller.has_session_tby_path():
            current_tby = self.controller.get_session_tby_path()
            if current_tby:
                return os.path.splitext(os.path.basename(current_tby))[0] or "session"
        if self.controller.media_filename:
            return os.path.splitext(self.controller.media_filename)[0] or self.controller.media_filename
        if self.controller.song_metadata:
            return str(self.controller.song_metadata)
        return "session"

    def _on_save_session_clicked(self):
        if not self.controller.player.canPlay:
            self.statusBar().showMessage("Please open a file...", 1200)
            return

        if not self.controller.has_session_tby_path():
            self._on_save_session_as_clicked()
            return

        ok, message, _saved_path = self.controller.save_tby_session()
        if not ok:
            QMessageBox.critical(self, "Error", message or "Unable to save .tby file")
            return
        self._rebuild_recent_menu()
        self.statusBar().showMessage(message, 1500)

    def _on_save_session_as_clicked(self):
        if not self.controller.player.canPlay:
            self.statusBar().showMessage("Please open a file...", 1200)
            return

        initial_dir = self.controller.settings.getVal("App", "LastSaveDir", os.path.expanduser("~"))
        default_stem = self._default_session_stem()

        filename, _selected = QFileDialog.getSaveFileName(
            self,
            "Save session as",
            os.path.join(initial_dir, default_stem + ".tby"),
            build_tby_filter(),
        )
        if not filename:
            return

        ok, message, _saved_path = self.controller.save_tby_session_as(filename)
        if not ok:
            QMessageBox.critical(self, "Error", message or "Unable to save .tby file")
            return
        self._rebuild_recent_menu()
        self.statusBar().showMessage(message, 1500)

    def _on_export_audio_as_clicked(self):
        if not self.controller.player.canPlay:
            self.statusBar().showMessage("Please open a file...", 1200)
            return

        initial_dir = self.controller.settings.getVal("App", "LastSaveDir", os.path.expanduser("~"))
        default_stem = "output"
        if self.controller.media_filename:
            default_stem = os.path.splitext(self.controller.media_filename)[0] or self.controller.media_filename
        elif self.controller.song_metadata:
            default_stem = self.controller.song_metadata

        filename, _selected = QFileDialog.getSaveFileName(
            self,
            "Save file as",
            os.path.join(initial_dir, default_stem + "." + SAVE_DEFAULT_EXTENSION),
            build_audio_save_filter(),
        )
        if not filename:
            return

        ok, message, _saved_path = self.controller.export_audio_file(filename)
        if not ok:
            QMessageBox.critical(self, "Error", message or "Unable to export file")
            return
        self.statusBar().showMessage(message, 2000)

    def _normalize_recent_path(self, raw_path: str) -> str:
        value = str(raw_path or "").strip()
        if value.startswith("file://"):
            try:
                parsed = QUrl(value)
                if parsed.isLocalFile():
                    value = parsed.toLocalFile()
            except Exception:
                pass
        return os.path.realpath(value) if value else value

    def _open_path(self, file_path: str, apply_recent_options: bool) -> bool:
        target = self._normalize_recent_path(file_path)
        if not target:
            return False
        if str(target).lower().endswith(".tby"):
            return self._open_tby_path(target)
        self.open_media_path(target, apply_recent_options=apply_recent_options)
        return True

    def _on_open_recent_clicked(self, file_key: str):
        normalized = self._normalize_recent_path(file_key)
        if not os.path.isfile(normalized):
            self.controller.remove_recent_file(file_key)
            if normalized and normalized != file_key:
                self.controller.remove_recent_file(normalized)
            self._rebuild_recent_menu()
            QMessageBox.warning(self, "File not found", f"Unable to open file:\n{file_key}")
            return
        self._open_path(normalized, apply_recent_options=True)

    def _on_open_recent_dialog(self):
        recent = self.controller.get_recent_files()
        keys = list(recent.keys())
        keys.reverse()
        if not keys:
            self.statusBar().showMessage("Recent files list is empty", 1200)
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Open Recent")
        dialog.resize(720, 360)

        content = QVBoxLayout(dialog)
        file_list = QListWidget(dialog)
        for key in keys:
            base = os.path.basename(key) if os.path.isabs(key) else key
            item = QListWidgetItem(base)
            item.setToolTip(key)
            item.setData(Qt.UserRole, key)
            file_list.addItem(item)
        file_list.setCurrentRow(0)
        file_list.itemDoubleClicked.connect(lambda _item: dialog.accept())
        content.addWidget(file_list)

        buttons = QDialogButtonBox(QDialogButtonBox.Open | QDialogButtonBox.Cancel, parent=dialog)
        remove_button = buttons.addButton("Remove", QDialogButtonBox.ActionRole)
        remove_button.clicked.connect(lambda: self._remove_selected_recent_item(file_list))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        content.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        item = file_list.currentItem()
        if item is None:
            return
        selected_path = str(item.data(Qt.UserRole) or "")
        if selected_path:
            self._on_open_recent_clicked(selected_path)

    def _remove_selected_recent_item(self, file_list: QListWidget):
        item = file_list.currentItem()
        if item is None:
            return
        selected_path = str(item.data(Qt.UserRole) or "").strip()
        if not selected_path:
            return

        self.controller.remove_recent_file(selected_path)
        normalized = self._normalize_recent_path(selected_path)
        if normalized and normalized != selected_path:
            self.controller.remove_recent_file(normalized)

        row = file_list.row(item)
        removed_item = file_list.takeItem(row)
        del removed_item

        if file_list.count() > 0:
            file_list.setCurrentRow(min(row, file_list.count() - 1))
        self._rebuild_recent_menu()

    def _on_clear_recent_clicked(self):
        self.controller.clear_recent_files()
        self._rebuild_recent_menu()
        self.statusBar().showMessage("Recent files cleared", 1200)

    def _rebuild_recent_menu(self):
        self.recent_menu.clear()
        recent = self.controller.get_recent_files()
        keys = list(recent.keys())
        keys.reverse()

        if not keys:
            empty_action = QAction("(Empty)", self)
            empty_action.setEnabled(False)
            self.recent_menu.addAction(empty_action)
            return

        for key in keys:
            base = os.path.basename(key) if os.path.isabs(key) else key
            action = QAction(base, self)
            action.setStatusTip(key)
            action.triggered.connect(lambda checked=False, path=key: self._on_open_recent_clicked(path))
            self.recent_menu.addAction(action)

    def open_media_path(self, file_path: str, apply_recent_options: bool):
        ok, message = self.controller.load_file(file_path, apply_recent_options=apply_recent_options)
        if not ok:
            QMessageBox.critical(self, "Error", message or "Unable to open media")
            return

        self._sync_file_title()
        self._rebuild_recent_menu()
        self.statusBar().showMessage(self.controller.song_metadata, 1500)
        self._on_tick()

    def _sync_file_title(self):
        if self.controller.media_filename:
            self.setWindowTitle(f"{APP_TITLE} - {self.controller.media_filename}")
        else:
            self.setWindowTitle(APP_TITLE)
        self.media_info_label.setText(self.controller.song_metadata or "No media loaded")

    def _on_toggle_play_clicked(self):
        if not self.controller.toggle_play():
            self.statusBar().showMessage("Please open a file...", 1200)

    def _on_stop_clicked(self):
        self.controller.stop_playing()

    def _on_rewind_clicked(self):
        self._on_restart_loop_clicked()

    def _on_restart_loop_clicked(self):
        restart_result = self.controller.restart_loop_from_a()
        if restart_result == -1:
            self.statusBar().showMessage("Please open a file...", 1200)
            return
        if restart_result == -2:
            return
        if restart_result > 0:
            self.statusBar().showMessage(
                f"At A. Play in {restart_result / 1000.0:.2f}s",
                min(max(restart_result + 400, 900), 6000),
            )
            self._loop_restart_timer.start(restart_result)
            return
        self.statusBar().showMessage("Restart loop from A", 1000)

    def _on_delayed_loop_restart(self):
        if self.controller.player.canPlay and self.controller.has_valid_loop_range():
            self.controller.play()
            self.statusBar().showMessage("Restarted loop from A", 1000)

    def _on_set_loop_start_clicked(self):
        if not self.controller.player.canPlay:
            self.statusBar().showMessage("Please open a file...", 1200)
            return
        current_pos = self.controller.player.query_position()
        ok, boundary_reset = self.controller.set_loop_start_relaxed(current_pos)
        if ok:
            if boundary_reset:
                self.statusBar().showMessage("Loop start updated (B reset)", 1200)
            else:
                self.statusBar().showMessage("Loop start updated", 1000)
            self._on_tick()
        else:
            self.statusBar().showMessage("Loop start must be before B", 1200)

    def _on_set_loop_end_clicked(self):
        if not self.controller.player.canPlay:
            self.statusBar().showMessage("Please open a file...", 1200)
            return
        current_pos = self.controller.player.query_position()
        ok, boundary_reset = self.controller.set_loop_end_relaxed(current_pos)
        if ok:
            if boundary_reset:
                self.statusBar().showMessage("Loop end updated (A reset)", 1200)
            else:
                self.statusBar().showMessage("Loop end updated", 1000)
            self._on_tick()
        else:
            self.statusBar().showMessage("Loop end must be after A", 1200)

    def _on_reset_loop_start_clicked(self):
        if not self.controller.player.canPlay:
            self.statusBar().showMessage("Please open a file...", 1200)
            return
        if self.controller.set_loop_start(0):
            self.statusBar().showMessage("Loop start reset", 1000)
            self._on_tick()

    def _on_reset_loop_end_clicked(self):
        if not self.controller.player.canPlay:
            self.statusBar().showMessage("Please open a file...", 1200)
            return
        duration = self.controller.player.query_duration()
        if duration and self.controller.set_loop_end(duration):
            self.statusBar().showMessage("Loop end reset", 1000)
            self._on_tick()

    def _on_move_loop_start_clicked(self, shift_ms: int):
        ok, message = self.controller.move_loop_start_ms(shift_ms)
        self.statusBar().showMessage(message, 1200)
        if ok:
            self._on_tick()

    def _on_move_loop_end_clicked(self, shift_ms: int):
        ok, message = self.controller.move_loop_end_ms(shift_ms)
        self.statusBar().showMessage(message, 1200)
        if ok:
            self._on_tick()

    def _on_loop_toggle_toggled(self, enabled: bool):
        self.controller.set_loop_enabled(enabled)
        if enabled:
            self.statusBar().showMessage("Loop enabled", 1000)
        else:
            self.statusBar().showMessage("Loop disabled", 1000)

    def _on_progress_pressed(self):
        self._scrubbing_progress = True

    def _on_progress_moved(self, value: int):
        duration_seconds = 0.0
        duration_ns = self.controller.player.query_duration()
        if duration_ns is not None and duration_ns > 0:
            duration_seconds = self.controller.player.song_time(duration_ns) or 0.0
        preview_seconds = duration_seconds * (value / 1000000.0)
        self.time_label.setText(format_seconds_text(preview_seconds))

    def _on_progress_released(self):
        value = self.progress_slider.value()
        self.controller.seek_fraction(value / 1000000.0)
        self._scrubbing_progress = False

    def _apply_loop_range_seconds(self, start_seconds: float, end_seconds: float):
        if self.controller.apply_loop_range_seconds(start_seconds, end_seconds):
            if not self.loop_toggle_switch.isChecked():
                self.loop_toggle_switch.setChecked(True)
            else:
                self.statusBar().showMessage("Loop range updated", 1200)
        else:
            self.statusBar().showMessage("Unable to apply loop range", 1200)

    def _on_timeline_seek(self, target_seconds: float):
        if self.controller.seek_seconds(target_seconds):
            self._on_tick()

    def _on_timeline_loop_select(self, start_seconds: float, end_seconds: float):
        self._apply_loop_range_seconds(start_seconds, end_seconds)

    def _on_timeline_context_request(self, seconds: float, global_position):
        self._show_timeline_context_menu(global_position, seconds)

    def _on_timeline_marker_activate(self, marker_index: int, marker_seconds: float):
        if self.controller.seek_to_favorite(marker_index):
            self.statusBar().showMessage(f"Jump to favorite #{marker_index + 1}", 1000)
            self._on_tick()
            return
        if self.controller.seek_seconds(marker_seconds):
            self.statusBar().showMessage("Jump to marker", 1000)
            self._on_tick()

    def _show_timeline_context_menu(self, global_position, seconds: float):
        self._loop_context_seconds = float(seconds)
        menu = QMenu(self)
        set_start_action = menu.addAction("Set loop start here")
        set_end_action = menu.addAction("Set loop end here")
        chosen = menu.exec(global_position)
        if chosen is set_start_action:
            self._set_loop_start_from_context()
        elif chosen is set_end_action:
            self._set_loop_end_from_context()

    def _set_loop_start_from_context(self):
        if self._loop_context_seconds is None:
            self.statusBar().showMessage("Please open a file...", 1200)
            return
        target = self.controller.player.pipeline_time(self._loop_context_seconds)
        ok, boundary_reset = self.controller.set_loop_start_relaxed(target)
        if ok:
            if boundary_reset:
                self.statusBar().showMessage("Loop start updated (B reset)", 1200)
            else:
                self.statusBar().showMessage("Loop start updated", 1000)
            self._on_tick()
        else:
            self.statusBar().showMessage("Loop start must be before B", 1200)

    def _set_loop_end_from_context(self):
        if self._loop_context_seconds is None:
            self.statusBar().showMessage("Please open a file...", 1200)
            return
        target = self.controller.player.pipeline_time(self._loop_context_seconds)
        ok, boundary_reset = self.controller.set_loop_end_relaxed(target)
        if ok:
            if boundary_reset:
                self.statusBar().showMessage("Loop end updated (A reset)", 1200)
            else:
                self.statusBar().showMessage("Loop end updated", 1000)
            self._on_tick()
        else:
            self.statusBar().showMessage("Loop end must be after A", 1200)

    def _on_speed_changed(self, value: float):
        slider_value = self._speed_to_slider_value(value)
        with QSignalBlocker(self.speed_slider):
            self.speed_slider.setValue(slider_value)
        self.controller.set_speed(value)

    def _on_speed_slider_changed(self, value: int):
        speed_value = self._slider_value_to_speed(value)
        normalized_slider_value = self._speed_to_slider_value(speed_value)
        if normalized_slider_value != int(value):
            with QSignalBlocker(self.speed_slider):
                self.speed_slider.setValue(normalized_slider_value)
        with QSignalBlocker(self.speed_spin):
            self.speed_spin.setValue(speed_value)
        self.controller.set_speed(speed_value)

    def _on_semitones_changed(self, value: int):
        with QSignalBlocker(self.semitones_slider):
            self.semitones_slider.setValue(int(value))
        self._on_pitch_changed()

    def _on_semitones_slider_changed(self, value: int):
        with QSignalBlocker(self.semitones_spin):
            self.semitones_spin.setValue(int(value))
        self._on_pitch_changed()

    def _on_cents_changed(self, value: int):
        with QSignalBlocker(self.cents_slider):
            self.cents_slider.setValue(int(value))
        self._on_pitch_changed()

    def _on_cents_slider_changed(self, value: int):
        with QSignalBlocker(self.cents_spin):
            self.cents_spin.setValue(int(value))
        self._on_pitch_changed()

    def _on_pitch_changed(self):
        self.controller.set_pitch_components(self.semitones_spin.value(), self.cents_spin.value())

    def _on_volume_slider_changed(self, value: int):
        self._sync_volume_spin(value)
        self.controller.set_volume_percent(value)

    def _on_volume_spin_changed(self, value: int):
        self._sync_volume_slider(value)
        self.controller.set_volume_percent(value)

    def _on_reset_semitones_clicked(self):
        self.semitones_spin.setValue(0)

    def _on_reset_cents_clicked(self):
        self.cents_spin.setValue(0)

    def _on_reset_volume_clicked(self):
        self.volume_spin.setValue(MAX_VOLUME // 2)

    def _sync_volume_spin(self, value: int):
        with QSignalBlocker(self.volume_spin):
            self.volume_spin.setValue(value)

    def _sync_volume_slider(self, value: int):
        with QSignalBlocker(self.volume_slider):
            self.volume_slider.setValue(value)

    def _on_add_favorite_clicked(self):
        ok, message = self.controller.add_favorite_at_current()
        self.statusBar().showMessage(message, 1200)
        if ok:
            self._on_tick()

    def _on_delete_favorite_clicked(self):
        ok, message = self.controller.delete_favorite()
        self.statusBar().showMessage(message, 1200)
        if ok:
            self._on_tick()

    def _on_jump_next_favorite_clicked(self):
        ok, message = self.controller.jump_to_next_favorite()
        self.statusBar().showMessage(message, 1200)
        if ok:
            self._on_tick()

    def _on_jump_previous_favorite_clicked(self):
        ok, message = self.controller.jump_to_previous_favorite()
        self.statusBar().showMessage(message, 1200)
        if ok:
            self._on_tick()

    def _on_favorite_row_changed(self, row: int):
        if self._syncing_favorites:
            return
        if row < 0:
            return
        if self.controller.seek_to_favorite(row):
            self.statusBar().showMessage(f"Jump to favorite #{row + 1}", 1000)

    def _build_timeline_markers(self) -> list[dict]:
        markers = []
        for favorite in self.controller.get_favorites_display():
            fav_index = int(favorite.get("index", 0))
            markers.append(
                {
                    "index": fav_index,
                    "time_seconds": favorite.get("time_seconds"),
                    "label": str(fav_index + 1),
                    "color": self._favorite_color_for_index(fav_index),
                }
            )
        return markers

    def _favorite_color_for_index(self, index: int) -> str:
        if not UI_FAVORITE_COLORS:
            return UI_ACCENT
        return UI_FAVORITE_COLORS[int(index) % len(UI_FAVORITE_COLORS)]

    def _show_shortcuts_help(self):
        self._open_settings_dialog(open_tab="shortcuts")

    def _open_about_dialog(self):
        self._open_settings_dialog(open_tab="about")

    def _open_settings_dialog(self, open_tab: str = "playback"):
        dialog = SettingsDialog(self.controller, self, open_tab=open_tab)
        dialog.exec()
        self._configure_seek_tooltips()

    def _refresh_favorites_list(self, snapshot: PlaybackSnapshot):
        self._syncing_favorites = True
        try:
            with QSignalBlocker(self.favorite_list):
                self.favorite_list.clear()
                for favorite in self.controller.get_favorites_display():
                    fav_index = int(favorite.get("index", 0))
                    item = QListWidgetItem(favorite.get("label", "Favorite"))
                    item.setForeground(QColor(self._favorite_color_for_index(fav_index)))
                    self.favorite_list.addItem(item)

                if snapshot.selected_favorite_index is None:
                    self.favorite_list.setCurrentRow(-1)
                else:
                    self.favorite_list.setCurrentRow(int(snapshot.selected_favorite_index))
        finally:
            self._syncing_favorites = False

        self.timeline.set_markers(self._build_timeline_markers())
        self.favorite_count_label.setText(f"{snapshot.favorite_count} total")
        self._favorites_revision_seen = int(snapshot.favorites_revision)

    def _apply_snapshot(self, snapshot: PlaybackSnapshot):
        self.time_label.setText(format_seconds_text(snapshot.position_seconds))

        if not self._scrubbing_progress:
            with QSignalBlocker(self.progress_slider):
                self.progress_slider.setValue(int(snapshot.progress_ratio * 1000000))

        with QSignalBlocker(self.loop_toggle_switch):
            self.loop_toggle_switch.setChecked(snapshot.loop_enabled)

        with QSignalBlocker(self.speed_spin):
            self.speed_spin.setValue(snapshot.speed)
        with QSignalBlocker(self.speed_slider):
            self.speed_slider.setValue(self._speed_to_slider_value(snapshot.speed))

        with QSignalBlocker(self.semitones_spin):
            self.semitones_spin.setValue(snapshot.semitones)
        with QSignalBlocker(self.semitones_slider):
            self.semitones_slider.setValue(int(snapshot.semitones))

        with QSignalBlocker(self.cents_spin):
            self.cents_spin.setValue(snapshot.cents)
        with QSignalBlocker(self.cents_slider):
            self.cents_slider.setValue(int(snapshot.cents))

        self._sync_volume_slider(snapshot.volume_percent)
        self._sync_volume_spin(snapshot.volume_percent)

        if snapshot.is_playing:
            self.play_button.setText("Pause")
            if not self._pause_icon.isNull():
                self.play_button.setIcon(self._pause_icon)
            else:
                self.play_button.setIcon(QIcon())
        else:
            self.play_button.setText("Play")
            if not self._play_icon.isNull():
                self.play_button.setIcon(self._play_icon)
            else:
                self.play_button.setIcon(QIcon())

        self.loop_a_label.setText(f"A: {format_seconds_text(snapshot.loop_start_seconds)}")
        self.loop_b_label.setText(f"B: {format_seconds_text(snapshot.loop_end_seconds)}")

        if not snapshot.loop_enabled:
            self.loop_hint_label.setText("Loop is off")
        elif snapshot.loop_start_seconds is not None and snapshot.loop_end_seconds is not None:
            self.loop_hint_label.setText("Loop active")
        else:
            self.loop_hint_label.setText("Loop is on. Set A/B.")

        duration_seconds = None
        if snapshot.duration_ns is not None and snapshot.duration_ns > 0:
            duration_seconds = self.controller.player.song_time(snapshot.duration_ns)
        self.timeline.set_duration(duration_seconds)
        timeline_playhead_seconds = snapshot.position_seconds
        if duration_seconds is not None and duration_seconds > 0:
            ratio = max(0.0, min(1.0, float(snapshot.progress_ratio)))
            timeline_playhead_seconds = duration_seconds * ratio
        self.timeline.set_playhead(timeline_playhead_seconds)
        self.timeline.set_loop_enabled(snapshot.loop_enabled)
        self.timeline.set_loop(snapshot.loop_start_seconds, snapshot.loop_end_seconds)

        self.media_info_label.setText(snapshot.song_metadata or "No media loaded")
        if snapshot.favorites_revision != self._favorites_revision_seen:
            self._refresh_favorites_list(snapshot)
        else:
            self.favorite_count_label.setText(f"{snapshot.favorite_count} total")

    def _on_tick(self):
        if self.controller.consume_mpv_exit_request():
            app = QApplication.instance()
            if app is not None:
                app.quit()
            return
        snapshot = self.controller.tick()
        self._apply_snapshot(snapshot)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.isLocalFile() for url in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = [url for url in event.mimeData().urls() if url.isLocalFile()]
        if not urls:
            event.ignore()
            return

        file_path = urls[0].toLocalFile()
        if not file_path:
            event.ignore()
            return

        if str(file_path).lower().endswith(".tby"):
            if self._open_tby_path(file_path):
                event.acceptProposedAction()
                return
            event.ignore()
            return

        self.open_media_path(file_path, apply_recent_options=False)
        event.acceptProposedAction()

    def closeEvent(self, event):
        self._tick_timer.stop()
        self._loop_restart_timer.stop()
        self.controller.close()
        super().closeEvent(event)
