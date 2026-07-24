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
            self.assertIs(main.stack.currentWidget(), previous)
            self.assertEqual(main.workspace_title.text(), app.title)
            QTest.qWait(10)
            first = main.app_pages[app.key]
            self.assertIs(main.stack.currentWidget(), first)
            main.open_app(app)
            self.assertIs(main.app_pages[app.key], first)
            self.assertEqual(preload.call_count, 1)
            main.close()

    def test_skeleton_solo_aparece_si_la_carga_supera_el_umbral(self) -> None:
        app = app_by_key("txt_csv")
        with patch("suite_pyside6.ui.main_window.preload_window_class"), patch(
            "suite_pyside6.ui.main_window.preloaded_window_class", return_value=None
        ):
            main = MainWindow()
            previous = main.stack.currentWidget()
            main.open_app(app)
            self.assertIs(main.stack.currentWidget(), previous)
            QTest.qWait(140)
            self.assertIs(main.stack.currentWidget(), main.navigation_loading_page)
            main._opening_app_key = ""
            main.close()

    def test_doble_solicitud_pendiente_no_crea_dos_ventanas(self) -> None:
        app = app_by_key("palets")
        with patch("suite_pyside6.ui.main_window.preload_window_class") as preload, patch(
            "suite_pyside6.ui.main_window.preloaded_window_class", return_value=None
        ):
            main = MainWindow()
            main.open_app(app)
            main.open_app(app)
            self.assertEqual(preload.call_count, 1)
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


if __name__ == "__main__":
    unittest.main()
