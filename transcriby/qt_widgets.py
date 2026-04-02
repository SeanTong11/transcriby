#!/usr/bin/env python3
"""Reusable Qt widgets for shortcut-friendly numeric controls."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox


class _ShortcutStepMixin:
    """Turn bare +/- key presses into step changes and sync cursor state."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.installEventFilter(self)
        self._sync_line_edit_cursor()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.lineEdit():
            if event.type() == QEvent.Type.KeyPress:
                key_event = event if isinstance(event, QKeyEvent) else None
                if key_event is not None and self._handle_step_key(key_event):
                    return True
            if event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
                QTimer.singleShot(0, self._sync_line_edit_cursor)
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent):
        if self._handle_step_key(event):
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event: QFocusEvent):
        super().focusInEvent(event)
        self._sync_line_edit_cursor()

    def focusOutEvent(self, event: QFocusEvent):
        super().focusOutEvent(event)
        self._sync_line_edit_cursor()

    def _handle_step_key(self, event: QKeyEvent) -> bool:
        modifiers = event.modifiers()
        disallowed_modifiers = (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )
        if modifiers & disallowed_modifiers:
            return False

        if event.key() == Qt.Key.Key_Plus:
            self.stepBy(1)
            event.accept()
            return True

        if event.key() == Qt.Key.Key_Minus:
            self.stepBy(-1)
            event.accept()
            return True

        return False

    def _sync_line_edit_cursor(self):
        line_edit = self.lineEdit()
        if line_edit is None:
            return

        cursor_shape = (
            Qt.CursorShape.IBeamCursor
            if self.hasFocus() or line_edit.hasFocus()
            else Qt.CursorShape.ArrowCursor
        )
        line_edit.setCursor(cursor_shape)


class ShortcutStepSpinBox(_ShortcutStepMixin, QSpinBox):
    """A QSpinBox that treats +/- as increment/decrement while focused."""


class ShortcutStepDoubleSpinBox(_ShortcutStepMixin, QDoubleSpinBox):
    """A QDoubleSpinBox that treats +/- as increment/decrement while focused."""
