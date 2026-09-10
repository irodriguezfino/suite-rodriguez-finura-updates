from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook, load_workbook
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractItemView, QBoxLayout, QCheckBox

try:
    from xlrd import open_workbook
except ModuleNotFoundError:
    open_workbook = None

from suite_pyside6.core.pesos import _as_decimal, calcular_peso_vaciado, process_pesos_files
from suite_pyside6.ui.pesos_window import PesosWindow
from suite_pyside6.ui.polish import prepare_embedded_window
from suite_pyside6.ui.theme import base_qss


HEADERS = [
    "fechaPeso", "loteSacrificio", "loteSacrificioMatadero", "ordenPesada", "horaPeso",
    "pesoBruto", "taraVisor", "taraTrip", "pesoNeto", "canalApto", "estado",
    "tieneIncidencia", "incidencias",
]


def _write_lote(path: Path, sheets: int = 1) -> None:
    book = Workbook()
    book.remove(book.active)
    for index in range(sheets):
        sheet = book.create_sheet(f"Lote {index + 1}")
        sheet.append(HEADERS)
        sheet.append(["2026-07-31", "L", "M", 1, "10:00", 143.70, 2, 3, 138, "S", "OK", "NO", ""])
        sheet.append(["2026-07-31", "L", "M", 2, "10:01", 141.50, 2, 3, 136, "S", "OK", "NO", ""])
        sheet.append(["2026-07-31", "L", "M", 3, "10:02", 141.30, 2, 3, 135, "S", "OK", "NO", ""])
    book.save(path)
    book.close()


