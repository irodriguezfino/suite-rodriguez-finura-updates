from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook
from PySide6.QtWidgets import QApplication, QFrame, QLabel

from suite_pyside6.core.apps import app_by_key
from suite_pyside6.ui.app_windows import get_window_class
from suite_pyside6.ui.polish import operational_snapshot, prepare_embedded_window
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
        self.assertEqual(app.title, "Precintos Deshuesado")
        self.assertIs(get_window_class(app.key), RepartoMermaPrecintosWindow)
        window = RepartoMermaPrecintosWindow()
        self.assertEqual(window.state, "Inicial")
        self.assertIs(window.centralWidget(), window.stack)
        self.assertIs(window.stack.currentWidget(), window.selection_page)
        self.assertEqual(window.stack.count(), 3)
        self.assertFalse(bool(window.property("bodyScrollWrapped")))
        self.assertFalse(window.export_button.isEnabled())
        self.assertTrue(window.load_button.accessibleName())
        self.assertTrue(window.final_weight.accessibleName())
        self.assertTrue(window.work_order.accessibleName())
        self.assertTrue(window.preview_table.accessibleDescription())
        window.show_pda()
        self.assertFalse(window.pda_back_button.isHidden())
        window.pda_back_button.click()
        self.assertIs(window.stack.currentWidget(), window.selection_page)
        window.show_fac()
        self.assertFalse(window.fac_back_button.isHidden())
        window.fac_back_button.click()
        self.assertIs(window.stack.currentWidget(), window.selection_page)
        window.close()

    def test_fac_agrega_elimina_y_exporta_sin_repartir(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "fac.csv"
            source.write_text("a;b;c;PREC-1;10;7.9;21;SI\na;b;c;PREC-2;10;8.0;20;NO\n", encoding="utf-8")
            window = RepartoMermaPrecintosWindow()
            window.show_fac()
            window.add_fac_paths([source])
            self.assertEqual(len(window.fac_result.records), 1)
            self.assertFalse(window.fac_work_order.isHidden())
            self.assertFalse(window.fac_export_button.isEnabled())
            window.fac_work_order.setText("000123")
            self.assertTrue(window.fac_export_button.isEnabled())
            output = Path(directory) / "ax.csv"
            window.save_fac_path(output, window.fac_work_order.text())
            self.assertEqual(output.read_text(encoding="cp1252"), "000123;PREC-1;7,90\n")
            window.fac_files_table.cellWidget(0, 2).click()
            self.assertEqual(window.fac_files_table.rowCount(), 0)
            window.add_fac_paths([source])
            window.fac_clear_button.click()
            self.assertEqual(window.fac_files_table.rowCount(), 0)
            self.assertEqual(window.fac_work_order.text(), "")
            window.close()

    def test_fac_embebida_mantiene_acciones_y_contexto_del_modo(self):
        window = RepartoMermaPrecintosWindow()
        prepare_embedded_window(window)
        window.show()
        window.show_fac()
        self.application.processEvents()
        self.assertTrue(window.fac_back_button.isVisible())
        self.assertTrue(window.fac_add_button.isVisible())
        self.assertTrue(window.fac_work_order.isVisible())
        self.assertEqual(operational_snapshot(window)["next"], "Añadir archivos CSV")
        window.close()

    def test_fac_reutiliza_el_flujo_guiado_y_actualiza_cada_etapa(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "fac.csv"
            source.write_text("a;b;c;PREC-1;10;7.9;21;SI\n", encoding="utf-8")
            window = RepartoMermaPrecintosWindow()
            window.show_fac()

            self.assertEqual(window.fac_state, "Inicial")
            self.assertEqual(window.fac_rail_progress.value(), 0)
            self.assertEqual(window.fac_command_hint.text(), "Añadir archivos CSV")
            self.assertEqual(len(window.fac_page.findChildren(QLabel, "StepBadge")), 4)
            fac_steps = [label.text() for label in window.fac_page.findChildren(QLabel, "StepText")]
            self.assertEqual(fac_steps, ["Cargar archivos", "Procesar y validar", "Indicar orden de trabajo", "Guardar CSV AX"])
            self.assertNotIn("peso final", " ".join(fac_steps).casefold())

            window.add_fac_paths([source])
            self.assertEqual(window.fac_state, "Orden de trabajo pendiente")
            self.assertEqual(window.fac_rail_progress.value(), 70)
            self.assertEqual(window.fac_command_hint.text(), "Indicar orden de trabajo")
            self.assertEqual(window.flow_state(), (2, False, False))

            window.fac_work_order.setText("OT-0001")
            self.assertEqual(window.fac_state, "Listo para exportar")
            self.assertTrue(window.fac_export_button.isEnabled())
            self.assertEqual(window.fac_rail_progress.value(), 85)
            self.assertEqual(window.fac_command_hint.text(), "Guardar CSV AX")

            output = Path(directory) / "ax.csv"
            window.save_fac_path(output, window.fac_work_order.text())
            self.assertEqual(window.fac_state, "Exportación completada")
            self.assertEqual(window.fac_rail_progress.value(), 100)
            self.assertEqual(window.fac_command_hint.text(), "Iniciar nueva operación")
            self.assertEqual(window.flow_state(), (4, False, True))

            window.clear_fac()
            self.assertEqual(window.fac_state, "Inicial")
            self.assertEqual(window.fac_rail_progress.value(), 0)
            window.close()

    def test_pda_stepper_no_se_renderiza_como_tarjeta(self):
        window = RepartoMermaPrecintosWindow()
        pda_stepper = window.pda_page.findChild(QFrame, "Stepper")
        self.assertIsNotNone(pda_stepper)
        self.assertTrue(pda_stepper.property("plainStepper"))
        window.close()

    def test_toolbars_pda_y_fac_comparten_el_mismo_estilo_base(self):
        window = RepartoMermaPrecintosWindow()
        pda_toolbar = window.pda_page.findChild(QFrame, "Toolbar")
        fac_toolbar = window.fac_page.findChild(QFrame, "Toolbar")
        self.assertIsNotNone(pda_toolbar)
        self.assertIsNotNone(fac_toolbar)
        self.assertEqual(pda_toolbar.property("controlCommand"), fac_toolbar.property("controlCommand"))
        self.assertEqual(pda_toolbar.property("flowWrapped"), fac_toolbar.property("flowWrapped"))
        self.assertEqual(pda_toolbar.property("preserveButtonText"), fac_toolbar.property("preserveButtonText"))
        window.close()

    def test_fac_error_de_salida_indica_reintento_sin_perder_los_datos(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "fac.csv"
            source.write_text("a;b;c;PREC-1;10;7.9;21;SI\n", encoding="utf-8")
            window = RepartoMermaPrecintosWindow()
            window.show_fac()
            window.add_fac_paths([source])
            window.fac_work_order.setText("OT-0002")

            window.save_fac_path(Path(directory) / "no_existe" / "ax.csv", "OT-0002")
            self.assertEqual(window.fac_state, "Error de exportación")
            self.assertTrue(window.fac_export_button.isEnabled())
            self.assertEqual(window.fac_command_hint.text(), "Elegir otra ubicación de salida")
            self.assertEqual(window.context_snapshot()["next"], "Elegir otra ubicación de salida")
            window.close()

    def test_flujo_valido_exporta_orden_precinto_y_peso(self):
        with tempfile.TemporaryDirectory() as directory:
            window = RepartoMermaPrecintosWindow()
            window.load_path(self.make_source(directory, ["A;X;10,00;1", "B;X;20,00;1"]))
            self.assertEqual(window.state, "Fichero analizado")
            self.assertFalse(window.export_button.isEnabled())
            window.final_weight.setText("27,00")
            self.assertEqual(window.state, "Orden de trabajo pendiente")
            self.assertFalse(window.export_button.isEnabled())
            window.work_order.setText("OT-0001")
            self.assertEqual(window.state, "Listo para exportar")
            self.assertTrue(window.export_button.isEnabled())
            self.assertEqual(window.preview_table.columnCount(), 4)
            output = Path(directory) / "ax.csv"
            window.save_path(output, "OT-0001")
            self.assertEqual(window.state, "Exportación completada")
            self.assertEqual(output.read_text(encoding="cp1252"), "OT-0001;A;9,00\nOT-0001;B;18,00\n")
            self.assertTrue(all(len(row.split(";")) == 3 for row in output.read_text(encoding="cp1252").splitlines()))
            window.close()

    def test_duplicados_no_bloquean_ni_muestran_avisos(self):
        with tempfile.TemporaryDirectory() as directory:
            window = RepartoMermaPrecintosWindow()
            window.load_path(self.make_source(directory, ["A;X;1;1", "A;X;2;1"]))
            self.assertEqual(window.state, "Fichero analizado")
            self.assertEqual(window.preview_table.rowCount(), 2)
            window.final_weight.setText("1,50")
            window.work_order.setText("OT-0002")
            self.assertEqual(window.state, "Listo para exportar")
            self.assertTrue(window.export_button.isEnabled())
            output = Path(directory) / "duplicados.csv"
            window.save_path(output, "OT-0002")
            self.assertEqual(output.read_text(encoding="cp1252"), "OT-0002;A;0,50\nOT-0002;A;1,00\n")
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
            window.work_order.setText("OT-0001")
            self.assertTrue(window.export_button.isEnabled())
            window.load_path(second)
            self.assertEqual(window.final_weight.text(), "")
            self.assertEqual(window.work_order.text(), "")
            self.assertEqual(window.state, "Fichero analizado")
            self.assertFalse(window.export_button.isEnabled())
            window.close()

    def test_error_de_exportacion_se_muestra_y_no_deja_salida_lista(self):
        with tempfile.TemporaryDirectory() as directory:
            window = RepartoMermaPrecintosWindow()
            window.load_path(self.make_source(directory, ["A;X;1,00;1"]))
            window.final_weight.setText("1,00")
            window.work_order.setText("OT-0003")
            window.save_path(Path(directory) / "no_existe" / "ax.csv")
            self.assertEqual(window.state, "Error de exportación")
            self.assertTrue(window.export_button.isEnabled())
            self.assertEqual(window.command_hint.text(), "Elegir otra ubicación de salida")
            self.assertIn("No se pudo", window.rail_detail.text())
            output = Path(directory) / "ax.csv"
            window.save_path(output)
            self.assertEqual(window.state, "Exportación completada")
            self.assertEqual(output.read_text(encoding="cp1252"), "OT-0003;A;1,00\n")
            window.close()

    def test_orden_de_trabajo_vacia_no_genera_archivo(self):
        with tempfile.TemporaryDirectory() as directory:
            window = RepartoMermaPrecintosWindow()
            window.load_path(self.make_source(directory, ["A;X;1,00;1"]))
            window.final_weight.setText("1,00")
            output = Path(directory) / "ax.csv"
            window.work_order.setText("   ")
            window.save_path(output)
            self.assertFalse(output.exists())
            self.assertEqual(window.state, "Orden de trabajo pendiente")
            self.assertFalse(window.export_button.isEnabled())
            window.close()

    def test_orden_de_trabajo_en_el_panel_activa_el_guardado_y_se_recorta(self):
        with tempfile.TemporaryDirectory() as directory:
            window = RepartoMermaPrecintosWindow()
            window.load_path(self.make_source(directory, ["A;X;1,00;1"]))
            window.final_weight.setText("1,00")
            self.assertFalse(window.export_button.isEnabled())
            window.work_order.setText("  000123  ")
            self.assertEqual(window.state, "Listo para exportar")
            self.assertTrue(window.export_button.isEnabled())
            output = Path(directory) / "ax.csv"
            window.save_path(output)
            self.assertEqual(output.read_text(encoding="cp1252"), "000123;A;1,00\n")
            window.close()


if __name__ == "__main__":
    unittest.main()
