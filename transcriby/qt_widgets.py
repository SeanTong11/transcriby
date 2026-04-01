#!/usr/bin/env python3
"""Reusable Qt widgets for shortcut-friendly numeric controls."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox


class _ShortcutStepMixin:
    """Turn bare +/- key presses into step changes for non-negative editors."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.lineEdit() and event.type() == QEvent.Type.KeyPress:
            key_event = event if isinstance(event, QKeyEvent) else None
            if key_event is not None and self._handle_step_key(key_event):
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent):
        if self._handle_step_key(event):
            return
        super().keyPressEvent(event)

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


class ShortcutStepSpinBox(_ShortcutStepMixin, QSpinBox):
    """A QSpinBox that treats +/- as increment/decrement while focused."""


class ShortcutStepDoubleSpinBox(_ShortcutStepMixin, QDoubleSpinBox):
    """A QDoubleSpinBox that treats +/- as increment/decrement while focused."""
