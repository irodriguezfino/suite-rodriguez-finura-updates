from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

from suite_pyside6.core.apps import app_by_key
from suite_pyside6.ui.main_window import MainWindow


class _FastWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setCentralWidget(QWidget())


class NavigationTests(unittest.TestCase):
    def wait_until(self, condition):
        import time
        deadline = time.monotonic() + 3
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(condition(), "La navegación no completó la solicitud")

    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_apertura_muestra_shell_inmediato_y_reutiliza_la_pagina(self) -> None:
        app = app_by_key("txt_csv")
        with patch("suite_pyside6.ui.main_window.preload_window_class") as preload, patch(
            "suite_pyside6.ui.main_window.preloaded_window_class", return_value=_FastWindow
        ):
            main = MainWindow()
            previous = main.stack.currentWidget()
            main.open_app(app)
            self.assertIs(main.stack.currentWidget(), main.navigation_loading_page)
            self.assertEqual(main.workspace_title.text(), app.title)
            self.wait_until(lambda: app.key in main.app_pages)
            first = main.app_pages[app.key]
            self.assertIs(main.stack.currentWidget(), first)
            main.open_app(app)
            self.assertIs(main.app_pages[app.key], first)
            self.assertEqual(preload.call_count, 0)
            main.close()

    def test_carga_no_registrada_muestra_error_y_reintento(self) -> None:
        app = app_by_key("txt_csv")
        with patch("suite_pyside6.ui.main_window.preload_window_class"), patch(
            "suite_pyside6.ui.main_window.preloaded_window_class", return_value=None
        ):
            main = MainWindow()
            previous = main.stack.currentWidget()
            main.open_app(app)
            self.assertIs(main.stack.currentWidget(), main.navigation_loading_page)
            QTest.qWait(140)
            self.assertIs(main.stack.currentWidget(), main.navigation_loading_page)
            self.assertEqual(main._opening_app_key, "")
            self.assertFalse(main.navigation_retry_button.isHidden())
            main.close()

    def test_doble_solicitud_pendiente_no_crea_dos_ventanas(self) -> None:
        app = app_by_key("palets")
        with patch("suite_pyside6.ui.main_window.preload_window_class") as preload, patch(
            "suite_pyside6.ui.main_window.preloaded_window_class", return_value=None
        ):
            main = MainWindow()
            main.open_app(app)
            main.open_app(app)
            self.assertEqual(preload.call_count, 0)
            self.assertEqual(main.app_pages, {})
            with patch("suite_pyside6.ui.main_window.preloaded_window_class", return_value=_FastWindow):
                main._complete_app_open(app)
            self.assertEqual(list(main.app_pages), [app.key])
            main.close()

    def test_cambio_de_seccion_conserva_el_shell_y_aplica_transicion(self) -> None:
        main = MainWindow()
        sidebar = main.sidebar
        header = main.header
        main.show_view("procesos")
        self.assertIs(main.sidebar, sidebar)
        self.assertIs(main.header, header)
        self.assertIs(main.stack.currentWidget(), main.processes_page)
        self.assertIn(main.processes_page.property("navigationTransition"), {"stable", "reduced"})
        main.close()

    def test_catalogo_no_precarga_y_reutiliza_filas_al_filtrar_y_volver(self):
        with patch("suite_pyside6.ui.main_window.preloaded_window_class") as loader:
            main = MainWindow()
            main.show_view("procesos")
            rows = dict(main._process_rows)
            QTest.qWait(400)
            main.search.setText("pesos")
            self.assertIs(main._process_rows["pesos"], rows["pesos"])
            self.assertFalse(rows["pesos"].isHidden())
            self.assertTrue(rows["palets"].isHidden())
            main.search.clear()
            main.show_dashboard()
            main.show_view("procesos")
            self.assertEqual(main._process_rows, rows)
            loader.assert_not_called()
            main.close()

    def test_veinte_clicks_crean_una_ventana_y_un_registro(self):
        with patch("suite_pyside6.ui.main_window.preloaded_window_class", return_value=_FastWindow) as loader, patch(
            "suite_pyside6.ui.main_window.remember_app_open"
        ) as history:
            main = MainWindow()
            main.show_view("procesos")
            for _ in range(20):
                main.open_app(app_by_key("palets"))
            button = main._pending_open_buttons[0][0]
            self.assertFalse(button.isEnabled())
            self.assertEqual(button.text(), "Abriendo…")
            self.wait_until(lambda: "palets" in main.app_pages)
            self.assertEqual(list(main.app_pages), ["palets"])
            self.assertTrue(button.isEnabled())
            loader.assert_called_once()
            history.assert_called_once_with("palets")
            main.close()

    def test_cancelar_y_volver_a_misma_app_descarta_callback_antiguo(self):
        with patch("suite_pyside6.ui.main_window.preloaded_window_class", return_value=_FastWindow) as loader:
            main = MainWindow()
            selected = app_by_key("txt_csv")
            main.open_app(selected)
            old_request = main._open_request_id
            main.show_view("procesos")
            main.open_app(selected)
            main._complete_app_open(selected, old_request)
            loader.assert_not_called()
            self.wait_until(lambda: selected.key in main.app_pages)
            loader.assert_called_once()
            main.close()

    def test_cerrar_durante_apertura_no_construye_ventana(self):
        with patch("suite_pyside6.ui.main_window.preloaded_window_class", return_value=_FastWindow) as loader:
            main = MainWindow()
            main.open_app(app_by_key("txt_csv"))
            main.close()
            QTest.qWait(50)
            loader.assert_not_called()

    def test_aviso_se_pinta_antes_de_construir_la_aplicacion(self):
        from PySide6.QtCore import QObject, QEvent
        painted = []
        class WatchPaint(QObject):
            def eventFilter(self, watched, event):
                if event.type() == QEvent.Paint:
                    painted.append(True)
                return False
        main = MainWindow()
        main.show()
        self.application.processEvents()
        observer = WatchPaint(main)
        main.navigation_loading_page.installEventFilter(observer)
        def load(_key):
            self.assertTrue(painted, "El aviso debe pintarse antes de iniciar la construcción")
            return _FastWindow
        with patch("suite_pyside6.ui.main_window.preloaded_window_class", side_effect=load):
            main.open_app(app_by_key("txt_csv"))
            self.wait_until(lambda: "txt_csv" in main.app_pages)
        main.close()

    def test_error_restauracion_y_reintento(self):
        with patch("suite_pyside6.ui.main_window.preloaded_window_class", side_effect=ValueError("fallo controlado")):
            main = MainWindow()
            main.open_app(app_by_key("txt_csv"))
            self.wait_until(lambda: not main._opening_app_key)
            self.assertIn("fallo controlado", main.navigation_loading_detail.text())
            self.assertEqual(main._opening_app_key, "")
        with patch("suite_pyside6.ui.main_window.preloaded_window_class", return_value=_FastWindow):
            main.navigation_retry_button.click()
            self.wait_until(lambda: "txt_csv" in main.app_pages)
            self.assertIn("txt_csv", main.app_pages)
            main.close()

    def test_archivos_se_entregan_una_vez_tras_apertura_diferida(self):
        from pathlib import Path
        paths = [Path("lote.txt")]
        with patch("suite_pyside6.ui.main_window.preloaded_window_class", return_value=_FastWindow), patch(
            "suite_pyside6.ui.main_window.handle_dropped_paths", return_value=True
        ) as deliver:
            main = MainWindow()
            with patch.object(main, "_app_for_dropped_paths", return_value=app_by_key("txt_csv")):
                self.assertTrue(main._open_dropped_paths(paths))
                self.assertTrue(main._open_dropped_paths(paths))
                deliver.assert_not_called()
                self.wait_until(lambda: "txt_csv" in main.app_pages)
                deliver.assert_called_once_with(main.app_pages["txt_csv"], paths)
            main.close()

    def test_aperturas_reales_en_interprete_limpio_no_cargan_motores_pesados(self):
        import json
        import os
        import subprocess
        import sys
        from pathlib import Path
        script = Path(__file__).resolve().parents[1] / "tools" / "benchmark_navigation.py"
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        env["PYTHONPATH"] = str(script.parents[1] / "src")
        completed = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                                   env=env, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(len(result["apps"]), 12)
        self.assertEqual(result["heavy_libraries_imported"], [])


if __name__ == "__main__":
    unittest.main()
