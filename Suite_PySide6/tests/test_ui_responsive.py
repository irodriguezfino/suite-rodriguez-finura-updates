from __future__ import annotations

import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QBoxLayout, QFrame, QLabel, QMainWindow, QTableWidget, QVBoxLayout, QWidget

from suite_pyside6.ui.app_windows import WINDOW_CLASSES
from suite_pyside6.ui.control_recepcion_maquilas_window import ControlRecepcionPrecintosWindow
from suite_pyside6.ui.file_compare_window import FileCompareWindow
from suite_pyside6.ui.main_window import MainWindow
from suite_pyside6.ui.numerador_etiquetas_window import NumeradorEtiquetasWindow
from suite_pyside6.ui.precintos_excel_window import PrecintosExcelWindow
from suite_pyside6.ui.components import dropzone, empty_state
from suite_pyside6.ui.polish import polish_window, prepare_embedded_window
from suite_pyside6.ui.responsive import make_flow
from suite_pyside6.ui.theme import DARK, base_qss


class ResponsiveSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_paneles_operativos_se_apilan_antes_de_comprimir_el_carril(self) -> None:
        for key, window_class in WINDOW_CLASSES.items():
            window = window_class()
            prepare_embedded_window(window)
            window.resize(1040, 720)
            window.show()
            QTest.qWait(10)
            for workspace in window.findChildren(QFrame, "ControlPilotWorkspace"):
                layout = workspace.layout()
                self.assertIsInstance(layout, QBoxLayout, key)
                self.assertEqual(layout.direction(), QBoxLayout.TopToBottom, key)
            window.close()

    def test_comparador_apila_las_vistas_en_ancho_compacto(self) -> None:
        window = FileCompareWindow()
        window.resize(900, 700)
        window.show()
        QTest.qWait(10)
        self.assertEqual(window.preview_splitter.orientation(), Qt.Vertical)
        window.resize(1100, 700)
        QTest.qWait(10)
        self.assertEqual(window.preview_splitter.orientation(), Qt.Horizontal)
        window.close()

    def test_stepper_compartido_agrupa_paso_y_etiqueta_en_una_unidad_legible(self) -> None:
        window = FileCompareWindow()
        stepper = window.findChild(QFrame, "Stepper")
        workflow_card = window.findChild(QFrame, "WorkflowControlCard")
        self.assertIsNotNone(stepper)
        self.assertIsNotNone(workflow_card)
        self.assertIs(stepper.parentWidget(), workflow_card)
        self.assertEqual(stepper.findChild(QLabel, "StepperIntro").text(), "Flujo")
        self.assertEqual(len(stepper.findChildren(QWidget, "StepItem")), 4)
        self.assertEqual([label.text() for label in stepper.findChildren(QLabel, "StepConnector")], ["—", "—", "—"])
        window.close()

    def test_filas_adaptativas_centran_verticalmente_controles_de_distinta_altura(self) -> None:
        host = QWidget()
        layout = make_flow(host, margin=0, spacing=8)
        compact = QFrame()
        compact.setFixedSize(80, 32)
        summary = QFrame()
        summary.setFixedSize(150, 52)
        layout.addWidget(compact)
        layout.addWidget(summary)
        host.resize(300, 80)
        host.show()
        QTest.qWait(10)
        self.assertLessEqual(abs(compact.geometry().center().y() - summary.geometry().center().y()), 1)
        host.close()

    def test_tema_no_impone_gris_a_todos_los_contenedores_internos(self) -> None:
        stylesheet = base_qss()
        self.assertNotIn("QWidget {\n        background:", stylesheet)
        self.assertIn("QFrame#ControlMetricStrip {", stylesheet)

    def test_contexto_se_compacta_en_ancho_medio_para_priorizar_el_trabajo(self) -> None:
        window = MainWindow()
        window.current_view = "trabajo"
        window.resize(1360, 800)
        window.show()
        QTest.qWait(10)
        window._apply_responsive_state()
        self.assertFalse(window.context_rail.isVisible())
        self.assertTrue(window.compact_context_bar.isVisible())
        self.assertEqual(window.header_layout.direction(), QBoxLayout.TopToBottom)
        window.resize(1500, 800)
        window._apply_responsive_state()
        self.assertTrue(window.context_rail.isVisible())
        self.assertFalse(window.compact_context_bar.isVisible())
        self.assertEqual(window.header_layout.direction(), QBoxLayout.LeftToRight)
        window.close()

    def test_acciones_secundarias_se_agrupan_sin_ocultar_el_flujo(self) -> None:
        compare = FileCompareWindow()
        self.assertEqual(
            [action.text() for action in compare.more_actions_button.menu().actions() if not action.isSeparator()],
            ["Copiar resultado", "Guardar informe", "Abrir archivo A", "Abrir archivo B"],
        )
        labels = NumeradorEtiquetasWindow()
        self.assertEqual(
            [action.text() for action in labels.design_actions_button.menu().actions()],
            ["Eliminar diseño", "Exportar diseño", "Importar diseño"],
        )
        reception = ControlRecepcionPrecintosWindow()
        self.assertEqual(
            [action.text() for action in reception.more_actions_button.menu().actions() if not action.isSeparator()],
            ["Limpiar correcciones", "Generar PDF rangos", "Limpiar trabajo"],
        )
        compare.close()
        labels.close()
        reception.close()

    def test_superficies_incrustadas_no_heredan_el_fondo_negro_del_viewport(self) -> None:
        shell = MainWindow()
        page = PrecintosExcelWindow()
        prepare_embedded_window(page)
        page.setParent(shell.stack)
        page.setWindowFlags(Qt.Widget)
        shell.stack.addWidget(page)
        shell.stack.setCurrentWidget(page)
        shell.resize(1500, 800)
        shell.show()
        QTest.qWait(10)
        toolbar = page.findChild(QFrame, "Toolbar")
        self.assertIsNotNone(toolbar)
        pixel = toolbar.grab().toImage().pixelColor(4, 4).name().lower()
        self.assertNotEqual(pixel, "#000000")
        self.assertIn("QWidget#WindowScrollContent", base_qss())
        shell.close()

    def test_resumen_operativo_se_muestra_antes_de_la_tabla(self) -> None:
        window = QMainWindow()
        root = QWidget()
        panel = QFrame(root)
        panel_layout = QVBoxLayout(panel)
        table = QTableWidget(0, 2, panel)
        strip = QFrame(panel)
        strip.setObjectName("ControlMetricStrip")
        # Simula una de las vistas históricas que añadía el resumen después
        # del detalle: la capa compartida debe normalizarlo sin tocar datos.
        panel_layout.addWidget(table)
        panel_layout.addWidget(strip)
        root_layout = QVBoxLayout(root)
        root_layout.addWidget(panel)
        window.setCentralWidget(root)

        polish_window(window, stepper=False, body_scroll=False)

        self.assertLess(panel_layout.indexOf(strip), panel_layout.indexOf(table))
        window.close()

    def test_estados_vacios_y_zonas_de_carga_tienen_superficies_distintas(self) -> None:
        self.assertEqual(empty_state("Sin resultados").objectName(), "EmptyState")
        self.assertEqual(dropzone("Carga", "Suelta aquí los archivos").objectName(), "Dropzone")

    def test_modo_oscuro_conserva_la_identidad_azul_de_la_suite(self) -> None:
        self.assertEqual(DARK["background"], "#0B1220")
        self.assertEqual(DARK["sidebar_bg"], "#081426")
        self.assertEqual(DARK["primary"], "#89A9FF")

    def test_bandeja_prioriza_carga_y_separa_actividad_de_salidas(self) -> None:
        window = MainWindow()
        self.assertEqual(window.command_title.text(), "Inicia o retoma una operación")
        self.assertEqual(window.dashboard_load_button.text(), "Cargar archivos")
        self.assertEqual(window.dashboard_process_button.text(), "Ver procesos")
        self.assertIsNotNone(window.findChild(QFrame, "DashboardCommandCard"))
        self.assertEqual(len(window.findChildren(QFrame, "ActivityPanel")), 2)
        self.assertGreaterEqual(len(window.dashboard_frequent_layout.parentWidget().findChildren(QFrame, "DashboardProcessCard")), 3)
        window.close()

    def test_bandeja_apila_inicio_y_continuacion_en_ancho_compacto(self) -> None:
        window = MainWindow()
        window.resize(860, 720)
        window.show()
        QTest.qWait(10)
        self.assertEqual(window.dashboard_start_layout.direction(), QBoxLayout.TopToBottom)
        self.assertEqual(window.dashboard_continue_row.direction(), QBoxLayout.TopToBottom)
        window.close()


if __name__ == "__main__":
    unittest.main()
