from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QMimeData, QPointF, QUrl, Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import app_by_key
from suite_pyside6.ui.app_windows import get_window_class
from suite_pyside6.ui.main_window import MainWindow
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
            output = Path(directory) / "listado precintos"
            window = PrecintosTxtAxWindow()
            window.load_path(source)
            self.assertTrue(window.convert_button.isEnabled())
            self.assertEqual(window.result.precintos, ["P001", "P001"])
            self.assertEqual(window.metric_lines.text(), "3")
            self.assertEqual(window.metric_valid.text(), "2")
            self.assertEqual(window.metric_duplicates.text(), "1")
            self.assertEqual(window.precintos_list.toPlainText(), "P001\nP001")
            self.assertEqual(window.ignored_table.rowCount(), 1)
            self.assertEqual(window.ignored_table.item(0, 0).text(), "3")
            self.assertEqual(window.ignored_table.item(0, 1).text(), "incorrecta")
            self.assertEqual(window.ignored_table.item(0, 2).text(), "Separador no encontrado")
            metric_rows = {
                window.metrics_layout.getItemPosition(window.metrics_layout.indexOf(metric))[0]
                for metric in (
                    window.metric_lines,
                    window.metric_valid,
                    window.metric_exported,
                    window.metric_duplicates,
                    window.metric_skipped,
                )
            }
            self.assertEqual(metric_rows, {0})
            window.save_path(output)
            self.assertEqual(output.with_suffix(".csv").read_bytes(), b"P001\r\nP001\r\n")
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
            self.assertIn("No se han encontrado", window.status.text())
            self.assertFalse(window.convert_button.isEnabled())
            window.close()

    def test_cargar_un_segundo_archivo_limpia_el_resultado_anterior(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "primero.txt"
            second = Path(directory) / "segundo.txt"
            first.write_text("A -> PRIMERO\n", encoding="utf-8")
            second.write_text("B -> SEGUNDO\n", encoding="utf-8")
            window = PrecintosTxtAxWindow()
            window.load_path(first)
            self.assertEqual(window.result.precintos, ["PRIMERO"])
            self.assertEqual(window.ignored_table.rowCount(), 0)
            self.assertFalse(window.ignored_empty.isHidden())
            window.load_path(second)
            self.assertEqual(window.result.precintos, ["SEGUNDO"])
            self.assertEqual(window.ignored_table.rowCount(), 0)
            window.close()

    def test_tabla_de_ignoradas_se_actualiza_y_coincide_con_el_conteo(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "mezclado.txt"
            source.write_text("\nA -> OK\nSIN FLECHA\nB -> \nC -> COD\x00IGO\n", encoding="utf-8")
            window = PrecintosTxtAxWindow()
            window.load_path(source)
            self.assertEqual(window.result.precintos, ["OK"])
            self.assertEqual(window.metric_skipped.text(), "4")
            self.assertEqual(window.ignored_table.rowCount(), 4)
            self.assertEqual(
                [window.ignored_table.item(row, 2).text() for row in range(4)],
                [
                    "Línea vacía",
                    "Separador no encontrado",
                    "Segunda columna vacía",
                    "Caracteres no permitidos en el precinto",
                ],
            )
            window.close()

    def test_click_convertir_ejecuta_el_flujo_completo_y_escribe_el_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "origen.txt"
            output = Path(directory) / "salida.csv"
            source.write_text("A -> 0001\nB -> P002\nSin separador\n", encoding="utf-8")
            window = PrecintosTxtAxWindow()
            window.load_path(source)
            with patch("suite_pyside6.ui.precintos_txt_ax_window.save_file", return_value=output) as save_dialog:
                window.convert_button.click()
            self.assertTrue(save_dialog.called)
            self.assertEqual(window.result.precintos, ["0001", "P002"])
            self.assertEqual(window.metric_lines.text(), "3")
            self.assertEqual(window.metric_exported.text(), "2")
            self.assertEqual(window.metric_skipped.text(), "1")
            self.assertEqual(window.output_path, output)
            self.assertEqual(output.read_bytes(), b"0001\r\nP002\r\n")
            self.assertIn("CSV generado correctamente", window.status.text())
            window.close()

    def test_error_de_escritura_se_muestra_y_conserva_la_conversion(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "origen.txt"
            source.write_text("A -> P001\n", encoding="utf-8")
            window = PrecintosTxtAxWindow()
            window.load_path(source)
            with self.assertLogs("suite_pyside6.ui.precintos_txt_ax_window", level="ERROR"):
                with patch("suite_pyside6.ui.precintos_txt_ax_window.write_ax_csv", side_effect=OSError("sin permiso")):
                    window.save_path(Path(directory) / "bloqueado.csv")
            self.assertEqual(window.result.precintos, ["P001"])
            self.assertIsNone(window.output_path)
            self.assertIn("No se ha podido generar", window.status.text())
            window.close()

    def test_flujo_embebido_en_la_suite_convierte_y_guarda(self):
        get_window_class("precintos_txt_ax")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "origen.txt"
            output = Path(directory) / "resultado.csv"
            source.write_text("A -> 0000123\nB -> P002\n", encoding="utf-8")
            menu = MainWindow()
            menu.show()
            definition = app_by_key("precintos_txt_ax")
            menu.open_app(definition)
            QTest.qWait(50)
            window = menu.open_windows[definition.key]
            with patch("suite_pyside6.ui.precintos_txt_ax_window.save_file", return_value=output):
                window.load_path(source)
                window.convert_button.click()
            self.assertEqual(window.result.precintos, ["0000123", "P002"])
            self.assertEqual(output.read_bytes(), b"0000123\r\nP002\r\n")
            self.assertEqual(window.output_path, output)
            menu.close()

    def test_cancelar_selectores_no_altera_el_estado(self):
        window = PrecintosTxtAxWindow()
        with patch("suite_pyside6.ui.precintos_txt_ax_window.open_file", return_value=None):
            window.select_file()
        self.assertIsNone(window.source_path)
        self.assertFalse(window.convert_button.isEnabled())

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "origen.txt"
            source.write_text("A -> 0001\n", encoding="utf-8")
            window.load_path(source)
            with patch("suite_pyside6.ui.precintos_txt_ax_window.save_file", return_value=None):
                window.save_csv_dialog()
            self.assertEqual(window.result.precintos, ["0001"])
            self.assertTrue(window.convert_button.isEnabled())
        window.close()

    def test_solo_hay_un_boton_de_exportacion(self):
        window = PrecintosTxtAxWindow()
        button_texts = [button.text() for button in window.findChildren(type(window.convert_button))]
        self.assertEqual(button_texts.count("Convertir a CSV"), 1)
        self.assertNotIn("CSV", button_texts)
        self.assertFalse(hasattr(window, "save_button"))
        window.close()

    def test_arrastrar_txt_lo_procesa_automaticamente(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "arrastrado.txt"
            source.write_text("A -> DROP-001\n", encoding="utf-8")
            mime_data = QMimeData()
            mime_data.setUrls([QUrl.fromLocalFile(str(source))])
            event = QDropEvent(
                QPointF(10, 10),
                Qt.DropAction.CopyAction,
                mime_data,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            window = PrecintosTxtAxWindow()
            window.upload_area.dropEvent(event)
            self.assertTrue(event.isAccepted())
            self.assertEqual(window.result.precintos, ["DROP-001"])
            self.assertTrue(window.convert_button.isEnabled())
            window.close()


if __name__ == "__main__":
    unittest.main()
