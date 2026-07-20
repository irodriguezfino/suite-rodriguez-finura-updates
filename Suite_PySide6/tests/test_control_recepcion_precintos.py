from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import APP_REGISTRY, app_by_key
from suite_pyside6.ui.app_windows import get_window_class
from suite_pyside6.ui.control_recepcion_maquilas_window import ControlRecepcionPrecintosWindow
from suite_pyside6.ui.main_window import MainWindow
from suite_pyside6.ui.personalized_descriptions import (
    PersonalizedDescriptionControl,
    header_description_key,
    migrate_control_recepcion_precintos_header,
    process_description_key,
)
from suite_pyside6.ui.session import (
    MAX_PERSONAL_DESCRIPTION_LENGTH,
    personal_description,
    remove_personal_description,
    save_personal_description,
)


class ControlRecepcionPrecintosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_registro_unificado_y_compatibilidad_de_claves_anteriores(self) -> None:
        app = app_by_key("control_recepcion_precintos")
        self.assertEqual(app.title, "Control y Recepción Precintos")
        self.assertIs(app_by_key("control_recepcion_maquilas"), app)
        self.assertIs(app_by_key("recepcion_maquilas"), app)
        self.assertNotIn("recepcion_maquilas", {item.key for item in APP_REGISTRY})
        self.assertNotIn("control_recepcion_maquilas", {item.key for item in APP_REGISTRY})
        self.assertIs(get_window_class(app.key), ControlRecepcionPrecintosWindow)

    def test_descripciones_independientes_reemplazan_el_texto_estandar(self) -> None:
        app_key = "control_recepcion_precintos"
        header_key = header_description_key(app_key)
        process_one_key = process_description_key(app_key, "catalog")
        process_two_key = process_description_key(app_key, "review")
        with tempfile.TemporaryDirectory() as directory:
            user_a = QSettings(str(Path(directory) / "usuario-a.ini"), QSettings.IniFormat)
            user_b = QSettings(str(Path(directory) / "usuario-b.ini"), QSettings.IniFormat)
            with patch("suite_pyside6.ui.session.settings", return_value=user_a):
                header = PersonalizedDescriptionControl("Descripción estándar de cabecera", header_key)
                process_one = PersonalizedDescriptionControl("Descripción estándar del proceso", process_one_key)
                process_two = PersonalizedDescriptionControl("Otra descripción estándar", process_two_key)
                self.assertEqual(header.description_label.text(), "Descripción estándar de cabecera")
                self.assertEqual(process_one.description_label.text(), "Descripción estándar del proceso")
                self.assertEqual(header.edit_button.text(), "Añadir descripción")

                save_personal_description(header_key, "Cabecera <script>alert(1)</script>")
                save_personal_description(process_one_key, "Proceso uno")
                save_personal_description(process_two_key, "Proceso dos")
                header.configure("Descripción estándar de cabecera", header_key)
                process_one.configure("Descripción estándar del proceso", process_one_key)
                process_two.configure("Otra descripción estándar", process_two_key)
                self.assertEqual(header.description_label.text(), "Cabecera <script>alert(1)</script>")
                self.assertEqual(header.description_label.textFormat(), Qt.PlainText)
                self.assertEqual(process_one.description_label.text(), "Proceso uno")
                self.assertEqual(process_two.description_label.text(), "Proceso dos")
                self.assertEqual(header.edit_button.text(), "Editar descripción")
                self.assertFalse(header.restore_button.isHidden())

                remove_personal_description(header_key)
                header.configure("Descripción estándar de cabecera", header_key)
                self.assertEqual(header.description_label.text(), "Descripción estándar de cabecera")
                self.assertTrue(header.restore_button.isHidden())
                with self.assertRaises(ValueError):
                    save_personal_description(process_one_key, "x" * (MAX_PERSONAL_DESCRIPTION_LENGTH + 1))

                legacy_key = "control_recepcion_precintos.description"
                save_personal_description(legacy_key, "Aclaración previa")
                migrate_control_recepcion_precintos_header()
                self.assertEqual(personal_description(header_key), "Aclaración previa")
                self.assertEqual(personal_description(legacy_key), "")

            with patch("suite_pyside6.ui.session.settings", return_value=user_b):
                self.assertEqual(personal_description(header_key), "")
                other_user_header = PersonalizedDescriptionControl("Descripción estándar de cabecera", header_key)
                self.assertEqual(other_user_header.description_label.text(), "Descripción estándar de cabecera")

    def test_cabecera_y_tarjeta_de_procesos_usan_el_mismo_control_reutilizable(self) -> None:
        app = app_by_key("control_recepcion_precintos")
        with tempfile.TemporaryDirectory() as directory:
            user = QSettings(str(Path(directory) / "usuario.ini"), QSettings.IniFormat)
            with patch("suite_pyside6.ui.session.settings", return_value=user):
                window = MainWindow()
                window.open_app(app)
                self.assertEqual(window.workspace_description.description_label.text(), app.description)
                self.assertEqual(window.workspace_description.edit_button.text(), "Añadir descripción")
                header_buttons = (
                    window.workspace_description.edit_button,
                    window.workspace_description.restore_button,
                    window.about_button,
                    window.home_button,
                )
                self.assertTrue(all(button.property("headerAction") for button in header_buttons))
                self.assertEqual({button.minimumHeight() for button in header_buttons}, {header_buttons[0].minimumHeight()})
                self.assertGreaterEqual(header_buttons[0].minimumHeight(), 36)
                self.assertTrue(all(button.parentWidget() is window.header_actions for button in header_buttons))
                window.resize(1500, 900)
                window.show()
                self.application.processEvents()
                visible_buttons = tuple(button for button in header_buttons if button.isVisible())
                self.assertEqual({button.height() for button in visible_buttons}, {visible_buttons[0].height()})
                self.assertLess(window.header_actions.width(), window.header_actions.parentWidget().width())

                save_personal_description(header_description_key(app.key), "DescripciÃ³n personalizada")
                window._set_workspace_description(app.description, header_description_key(app.key))
                self.application.processEvents()
                self.assertTrue(window.workspace_description.restore_button.isVisible())
                visible_buttons = tuple(button for button in header_buttons if button.isVisible())
                self.assertEqual({button.height() for button in visible_buttons}, {visible_buttons[0].height()})
                process_row = window._process_row(app)
                process_description = process_row.findChild(PersonalizedDescriptionControl)
                self.assertIsNotNone(process_description)
                self.assertEqual(process_description.description_label.text(), app.description)  # type: ignore[union-attr]
                save_personal_description(process_description_key(app.key), "Descripción de la tarjeta")
                process_row = window._process_row(app)
                process_description = process_row.findChild(PersonalizedDescriptionControl)
                self.assertEqual(process_description.description_label.text(), "Descripción de la tarjeta")  # type: ignore[union-attr]
                window.close()


if __name__ == "__main__":
    unittest.main()
