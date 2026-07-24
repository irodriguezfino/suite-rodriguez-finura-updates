from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolButton

from suite_pyside6.ui.components import ActionMenuButton, ModernSelect, SearchableComboBox
from suite_pyside6.ui.main_window import MainWindow
from suite_pyside6.ui.mermas_window import MermasWindow


class ModernSelectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_selector_nativo_muestra_valor_y_respeta_opciones_deshabilitadas(self) -> None:
        select = ModernSelect(placeholder="Selecciona estado")
        select.add_option("Pendiente", "pending")
        select.add_option("Archivado", "archived", enabled=False)
        select.setCurrentIndex(0)
        self.assertEqual(select.currentData(), "pending")
        self.assertFalse(bool(select.model().flags(select.model().index(1, 0)) & Qt.ItemIsEnabled))
        self.assertEqual(select.minimumHeight(), 40)
        self.assertEqual(select.focusPolicy(), Qt.StrongFocus)
        self.assertFalse(select.isEditable())
        self.assertEqual(select.cursor().shape(), Qt.PointingHandCursor)

    def test_chevron_siempre_tiene_espacio_y_cambia_el_estado_del_popup(self) -> None:
        select = ModernSelect()
        select.add_option("Una opción de texto especialmente larga para comprobar el espacio", "long")
        select.resize(280, 40)
        select.show()
        self.application.processEvents()
        self.assertTrue(select.property("chevronVisible"))
        self.assertGreater(select.chevron_rect().width(), 0)
        select.showPopup()
        self.application.processEvents()
        self.assertTrue(select.property("popupOpen"))
        select.hidePopup()
        self.assertFalse(select.property("popupOpen"))
        select.setEnabled(False)
        select.showPopup()
        self.assertFalse(select.property("popupOpen"))
        self.assertTrue(select.grab().isNull() is False)
        select.close()

    def test_teclado_abre_cierra_y_devuelve_el_foco(self) -> None:
        select = ModernSelect()
        select.add_option("Uno", 1)
        select.add_option("Dos", 2)
        select.show()
        select.setFocus()
        with patch.object(select, "showPopup") as show_popup:
            QTest.keyClick(select, Qt.Key_Space)
            show_popup.assert_called_once()
        with patch.object(select, "hidePopup") as hide_popup:
            QTest.keyClick(select, Qt.Key_Escape)
            self.assertFalse(hide_popup.called)
        self.assertTrue(select.focusPolicy() == Qt.StrongFocus)
        select.close()

    def test_combobox_busqueda_y_menu_de_acciones_son_componentes_reutilizables(self) -> None:
        combo = SearchableComboBox(placeholder="Busca un proceso")
        combo.add_option("Precintos Jamones", "precintos")
        combo.add_option("Merma Jamones", "mermas")
        combo.setCurrentIndex(0)
        self.assertTrue(combo.isEditable())
        self.assertEqual(combo.lineEdit().cursor().shape(), Qt.IBeamCursor)
        self.assertTrue(combo.lineEdit().isClearButtonEnabled())
        self.assertEqual(combo.completer().filterMode(), Qt.MatchContains)
        combo._update_search_feedback("sin coincidencias")
        self.assertEqual(combo.completer().model().index(0, 0).data(), "No se encontraron opciones")

        menu = ActionMenuButton(accessible_name="Acciones de categoría")
        delete = menu.add_action("Eliminar", lambda: None, destructive=True)
        self.assertEqual(menu.popupMode(), QToolButton.ToolButtonPopupMode.InstantPopup)
        self.assertTrue(delete.property("destructive"))
        self.assertEqual(menu.accessibleName(), "Acciones de categoría")

    def test_pantallas_migradas_usan_componentes_modernos(self) -> None:
        main = MainWindow()
        mermas = MermasWindow()
        self.assertIsInstance(main.theme_combo, ModernSelect)
        self.assertIsInstance(main.organization_app_combo, SearchableComboBox)
        self.assertIsInstance(main.organization_target_combo, ModernSelect)
        self.assertIsInstance(main.category_actions_button, ActionMenuButton)
        self.assertIsInstance(mermas.filter_combo, ModernSelect)
        self.assertTrue(main.theme_combo.property("chevronVisible"))
        self.assertTrue(main.organization_app_combo.property("chevronVisible"))
        self.assertTrue(main.organization_target_combo.property("chevronVisible"))
        self.assertTrue(mermas.filter_combo.property("chevronVisible"))
        self.assertTrue(mermas.filter_combo.property("filterSelect"))
        main.close()
        mermas.close()


if __name__ == "__main__":
    unittest.main()
