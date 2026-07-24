from __future__ import annotations

from types import SimpleNamespace
import unittest

from PySide6.QtWidgets import QApplication, QMainWindow

from suite_pyside6.core.apps import APP_REGISTRY
from suite_pyside6.ui.app_windows import get_window_class
from suite_pyside6.ui.polish import close_risk_reason, polish_window, show_inline_message


class CloseGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_archivos_solo_cargados_no_generan_aviso(self) -> None:
        window = QMainWindow()
        window.paths = ["entrada.txt"]  # type: ignore[attr-defined]
        window.result = SimpleNamespace(selected_files=["entrada.txt"])  # type: ignore[attr-defined]
        self.assertEqual(close_risk_reason(window), "")

    def test_resultado_procesado_sin_salida_generar_aviso(self) -> None:
        window = QMainWindow()
        window.result = SimpleNamespace(processed_lines=["registro"])  # type: ignore[attr-defined]
        self.assertIn("todavía no se han exportado", close_risk_reason(window))

    def test_salida_final_elimina_aviso_hasta_que_cambie_el_resultado(self) -> None:
        window = QMainWindow()
        window.result = SimpleNamespace(processed_lines=["registro"])  # type: ignore[attr-defined]
        show_inline_message(window, "success", "CSV guardado: salida.csv")
        self.assertEqual(close_risk_reason(window), "")
        window.result = SimpleNamespace(processed_lines=["nuevo registro"])  # type: ignore[attr-defined]
        self.assertIn("todavía no se han exportado", close_risk_reason(window))

    def test_operacion_activa_tiene_prioridad(self) -> None:
        window = QMainWindow()
        window.setProperty("operationActive", True)
        self.assertIn("operación en curso", close_risk_reason(window))

    def test_guard_permite_cierre_inmediato_sin_trabajo(self) -> None:
        window = QMainWindow()
        polish_window(window)
        self.assertTrue(window.close())

    def test_todas_las_aplicaciones_inician_limpias_y_cierran_sin_aviso(self) -> None:
        for app in APP_REGISTRY:
            with self.subTest(app=app.key):
                window_class = get_window_class(app.key)
                self.assertIsNotNone(window_class)
                window = window_class()  # type: ignore[operator]
                self.assertEqual(close_risk_reason(window), "")
                self.assertTrue(window.close())


if __name__ == "__main__":
    unittest.main()
