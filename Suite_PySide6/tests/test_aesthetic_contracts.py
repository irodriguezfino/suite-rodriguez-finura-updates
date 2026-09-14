from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame, QPushButton, QStyle, QStyleOptionSpinBox

from suite_pyside6.ui import session, theme
from suite_pyside6.ui.components import module_row
from suite_pyside6.ui.personalized_descriptions import PersonalizedDescriptionControl
from suite_pyside6.ui.visual_controls import ModernCheckBox, ModernSpinBox


class AestheticContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='suite-visual-test-')
        self.addCleanup(self.temp.cleanup)
        prefs = QSettings(str(Path(self.temp.name) / 'settings.ini'), QSettings.IniFormat)
        self.enterContext(patch.object(session, 'settings', return_value=prefs))
        self.enterContext(patch.object(theme, 'current_theme_preference', return_value='light'))

    def keep(self, widget):
        self.addCleanup(widget.hide)
        self.addCleanup(widget.deleteLater)
        return widget

    def test_actions_keep_same_axis_density_long_text_and_focus(self):
        control = PersonalizedDescriptionControl('Descripción normal', 'test.description')
        primary = QPushButton('Abrir')
        row = self.keep(module_row('Título largo de una aplicación', '', 'Jamones', 'Disponible', 'Alt+1', primary, control))
        row.setStyleSheet(theme.base_qss())
        row.show()
        for width in (1050, 750, 460):
            row.resize(width, 200)
            for compact in (True, False):
                row.catalog_metadata.setVisible(not compact)
                control.set_compact(compact)
                control.description_label.setText('Descripción larga con datos del trabajo. ' * 10)
                QTest.qWait(10)
                self.assertTrue(control._actions_menu.isVisible())
                first, second = row.catalog_action_buttons
                before = (first.size(), second.size())
                for button in (first, second):
                    button.setFocus()
                    QTest.qWait(5)
                    a = first.mapTo(row, QPoint()).y() + first.height()/2
                    b = second.mapTo(row, QPoint()).y() + second.height()/2
                    self.assertLessEqual(abs(a-b), 1)
                    self.assertEqual(first.height(), second.height())
                    self.assertEqual(before, (first.size(), second.size()))
                self.assertEqual(row._actions_below, width == 460)

    def test_description_menu_preserves_callbacks_and_personal_text(self):
        with patch.object(PersonalizedDescriptionControl, 'edit_description') as edit:
            control = PersonalizedDescriptionControl('Estándar', 'test.description')
            row = self.keep(module_row('Aplicación', '', 'Grupo', 'Disponible', '', QPushButton('Abrir'), control))
            control._actions_menu.menu().actions()[0].trigger()
            edit.assert_called_once_with()
            self.assertFalse(control._restore_action.isEnabled())
            session.save_personal_description('test.description', 'Mi descripción privada')
            for compact in (True, False, True):
                control.set_compact(compact)
                self.assertEqual(control.description_label.text(), 'Mi descripción privada')
                self.assertTrue(control._restore_action.isEnabled())
                self.assertFalse(control.restore_button.isVisible())

    def test_larger_fonts_keep_action_geometry_and_keyboard_menu(self):
        control = PersonalizedDescriptionControl('Descripción', 'test.description')
        row = self.keep(module_row('Aplicación', '', 'Grupo', 'Disponible', '', QPushButton('Abrir'), control))
        row.setStyleSheet(theme.base_qss() + '\nQWidget { font-size: 14pt; }')
        row.resize(720, 150)
        row.show()
        QTest.qWait(10)
        first, second = row.catalog_action_buttons
        self.assertEqual(first.height(), second.height())
        self.assertGreaterEqual(first.height(), first.fontMetrics().height() + 10)
        from PySide6.QtCore import QTimer
        seen = []
        menu = first.menu()
        menu.aboutToShow.connect(lambda: seen.append(True))
        QTimer.singleShot(30, menu.close)
        first.setFocus()
        QTest.keyClick(first, Qt.Key_Space)
        self.assertEqual(seen, [True])

    def test_checkmark_is_visible_and_keyboard_states_are_native(self):
        box = self.keep(ModernCheckBox('Opción'))
        box.setStyleSheet(theme.base_qss())
        box.resize(180, 40)
        box.show()
        box.setFocus()
        QTest.qWait(5)
        unchecked = box.grab().toImage()
        QTest.keyClick(box, Qt.Key_Space)
        self.assertTrue(box.isChecked())
        checked = box.grab().toImage()
        self.assertNotEqual(unchecked, checked)
        box.setTristate(True)
        box.setCheckState(Qt.PartiallyChecked)
        self.assertNotEqual(checked, box.grab().toImage())
        box.setEnabled(False)
        QTest.keyClick(box, Qt.Key_Space)
        self.assertEqual(box.checkState(), Qt.PartiallyChecked)

    def test_spinbox_arrows_keyboard_limits_and_value_unchanged(self):
        spin = self.keep(ModernSpinBox())
        spin.setStyleSheet(theme.base_qss())
        spin.setRange(1, 10000)
        spin.setValue(100)
        spin.resize(180, 40)
        spin.show()
        spin.setFocus()
        QTest.keyClick(spin, Qt.Key_Up)
        self.assertEqual(spin.value(), 101)
        option = QStyleOptionSpinBox()
        spin.initStyleOption(option)
        rect = spin.style().subControlRect(QStyle.CC_SpinBox, option, QStyle.SC_SpinBoxDown, spin)
        QTest.mouseClick(spin, Qt.LeftButton, pos=rect.center())
        self.assertEqual(spin.value(), 100)
        spin.setValue(10000)
        spin.stepUp()
        self.assertEqual(spin.value(), 10000)

    def test_comparison_options_keep_original_defaults(self):
        from suite_pyside6.ui.file_compare_window import FileCompareWindow
        from suite_pyside6.core.file_compare.models import CompareMode
        window = self.keep(FileCompareWindow())
        self.assertEqual(window.mode.currentData(), CompareMode.STRICT.value)
        self.assertEqual(window.maximum.value(), 100)
        self.assertFalse(window.ignore_case.isChecked())
        self.assertFalse(window.ignore_whitespace.isChecked())
        self.assertFalse(window.ignore_eol.isChecked())

    def test_empty_pesos_does_not_hide_recovery_or_drop_paths(self):
        from suite_pyside6.ui.pesos_window import PesosWindow
        window = self.keep(PesosWindow())
        window.show()
        self.assertTrue(window.metrics_strip.isHidden())
        self.assertFalse(window.recovery_button.isHidden())
        files = [Path('Nombre de archivo muy largo de un lote de prueba.xls')]
        window.set_files(files)
        self.assertEqual(window.result_table.rowCount(), 1)
        self.assertFalse(window.metrics_strip.isHidden())
        self.assertEqual(window.result_table.model().index(0, 0).data(Qt.ToolTipRole), str(files[0]))
        self.assertGreaterEqual(window.result_table.columnWidth(0), 120)

    def test_pda_fac_buttons_keep_same_destinations_and_state(self):
        from suite_pyside6.ui.reparto_merma_precintos_window import RepartoMermaPrecintosWindow
        window = self.keep(RepartoMermaPrecintosWindow())
        window.pda_mode_button.click()
        self.assertIs(window.stack.currentWidget(), window.pda_page)
        window.show_selection()
        window.fac_mode_button.click()
        self.assertIs(window.stack.currentWidget(), window.fac_page)
        self.assertIsInstance(window.fac_mode_button.parentWidget(), QFrame)

    def test_header_is_short_and_dashboard_does_not_repeat_catalogue(self):
        from suite_pyside6.ui.main_window import MainWindow
        window = self.keep(MainWindow())
        window.resize(1360, 850)
        window.show()
        QTest.qWait(10)
        header = window.findChild(QFrame, 'ConsoleHeader')
        self.assertLess(header.height(), 145)
        self.assertFalse(window.continue_strip.isVisible())
        labels = [button.text() for button in window.dashboard_page.findChildren(QPushButton) if button.isVisible()]
        self.assertEqual(labels.count('Ver procesos'), 1)
        self.assertNotIn('Ver catálogo', labels)
        window.resize(960, 620)
        QTest.qWait(10)
        if window.sidebar_logo is not None:
            pixmap = window.sidebar_logo.pixmap()
            self.assertLessEqual(pixmap.width()/pixmap.devicePixelRatioF(), window.sidebar_logo.width())


if __name__ == '__main__':
    unittest.main()
