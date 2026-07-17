from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook
from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import app_by_key
from suite_pyside6.ui.app_windows import get_window_class
from suite_pyside6.ui.reparto_merma_precintos_window import RepartoMermaPrecintosWindow


class RepartoMermaPrecintosWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    @staticmethod
    def make_source(directory: str, messages: list[str], name: str = "origen.xlsx") -> Path:
        path = Path(directory) / name
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["Mensaje (09:40:14)"])
        for message in messages:
            worksheet.append([message])
        workbook.save(path)
        workbook.close()
        return path

    def test_registro_navegacion_y_estado_inicial(self):
        app = app_by_key("reparto_merma_precintos")
        self.assertEqual(app.title, "Reparto de Merma por Precintos")
        self.assertIs(get_window_class(app.key), RepartoMermaPrecintosWindow)
        window = RepartoMermaPrecintosWindow()
        self.assertEqual(window.state, "Inicial")
        self.assertFalse(window.export_button.isEnabled())
        self.assertTrue(window.load_button.accessibleName())
        self.assertTrue(window.final_weight.accessibleName())
        self.assertTrue(window.preview_table.accessibleDescription())
        window.close()

    def test_flujo_valido_exporta_solo_dos_columnas(self):
        with tempfile.TemporaryDirectory() as directory:
            window = RepartoMermaPrecintosWindow()
            window.load_path(self.make_source(directory, ["A;X;10,00;1", "B;X;20,00;1"]))
            self.assertEqual(window.state, "Fichero analizado")
            self.assertFalse(window.export_button.isEnabled())
            window.final_weight.setText("27,00")
            self.assertEqual(window.state, "Listo para exportar")
            self.assertTrue(window.export_button.isEnabled())
            self.assertEqual(window.preview_table.columnCount(), 4)
            output = Path(directory) / "ax.csv"
            window.save_path(output)
            self.assertEqual(window.state, "Exportación completada")
            self.assertEqual(output.read_text(encoding="cp1252"), "A;9,00\nB;18,00\n")
            self.assertTrue(all(len(row.split(";")) == 2 for row in output.read_text(encoding="cp1252").splitlines()))
            window.close()

    def test_duplicados_no_bloquean_ni_muestran_avisos(self):
        with tempfile.TemporaryDirectory() as directory:
            window = RepartoMermaPrecintosWindow()
            window.load_path(self.make_source(directory, ["A;X;1;1", "A;X;2;1"]))
            self.assertEqual(window.state, "Fichero analizado")
            self.assertEqual(window.preview_table.rowCount(), 2)
            window.final_weight.setText("1,50")
            self.assertEqual(window.state, "Listo para exportar")
            self.assertTrue(window.export_button.isEnabled())
            output = Path(directory) / "duplicados.csv"
            window.save_path(output)
            self.assertEqual(output.read_text(encoding="cp1252"), "A;0,50\nA;1,00\n")
            self.assertFalse(hasattr(window, "issues"))
            window.close()

    def test_vista_previa_limita_las_filas_renderizadas(self):
        with tempfile.TemporaryDirectory() as directory:
            window = RepartoMermaPrecintosWindow()
            window.load_path(self.make_source(directory, [f"P{index};X;1,00;1" for index in range(300)]))
            self.assertEqual(len(window.source_result.records), 300)
            self.assertEqual(window.preview_table.rowCount(), 250)
            self.assertIn("250 de 300", window.preview_count.text())
            window.close()

    def test_recargar_fichero_limpia_el_peso_final_anterior(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.make_source(directory, ["A;X;1,00;1"])
            second = self.make_source(directory, ["B;X;2,00;1"], "segundo.xlsx")
            window = RepartoMermaPrecintosWindow()
            window.load_path(first)
            window.final_weight.setText("1,00")
            self.assertTrue(window.export_button.isEnabled())
            window.load_path(second)
            self.assertEqual(window.final_weight.text(), "")
            self.assertEqual(window.state, "Fichero analizado")
            self.assertFalse(window.export_button.isEnabled())
            window.close()

    def test_error_de_exportacion_se_muestra_y_no_deja_salida_lista(self):
        with tempfile.TemporaryDirectory() as directory:
            window = RepartoMermaPrecintosWindow()
            window.load_path(self.make_source(directory, ["A;X;1,00;1"]))
            window.final_weight.setText("1,00")
            window.save_path(Path(directory) / "no_existe" / "ax.csv")
            self.assertEqual(window.state, "Error de exportación")
            self.assertFalse(window.export_button.isEnabled())
            self.assertIn("No se pudo", window.rail_detail.text())
            window.close()


if __name__ == "__main__":
    unittest.main()
