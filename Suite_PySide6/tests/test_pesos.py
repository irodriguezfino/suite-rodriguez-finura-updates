from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from zipfile import ZipFile
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook, load_workbook
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
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
        self.assertEqual(calcular_peso_vaciado("143.70", "normal"), "142.10")
        self.assertEqual(calcular_peso_vaciado("141.50", "normal"), "139.90")
        self.assertEqual(calcular_peso_vaciado("143.70", "completo"), "139.20")
        self.assertEqual(calcular_peso_vaciado("141.50", "completo"), "137.00")
        self.assertEqual(calcular_peso_vaciado("141.30", "completo"), "136.80")
        self.assertEqual(calcular_peso_vaciado("1.0", "normal"), "1.00")
        # 1.15 - 1.15 * 0.011 = 1.13735; Excel ROUND(..., 1) is 1.1.
        self.assertEqual(calcular_peso_vaciado("1.15", "normal"), "1.10")

    def test_lectura_decimal_conserva_todos_los_decimales_hasta_el_redondeo_de_negocio(self) -> None:
        self.assertEqual(_as_decimal("12,345"), Decimal("12.345"))
        self.assertEqual(_as_decimal("8,75"), Decimal("8.75"))
        self.assertEqual(_as_decimal("0,125"), Decimal("0.125"))
        self.assertEqual(_as_decimal("99,9999"), Decimal("99.9999"))
        self.assertEqual(_as_decimal("1,01"), Decimal("1.01"))

    def test_calculo_decimal_con_entradas_de_alta_precision(self) -> None:
        expected_normal = {
            "12.345": "12.20",
            "0.125": "0.10",
            "99.9999": "98.90",
            "1.01": "1.00",
        }
        expected_completo = {
            "12.345": "9.30",
            "0.125": "-2.80",
            "99.9999": "96.00",
            "1.01": "-1.90",
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
                sheet.append(["2026-07-31", "L", "M", index, "10:00", weight, 2, 3, weight, "S", "OK", "NO", ""])
            book.save(path)
            book.close()

            result = process_pesos_files([path], {path: "normal"})
            self.assertEqual(result.error_count, 0)
            reloaded = load_workbook(path, data_only=False)
            bruto_weights = [reloaded.active.cell(row, 6).value for row in range(2, 6)]
            neto_weights = [reloaded.active.cell(row, 9).value for row in range(2, 6)]
            bruto_formats = [reloaded.active.cell(row, 6).number_format for row in range(2, 6)]
            neto_formats = [reloaded.active.cell(row, 9).number_format for row in range(2, 6)]
            reloaded.close()
            self.assertEqual(bruto_weights, ["12.20", "0.10", "98.90", "1.00"])
            self.assertEqual(neto_weights, [12.345, 0.125, 99.9999, 1.01])
            self.assertEqual(bruto_formats, ["@", "@", "@", "@"])
            self.assertEqual(neto_formats, ["General"] * 4)

    def test_normal_calcula_solo_bruto_y_conserva_neto(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bruto_neto.xlsx"
            book = Workbook()
            sheet = book.active
            sheet.append(HEADERS)
            sheet.append(["2026-07-31", "L", "M", 1, "10:00", 141.50, 2, 3, 143.70, "S", "OK", "NO", ""])
            book.save(path)
            book.close()

            result = process_pesos_files([path], {path: "normal"})
            self.assertEqual(result.error_count, 0)
            self.assertEqual(result.results[0].adjusted_weights, 1)
            reloaded = load_workbook(path, data_only=False)
            self.assertEqual(reloaded.active.cell(2, 6).value, "139.90")
            self.assertEqual(reloaded.active.cell(2, 9).value, 143.70)
            self.assertEqual(reloaded.active.cell(2, 6).number_format, "@")
            self.assertEqual(reloaded.active.cell(2, 9).number_format, "General")
            reloaded.close()

    def test_completo_modifica_solo_bruto_en_todas_las_hojas_con_encabezado(self) -> None:
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
                self.assertEqual(sheet.cell(2, 6).value, "139.20")
                self.assertEqual(sheet.cell(3, 6).value, "137.00")
                self.assertEqual(sheet.cell(4, 6).value, "136.80")
                self.assertEqual(sheet.cell(2, 9).value, 138)
                self.assertEqual(sheet.cell(3, 9).value, 136)
                self.assertEqual(sheet.cell(4, 9).value, 135)
                self.assertEqual(sheet.cell(3, 6).number_format, "@")
                self.assertEqual(sheet.cell(3, 9).number_format, "General")
                for row_index, row in enumerate(sheet.iter_rows(), start=1):
                    for column_index, cell in enumerate(row, start=1):
                        if row_index > 1 and column_index == 6:
                            continue
                        self.assertEqual(cell.value, before_values[sheet_index][row_index - 1][column_index - 1])
            self.assertEqual(book.worksheets[0].title, "Hoja1")
            book.close()

    def test_progreso_distingue_operaciones_sin_medida_de_las_celdas_contadas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lote.xlsx"
            _write_lote(path)
            updates = []
            result = process_pesos_files([path], {path: "normal"}, updates.append)

            self.assertEqual(result.error_count, 0)
            self.assertFalse(any(update.busy for update in updates))
            self.assertTrue(any(not update.busy and "Ajustando pesos" in update.message for update in updates))
            self.assertFalse(updates[-1].busy)
            self.assertEqual(updates[-1].completed, updates[-1].total)

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

    def test_ooxml_directo_preserva_las_partes_no_modificadas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lote.xlsx"
            _write_lote(path)
            payload = b"contenido auxiliar que Pesos no debe tocar"
            with ZipFile(path, "a") as archive:
                archive.writestr("customXml/itemPesosAudit.xml", payload)

            result = process_pesos_files([path], {path: "normal"})

            self.assertEqual(result.error_count, 0)
            with ZipFile(path, "r") as archive:
                self.assertEqual(archive.read("customXml/itemPesosAudit.xml"), payload)

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

    def test_peso_neto_no_numerico_se_conserva_sin_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "neto_invalido.xlsx"
            _write_lote(path)
            book = load_workbook(path)
            book.active.cell(3, 9).value = "no valido"
            book.save(path)
            book.close()
            result = process_pesos_files([path], {path: "normal"})
            self.assertEqual(result.error_count, 0)
            book = load_workbook(path)
            self.assertEqual(book.active.cell(3, 9).value, "no valido")
            book.close()

    def test_neto_preserva_formula_tipo_estilo_y_celdas_vacias_en_ambos_vaciados(self) -> None:
        from xml.etree import ElementTree as ET
        from openpyxl.styles import PatternFill
        namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

        def neto_xml(path):
            with ZipFile(path) as archive:
                root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
                return {cell.attrib["r"]: ET.tostring(cell) for cell in root.iter(namespace + "c")
                        if cell.attrib["r"].startswith("B")}

        for suffix in (".xlsx", ".xlsm"):
            for mode in ("normal", "completo"):
                with self.subTest(suffix=suffix, mode=mode), tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / ("neto" + suffix)
                    book = Workbook()
                    sheet = book.active
                    sheet.append(["pesoBruto", "pesoNeto"])
                    for value in (138.123, "138,123", "=SUM(1,2)", "pendiente", None):
                        sheet.append([143.7, value])
                    for row in range(2, 7):
                        sheet.cell(row, 2).number_format = "0.0000"
                        sheet.cell(row, 2).fill = PatternFill("solid", fgColor="FFFF00")
                    book.save(path)
                    book.close()
                    before = neto_xml(path)
                    result = process_pesos_files([path], {path: mode})
                    self.assertEqual(result.error_count, 0)
                    self.assertEqual(result.results[0].adjusted_weights, 5)
                    self.assertEqual(neto_xml(path), before)

    def test_vaciado_solo_requiere_bruto_e_ignora_encabezados_neto_duplicados(self) -> None:
        for headers in (["pesoBruto"], ["pesoBruto", "pesoNeto", "pesoNeto"]):
            with self.subTest(headers=headers), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "bruto.xlsx"
                book = Workbook()
                book.active.append(headers)
                book.active.append([143.7] + ["no tocar"] * (len(headers) - 1))
                book.save(path)
                book.close()
                result = process_pesos_files([path], {path: "completo"})
                self.assertEqual(result.error_count, 0)
                self.assertEqual(result.results[0].adjusted_weights, 1)

    @unittest.skipUnless(os.environ.get("PESOS_REFERENCE_DIR"), "Integración Excel real: configure PESOS_REFERENCE_DIR.")
    def test_xls_representativos_sobre_copias(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        try:
            from verify_user_pesos import verify
            result = verify(Path(os.environ["PESOS_REFERENCE_DIR"]))
            self.assertTrue(result["originals_unchanged"])
            self.assertGreater(result["verification"]["gross_checked"], 0)
        finally:
            sys.path.pop(0)


class PesosWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_vaciados_son_mutuamente_excluyentes_y_se_pueden_limpiar(self) -> None:
        window = PesosWindow()
        path = Path("lote.xlsx")
        window.set_files([path])
        normal = window.result_table.model().index(0, 1)
        window.result_table.activate(normal)
        self.assertEqual(window.vaciados[path], "normal")
        complete = window.result_table.model().index(0, 2)
        window.result_table.activate(complete)
        self.assertEqual(window.vaciados[path], "completo")
        self.assertEqual(normal.data(Qt.CheckStateRole), Qt.Unchecked)
        window.result_table.activate(complete)
        self.assertEqual(window.vaciados[path], "ninguno")
        window.close()

    def test_elegir_vaciado_conserva_la_posicion_en_lotes_largos(self) -> None:
        window = PesosWindow()
        paths = [Path(f"lote_{index:03}.xlsx") for index in range(80)]
        window.set_files(paths)
        window.show()
        QTest.qWait(30)
        scroll = window.result_table.verticalScrollBar()
        scroll.setValue(scroll.maximum())
        expected_position = scroll.value()
        window.result_table.activate(window.result_table.model().index(len(paths) - 1, 1))
        self.assertEqual(window.vaciados[paths[-1]], "normal")
        self.assertEqual(scroll.value(), expected_position)
        window.close()

    def test_checkbox_columns_y_texto_de_progreso_tienen_espacio_suficiente(self) -> None:
        window = PesosWindow()
        path = Path("lote.xlsx")
        window.set_files([path])
        self.assertEqual(window.rail_progress.value(), 0)
        for column in (1, 2):
            self.assertGreaterEqual(window.result_table.columnWidth(column), 164)
            self.assertEqual(window.result_table.model().index(0, column).data(Qt.CheckStateRole), Qt.Unchecked)
        self.assertFalse(window.result_table.findChildren(QCheckBox))
        window._on_progress(type("Progress", (), {"completed": 35, "total": 120, "message": "Procesando 35 de 120"})())
        self.assertEqual(window.rail_progress.value(), 29)
        self.assertIn("Procesando 35 de 120", window.rail_progress_text.text())
        self.assertIn("29 %", window.rail_progress_text.text())
        window._on_progress(type("Progress", (), {"completed": 1, "total": 2, "message": "Validando archivo", "busy": True})())
        self.assertEqual(window.rail_progress.maximum(), 100)
        self.assertEqual(window.rail_progress.value(), 50)
        self.assertIn("50 %", window.rail_progress_text.text())
        self.assertEqual(window.result_table.selectionMode(), QAbstractItemView.ExtendedSelection)
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