class PesosCoreTests(unittest.TestCase):
    def test_calculo_normal_completo_y_redondeo_excel(self) -> None:
        self.assertEqual(calcular_peso_vaciado("143.70", "normal"), "142.1")
        self.assertEqual(calcular_peso_vaciado("141.50", "normal"), "139.9")
        self.assertEqual(calcular_peso_vaciado("143.70", "completo"), "139.2")
        self.assertEqual(calcular_peso_vaciado("141.50", "completo"), "137.0")
        self.assertEqual(calcular_peso_vaciado("141.30", "completo"), "136.8")
        self.assertEqual(calcular_peso_vaciado("1.0", "normal"), "1.0")
        # 1.15 - 1.15 * 0.011 = 1.13735; Excel ROUND(..., 1) is 1.1.
        self.assertEqual(calcular_peso_vaciado("1.15", "normal"), "1.1")

    def test_lectura_decimal_conserva_todos_los_decimales_hasta_el_redondeo_de_negocio(self) -> None:
        self.assertEqual(_as_decimal("12,345"), Decimal("12.345"))
        self.assertEqual(_as_decimal("8,75"), Decimal("8.75"))
        self.assertEqual(_as_decimal("0,125"), Decimal("0.125"))
        self.assertEqual(_as_decimal("99,9999"), Decimal("99.9999"))
        self.assertEqual(_as_decimal("1,01"), Decimal("1.01"))

    def test_calculo_decimal_con_entradas_de_alta_precision(self) -> None:
        expected_normal = {
            "12.345": "12.2",
            "0.125": "0.1",
            "99.9999": "98.9",
            "1.01": "1.0",
        }
        expected_completo = {
            "12.345": "9.3",
            "0.125": "-2.8",
            "99.9999": "96.0",
            "1.01": "-1.9",
        }
        for value, expected in expected_normal.items():
            self.assertEqual(calcular_peso_vaciado(value, "normal"), expected)
        for value, expected in expected_completo.items():
            self.assertEqual(calcular_peso_vaciado(value, "completo"), expected)

    def test_guardar_y_recargar_conserva_el_decimal_resultante_y_su_formato(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "precision.xlsx"
            book = Workbook()
            sheet = book.active
            sheet.append(HEADERS)
            for index, weight in enumerate((12.345, 0.125, 99.9999, 1.01), start=1):
                sheet.append(["2026-07-31", "L", "M", index, "10:00", weight, 2, 3, 1, "S", "OK", "NO", ""])
            book.save(path)
            book.close()

            result = process_pesos_files([path], {path: "normal"})
            self.assertEqual(result.error_count, 0)
            reloaded = load_workbook(path, data_only=False)
            weights = [reloaded.active.cell(row, 6).value for row in range(2, 6)]
            formats = [reloaded.active.cell(row, 6).number_format for row in range(2, 6)]
            reloaded.close()
            self.assertEqual(weights, [12.2, 0.1, 98.9, 1.0])
            self.assertEqual(formats, ["0.0", "0.0", "0.0", "0.0"])

    def test_completo_modifica_solo_peso_bruto_y_todas_las_hojas_con_encabezado(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lote.xlsx"
            _write_lote(path, sheets=2)
            before = load_workbook(path, data_only=False)
            before_values = [
                [[cell.value for cell in row] for row in sheet.iter_rows()]
                for sheet in before.worksheets
            ]
            before.close()

            updates = []
            result = process_pesos_files([path], {path: "completo"}, updates.append)

            self.assertEqual(result.error_count, 0)
            self.assertEqual(result.results[0].adjusted_weights, 6)
            self.assertEqual(updates[-1].completed, updates[-1].total)
            book = load_workbook(path, data_only=False)
            for sheet_index, sheet in enumerate(book.worksheets):
                self.assertEqual(sheet.cell(2, 6).value, 139.2)
                self.assertEqual(sheet.cell(3, 6).value, 137.0)
                self.assertEqual(sheet.cell(4, 6).value, 136.8)
                self.assertEqual(sheet.cell(3, 6).number_format, "0.0")
                for row_index, row in enumerate(sheet.iter_rows(), start=1):
                    for column_index, cell in enumerate(row, start=1):
                        if row_index > 1 and column_index == 6:
                            continue
                        self.assertEqual(cell.value, before_values[sheet_index][row_index - 1][column_index - 1])
            self.assertEqual(book.worksheets[0].title, "Hoja1")
            book.close()

    def test_sin_vaciado_no_modifica_los_pesos(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lote.xlsx"
            _write_lote(path)
            result = process_pesos_files([path], {path: "ninguno"})
            self.assertEqual(result.error_count, 0)
            book = load_workbook(path, data_only=False)
            self.assertEqual([book.active.cell(row, 6).value for row in range(2, 5)], [143.7, 141.5, 141.3])
            self.assertEqual(book.active.title, "Hoja1")
            book.close()

    def test_error_por_encabezado_ausente_no_sobrescribe_archivo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sin_peso.xlsx"
            book = Workbook()
            book.active.append(["otro"])
            book.active.append([12])
            book.save(path)
            book.close()
            original = path.read_bytes()
            updates = []
            result = process_pesos_files([path], {path: "normal"}, updates.append)
            self.assertEqual(result.error_count, 1)
            self.assertIn("pesoBruto", result.results[0].message)
            self.assertEqual(path.read_bytes(), original)
            self.assertLess(updates[-1].completed, updates[-1].total)

    def test_error_por_peso_no_numerico_indica_hoja_y_fila(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalido.xlsx"
            _write_lote(path)
            book = load_workbook(path)
            book.active.cell(3, 6).value = "no valido"
            book.save(path)
            book.close()
            result = process_pesos_files([path], {path: "normal"})
            self.assertEqual(result.error_count, 1)
            self.assertIn("fila 3", result.results[0].message)
            self.assertIn("pesoBruto", result.results[0].message)

    @unittest.skipUnless(
        os.environ.get("PESOS_REFERENCE_DIR") and open_workbook is not None,
        "Defina PESOS_REFERENCE_DIR e instale xlrd para ejecutar la regresión XLS real.",
    )
    def test_lote_xls_de_referencia_coincide_con_vaciado_completo(self) -> None:
        reference_dir = Path(os.environ["PESOS_REFERENCE_DIR"])
        initial = reference_dir / "LOTE 2631115W-inicial.xls"
        expected = reference_dir / "LOTE 2631115W.xls"
        self.assertTrue(initial.is_file())
        self.assertTrue(expected.is_file())
        with tempfile.TemporaryDirectory() as directory:
            working = Path(directory) / initial.name
            shutil.copy2(initial, working)
            result = process_pesos_files([working], {working: "completo"})
            self.assertEqual(result.error_count, 0)
            self.assertEqual(result.results[0].adjusted_weights, 59)
            actual_sheet = open_workbook(working).sheet_by_index(0)
            expected_sheet = open_workbook(expected).sheet_by_index(0)
            actual_header = [str(value).strip().casefold() for value in actual_sheet.row_values(0)]
            expected_header = [str(value).strip().casefold() for value in expected_sheet.row_values(0)]
            actual_column = actual_header.index("pesobruto")
            expected_column = expected_header.index("pesobruto")
            self.assertEqual(actual_sheet.nrows - 1, 59)
            self.assertEqual(
                [actual_sheet.cell_value(row, actual_column) for row in range(1, actual_sheet.nrows)],
                [expected_sheet.cell_value(row, expected_column) for row in range(1, expected_sheet.nrows)],
            )


class PesosWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_vaciados_son_mutuamente_excluyentes_y_se_pueden_limpiar(self) -> None:
        window = PesosWindow()
        path = Path("lote.xlsx")
        window.set_files([path])
        normal = window.result_table.cellWidget(0, 1).findChild(QCheckBox)
        normal.setChecked(True)
        self.assertEqual(window.vaciados[path], "normal")
        complete = window.result_table.cellWidget(0, 2).findChild(QCheckBox)
        complete.setChecked(True)
        self.assertEqual(window.vaciados[path], "completo")
        self.assertFalse(window.result_table.cellWidget(0, 1).findChild(QCheckBox).isChecked())
        window.result_table.cellWidget(0, 2).findChild(QCheckBox).setChecked(False)
        self.assertEqual(window.vaciados[path], "ninguno")
        window.close()

    def test_checkbox_columns_y_texto_de_progreso_tienen_espacio_suficiente(self) -> None:
        window = PesosWindow()
        path = Path("lote.xlsx")
        window.set_files([path])
        self.assertEqual(window.rail_progress.value(), 0)
        for column in (1, 2):
            holder = window.result_table.cellWidget(0, column)
            checkbox = holder.findChild(QCheckBox)
            self.assertEqual(holder.objectName(), "VaciadoCheckHolder")
            self.assertEqual(checkbox.objectName(), "VaciadoCheck")
            self.assertGreaterEqual(window.result_table.columnWidth(column), checkbox.minimumWidth())
            self.assertGreaterEqual(window.result_table.columnWidth(column), holder.sizeHint().width())
            self.assertGreater(window.result_table.rowHeight(0), checkbox.sizeHint().height())
        window._on_progress(type("Progress", (), {"completed": 35, "total": 120, "message": "Procesando 35 de 120"})())
        self.assertEqual(window.rail_progress.value(), 29)
        self.assertIn("Procesando 35 de 120", window.rail_progress_text.text())
        self.assertIn("29 %", window.rail_progress_text.text())
        self.assertEqual(window.result_table.selectionMode(), QAbstractItemView.NoSelection)
        self.assertEqual(window.log.objectName(), "LotControlLog")
        window.close()

    def test_estilos_del_control_mantienen_superficie_blanca_y_checkboxes_limpios(self) -> None:
        stylesheet = base_qss()
        self.assertIn("QFrame#LotControlPrimary, QFrame#LotControlSecondary", stylesheet)
        self.assertIn("QPlainTextEdit#LotControlLog", stylesheet)
        self.assertIn("QWidget#VaciadoCheckHolder, QCheckBox#VaciadoCheck", stylesheet)

    def test_control_del_lote_pasa_de_rail_a_tarjeta_horizontal_en_ancho_medio(self) -> None:
        window = PesosWindow()
        prepare_embedded_window(window)
        window.show()
        window.resize(1040, 720)
        QTest.qWait(30)
        self.assertEqual(window.rail_sections.direction(), QBoxLayout.LeftToRight)
        self.assertGreater(window.rail.maximumWidth(), 10_000)
        self.assertGreaterEqual(window.rail.width(), window.centralWidget().width() - 48)
        self.assertGreaterEqual(window.rail_sections.itemAt(0).widget().width(), 300)
        self.assertGreaterEqual(window.rail_sections.itemAt(1).widget().width(), 220)

        window.resize(1360, 720)
        QTest.qWait(30)
        self.assertEqual(window.rail_sections.direction(), QBoxLayout.TopToBottom)
        self.assertGreaterEqual(window.rail.width(), 300)
        window.close()


if __name__ == "__main__":
    unittest.main()
