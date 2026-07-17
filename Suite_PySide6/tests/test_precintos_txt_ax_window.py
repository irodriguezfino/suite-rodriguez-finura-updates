from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import app_by_key
from suite_pyside6.ui.app_windows import get_window_class
from suite_pyside6.ui.precintos_txt_ax_window import PrecintosTxtAxWindow


class PrecintosTxtAxWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_registro_y_flujo_de_exportacion(self):
        self.assertEqual(app_by_key("precintos_txt_ax").title, "Precintos TXT a CSV AX")
        self.assertIs(get_window_class("precintos_txt_ax"), PrecintosTxtAxWindow)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "listado precintos.txt"
            source.write_text("A -> P001\r\nB -> P001\r\nincorrecta\r\n", encoding="utf-8", newline="")
            output = Path(directory) / "listado precintos.csv"
            window = PrecintosTxtAxWindow()
            window.load_path(source)
            self.assertTrue(window.convert_button.isEnabled())
            window.convert_selected_file()
            self.assertTrue(window.save_button.isEnabled())
            self.assertEqual(window.result.precintos, ["P001", "P001"])
            window.save_path(output)
            self.assertEqual(output.read_bytes(), b"P001\r\nP001\r\n")
            self.assertIn("CSV generado correctamente", window.status.text())
            window.close()

    def test_extension_incorrecta_y_sin_datos_validos(self):
        with tempfile.TemporaryDirectory() as directory:
            window = PrecintosTxtAxWindow()
            window.load_path(Path(directory) / "origen.csv")
            self.assertIn("extensión .txt", window.status.text())
            source = Path(directory) / "vacio.txt"
            source.write_text("sin flecha\nA -> \n", encoding="utf-8")
            window.load_path(source)
            window.convert_selected_file()
            self.assertIn("No se han encontrado", window.status.text())
            self.assertFalse(window.save_button.isEnabled())
            window.close()


if __name__ == "__main__":
    unittest.main()
