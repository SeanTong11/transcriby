import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

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


if __name__ == "__main__":
    unittest.main()
