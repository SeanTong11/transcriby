import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QWidget

from transcriby.qt_widgets import ShortcutStepDoubleSpinBox, ShortcutStepSpinBox


class ShortcutStepSpinBoxTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_plus_and_minus_step_integer_spinbox_from_line_edit(self):
        spin = ShortcutStepSpinBox()
        spin.setRange(0, 200)
        spin.setValue(100)

        QApplication.sendEvent(
            spin.lineEdit(),
            QKeyEvent(QEvent.KeyPress, Qt.Key.Key_Plus, Qt.KeyboardModifier.NoModifier, "+"),
        )
        self.assertEqual(spin.value(), 101)

        QApplication.sendEvent(
            spin.lineEdit(),
            QKeyEvent(QEvent.KeyPress, Qt.Key.Key_Minus, Qt.KeyboardModifier.NoModifier, "-"),
        )
        self.assertEqual(spin.value(), 100)

    def test_minus_steps_down_for_signed_integer_spinbox_from_line_edit(self):
        spin = ShortcutStepSpinBox()
        spin.setRange(-12, 12)
        spin.setValue(3)

        QApplication.sendEvent(
            spin.lineEdit(),
            QKeyEvent(QEvent.KeyPress, Qt.Key.Key_Minus, Qt.KeyboardModifier.NoModifier, "-"),
        )
        self.assertEqual(spin.value(), 2)

    def test_plus_and_minus_step_double_spinbox_from_line_edit(self):
        spin = ShortcutStepDoubleSpinBox()
        spin.setRange(0.1, 2.0)
        spin.setSingleStep(0.1)
        spin.setDecimals(1)
        spin.setValue(1.0)

        QApplication.sendEvent(
            spin.lineEdit(),
            QKeyEvent(QEvent.KeyPress, Qt.Key.Key_Plus, Qt.KeyboardModifier.ShiftModifier, "+"),
        )
        self.assertAlmostEqual(spin.value(), 1.1)

        QApplication.sendEvent(
            spin.lineEdit(),
            QKeyEvent(QEvent.KeyPress, Qt.Key.Key_Minus, Qt.KeyboardModifier.NoModifier, "-"),
        )
        self.assertAlmostEqual(spin.value(), 1.0)

    def test_line_edit_cursor_returns_to_arrow_after_focus_leaves(self):
        container = QWidget()
        container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        spin = ShortcutStepSpinBox(container)

        container.show()
        spin.show()
        spin.setFocus()
        self.app.processEvents()
        self.assertEqual(spin.lineEdit().cursor().shape(), Qt.CursorShape.IBeamCursor)

        container.setFocus()
        self.app.processEvents()
        self.assertEqual(spin.lineEdit().cursor().shape(), Qt.CursorShape.ArrowCursor)


if __name__ == "__main__":
    unittest.main()
